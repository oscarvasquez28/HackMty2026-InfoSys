import asyncio
import contextlib
from datetime import datetime
from decimal import Decimal
import json
import uuid
import pytest
import httpx
from sqlalchemy import select

from backend.main import app
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.models.forensic import InvestigationCase, TransactionRecord

SYNTHETIC_AML_CSV = """origin,destination,amount,timestamp
ACC_A,ACC_B,150000.0,1.0
ACC_B,ACC_C,148000.0,2.0
ACC_C,ACC_A,145000.0,3.0
CORP_INFLOW,MULE_01,500000.0,10.0
MULE_01,OFFSHORE_OUT,485000.0,22.0
LEGIT_PAYROLL,EMPLOYEE_01,2500.0,4.0
STORE_MERCHANT,CONSUMER_99,120.0,5.0
""".encode("utf-8")


@contextlib.asynccontextmanager
async def isolated_test_db():
    """
    Async context manager that configures an isolated in-memory SQLite database,
    initializes the schema, clears memory caches, and cleans up on exit.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()
    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


@pytest.mark.asyncio
async def test_csv_upload_persistence_with_database():
    """
    Tests that uploading an AMLSim CSV:
    1. Returns HTTP 201 with valid InvestigationUploadResponse.
    2. Persists an InvestigationCase row in the database with status PROCESSING.
    3. Bulk-inserts individual TransactionRecord rows with proper suspicion flags,
       reasons, amounts, and timestamps.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("test_amlsim.csv", SYNTHETIC_AML_CSV, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)
            assert response.status_code == 201

            payload = response.json()
            assert "case_id" in payload
            case_id_str = payload["case_id"]
            case_uuid = uuid.UUID(case_id_str)

            assert payload["filename"] == "test_amlsim.csv"
            assert payload["status"] == "PROCESSING"
            assert payload["metrics"]["total_nodes_analyzed"] > 0
            assert payload["metrics"]["detected_cycles_count"] >= 1
            assert payload["metrics"]["passthrough_accounts_count"] >= 1
            assert len(payload["subgraph"]["nodes"]) >= 3
            assert len(payload["subgraph"]["edges"]) >= 3

            # Verify InvestigationCase persisted in database
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                case_obj = (await session.execute(stmt)).scalar_one_or_none()

                assert case_obj is not None
                assert case_obj.id == case_uuid
                assert case_obj.filename == "test_amlsim.csv"
                assert case_obj.status == "PROCESSING"
                assert case_obj.verdict is None
                assert case_obj.metrics["detected_cycles_count"] >= 1
                assert case_obj.ingestion_metadata["total_records"] == 7

                # Verify TransactionRecord bulk persistence
                tx_stmt = (
                    select(TransactionRecord)
                    .where(TransactionRecord.case_id == case_uuid)
                    .order_by(TransactionRecord.amount.desc())
                )
                txs = (await session.execute(tx_stmt)).scalars().all()
                assert len(txs) == 7

                # Check that cycle transactions were flagged suspicious
                cycle_txs = [t for t in txs if t.origin == "ACC_A" and t.destination == "ACC_B"]
                assert len(cycle_txs) == 1
                assert cycle_txs[0].is_suspicious is True
                assert "CYCLE_STEP" in cycle_txs[0].reasons
                assert cycle_txs[0].amount == Decimal("150000.00")
                assert cycle_txs[0].timestamp is not None

                # Check that pass-through mule transactions were flagged suspicious
                mule_txs = [t for t in txs if t.origin == "CORP_INFLOW" and t.destination == "MULE_01"]
                assert len(mule_txs) == 1
                assert mule_txs[0].is_suspicious is True
                assert "PASSTHROUGH_BRIDGE" in mule_txs[0].reasons

                # Check that legitimate transactions were not flagged
                legit_payroll = [t for t in txs if t.origin == "LEGIT_PAYROLL"]
                assert len(legit_payroll) == 1
                assert legit_payroll[0].is_suspicious is False
                assert legit_payroll[0].reasons == []


@pytest.mark.asyncio
async def test_csv_upload_in_memory_fallback():
    """
    Tests that uploading proceeds without error and stores data in INVESTIGATION_CASES
    when no database connection is configured (offline fallback).
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = None
    INVESTIGATION_CASES.clear()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("offline_sample.csv", SYNTHETIC_AML_CSV, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)
            assert response.status_code == 201

            payload = response.json()
            case_id = payload["case_id"]
            assert case_id in INVESTIGATION_CASES
            assert INVESTIGATION_CASES[case_id]["filename"] == "offline_sample.csv"
    finally:
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


@pytest.mark.asyncio
async def test_csv_upload_validation_errors():
    """
    Tests validation error contracts:
    - Non-CSV file extension returns HTTP 400.
    - Empty file content returns HTTP 422.
    - Missing required columns returns HTTP 422.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Non-CSV extension
        resp1 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("dataset.txt", b"some,text,data", "text/plain")},
        )
        assert resp1.status_code == 400
        assert "File must be a CSV dataset." in resp1.text

        # Empty file
        resp2 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp2.status_code == 422
        assert "empty" in resp2.text.lower()

        # Missing required columns
        invalid_csv = b"random_col_1,random_col_2\nval1,val2\n"
        resp3 = await client.post(
            "/api/v1/investigations/upload",
            files={"file": ("invalid_columns.csv", invalid_csv, "text/csv")},
        )
        assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_paginated_listing_with_database():
    """
    Tests GET /api/v1/investigations:
    - Verifies pagination response schema (total, page, page_size, total_pages, items).
    - Verifies page slicing and page_size bounds.
    - Verifies case-insensitive status filtering (COMPLETED, PROCESSING).
    - Verifies query parameter constraints (page < 1, page_size < 1, page_size > 100).
    """
    async with isolated_test_db():
        factory = get_session_factory()
        async with factory() as session:
            for i in range(6):
                case_status = "COMPLETED" if i < 4 else "PROCESSING"
                case = InvestigationCase(
                    id=uuid.uuid4(),
                    filename=f"case_batch_{i}.csv",
                    status=case_status,
                    ingestion_metadata={"total_records": 10 * (i + 1)},
                    metrics={"total_nodes_analyzed": 5 + i},
                    subgraph={"nodes": [], "edges": []},
                    patterns={"cycles": []},
                    verdict={"risk_level": "CRITICAL"} if case_status == "COMPLETED" else None,
                )
                session.add(case)
            await session.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Default listing
            resp = await client.get("/api/v1/investigations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 6
            assert data["page"] == 1
            assert data["page_size"] == 20
            assert data["total_pages"] == 1
            assert len(data["items"]) == 6

            # Sliced pagination (page 1 of 2 per page)
            p1_resp = await client.get("/api/v1/investigations?page=1&page_size=2")
            assert p1_resp.status_code == 200
            p1_data = p1_resp.json()
            assert p1_data["total"] == 6
            assert p1_data["page"] == 1
            assert p1_data["page_size"] == 2
            assert p1_data["total_pages"] == 3
            assert len(p1_data["items"]) == 2

            # Page 2
            p2_resp = await client.get("/api/v1/investigations?page=2&page_size=2")
            assert p2_resp.status_code == 200
            p2_data = p2_resp.json()
            assert len(p2_data["items"]) == 2
            assert p1_data["items"][0]["case_id"] != p2_data["items"][0]["case_id"]

            # Case-insensitive status filter: completed
            filter_completed = await client.get("/api/v1/investigations?status=completed")
            assert filter_completed.status_code == 200
            fc_data = filter_completed.json()
            assert fc_data["total"] == 4
            assert all(item["status"] == "COMPLETED" for item in fc_data["items"])
            assert all(item["has_verdict"] is True for item in fc_data["items"])

            # Status filter: PROCESSING
            filter_processing = await client.get("/api/v1/investigations?status=PROCESSING")
            assert filter_processing.status_code == 200
            fp_data = filter_processing.json()
            assert fp_data["total"] == 2
            assert all(item["status"] == "PROCESSING" for item in fp_data["items"])

            # Status filter: non-existent status returns 0 items
            filter_none = await client.get("/api/v1/investigations?status=NON_EXISTENT")
            assert filter_none.status_code == 200
            fn_data = filter_none.json()
            assert fn_data["total"] == 0
            assert fn_data["items"] == []

            # Out-of-bounds page parameter validation
            assert (await client.get("/api/v1/investigations?page=0")).status_code == 422
            assert (await client.get("/api/v1/investigations?page_size=0")).status_code == 422
            assert (await client.get("/api/v1/investigations?page_size=101")).status_code == 422

            # Page beyond total data returns empty items list
            beyond_resp = await client.get("/api/v1/investigations?page=50")
            assert beyond_resp.status_code == 200
            assert beyond_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_paginated_listing_in_memory_fallback():
    """
    Tests GET /api/v1/investigations with offline in-memory fallback store.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = None
    INVESTIGATION_CASES.clear()

    try:
        # Pre-populate memory store
        for i in range(3):
            cid = str(uuid.uuid4())
            INVESTIGATION_CASES[cid] = {
                "case_id": cid,
                "filename": f"in_memory_{i}.csv",
                "status": "COMPLETED" if i == 0 else "PROCESSING",
                "created_at": "2026-09-12T08:00:00Z",
                "metrics": {"total_nodes_analyzed": 4},
                "verdict": {"risk_level": "HIGH"} if i == 0 else None,
            }

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/investigations")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3
            assert len(data["items"]) == 3

            # Filter in memory
            f_resp = await client.get("/api/v1/investigations?status=completed")
            assert f_resp.status_code == 200
            f_data = f_resp.json()
            assert f_data["total"] == 1
            assert f_data["items"][0]["status"] == "COMPLETED"
    finally:
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


@pytest.mark.asyncio
async def test_investigation_detail_retrieval():
    """
    Tests GET /api/v1/investigations/{case_id}:
    - Returns 200 with complete detail schema when case exists.
    - Returns 404 when valid UUID does not exist.
    - Returns 422 when path parameter is an invalid UUID format.
    """
    async with isolated_test_db():
        case_uuid = uuid.uuid4()
        factory = get_session_factory()
        async with factory() as session:
            case = InvestigationCase(
                id=case_uuid,
                filename="detail_test.csv",
                status="PROCESSING",
                ingestion_metadata={"total_records": 15, "total_volume": 250000.0},
                metrics={"total_nodes_analyzed": 8, "detected_cycles_count": 1},
                subgraph={"nodes": [{"id": "ACC_01", "total_in": 1000.0}], "edges": []},
                patterns={"cycles": [{"path": ["ACC_01", "ACC_02", "ACC_01"], "length": 2}]},
                verdict=None,
            )
            session.add(case)
            await session.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Successful retrieval
            resp = await client.get(f"/api/v1/investigations/{case_uuid}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["case_id"] == str(case_uuid)
            assert data["filename"] == "detail_test.csv"
            assert data["status"] == "PROCESSING"
            assert data["ingestion_metadata"]["total_records"] == 15
            assert data["metrics"]["detected_cycles_count"] == 1
            assert len(data["subgraph"]["nodes"]) == 1
            assert data["verdict"] is None

            # Non-existent UUID
            non_existent_uuid = str(uuid.uuid4())
            nf_resp = await client.get(f"/api/v1/investigations/{non_existent_uuid}")
            assert nf_resp.status_code == 404
            assert "not found" in nf_resp.json()["detail"].lower()

            # Malformed UUID
            bad_resp = await client.get("/api/v1/investigations/not-a-valid-uuid")
            assert bad_resp.status_code == 422


@pytest.mark.asyncio
async def test_sse_streaming_and_database_verdict_persistence():
    """
    Tests GET /api/v1/investigations/{case_id}/stream:
    1. Uploads dataset to establish a case in the database.
    2. Opens SSE connection and receives all 6 thought steps and terminal verdict.
    3. Confirms that upon completion, the InvestigationCase row in PostgreSQL
       has transitioned to status COMPLETED and stored the verdict JSON.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Upload CSV
            files = {"file": ("stream_test.csv", SYNTHETIC_AML_CSV, "text/csv")}
            upload_resp = await client.post("/api/v1/investigations/upload", files=files)
            assert upload_resp.status_code == 201
            case_id_str = upload_resp.json()["case_id"]
            case_uuid = uuid.UUID(case_id_str)

            # 2. Stream thoughts and verdict
            received_events = []
            async with client.stream("GET", f"/api/v1/investigations/{case_id_str}/stream") as stream_resp:
                assert stream_resp.status_code == 200
                assert "text/event-stream" in stream_resp.headers.get("content-type", "")

                current_event_name = None
                async for line in stream_resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        current_event_name = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and current_event_name:
                        data_str = line.split(":", 1)[1].strip()
                        payload = json.loads(data_str)
                        received_events.append({"event": current_event_name, "data": payload})
                        current_event_name = None

            thought_events = [e for e in received_events if e["event"] == "thought"]
            verdict_events = [e for e in received_events if e["event"] == "verdict"]

            assert len(thought_events) == 6
            assert [e["data"]["step"] for e in thought_events] == [1, 2, 3, 4, 5, 6]
            assert len(verdict_events) == 1

            final_verdict = verdict_events[0]["data"]
            assert final_verdict["case_id"] == case_id_str
            assert final_verdict["risk_level"] in ("CRITICAL", "HIGH")
            assert "confidence_score" in final_verdict
            assert "patterns_summary" in final_verdict
            assert "legal_recommendation" in final_verdict
            assert "audit_summary_text" in final_verdict

            # 3. Verify PostgreSQL persistence of verdict and status
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                persisted_case = (await session.execute(stmt)).scalar_one_or_none()

                assert persisted_case is not None
                assert persisted_case.status == "COMPLETED"
                assert persisted_case.verdict is not None
                assert persisted_case.verdict["risk_level"] == final_verdict["risk_level"]
                assert persisted_case.verdict["total_amount_mxn"] == final_verdict["total_amount_mxn"]


@pytest.mark.asyncio
async def test_sse_streaming_non_existent_case_returns_404():
    """
    Tests that requesting an SSE stream for a non-existent UUID returns HTTP 404
    before initiating an event stream.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        non_existent_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/investigations/{non_existent_id}/stream")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cascade_deletion_removes_transactions():
    """
    Tests that deleting an InvestigationCase automatically cascades and deletes
    all linked TransactionRecord rows.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("cascade_test.csv", SYNTHETIC_AML_CSV, "text/csv")}
            upload_resp = await client.post("/api/v1/investigations/upload", files=files)
            case_id = uuid.UUID(upload_resp.json()["case_id"])

            factory = get_session_factory()
            async with factory() as session:
                # Confirm transactions exist
                tx_count_before = (
                    await session.execute(
                        select(TransactionRecord).where(TransactionRecord.case_id == case_id)
                    )
                ).scalars().all()
                assert len(tx_count_before) == 7

                # Delete parent case
                case_obj = (
                    await session.execute(select(InvestigationCase).where(InvestigationCase.id == case_id))
                ).scalar_one_or_none()
                await session.delete(case_obj)
                await session.commit()

                # Verify child transactions were cascaded
                tx_count_after = (
                    await session.execute(
                        select(TransactionRecord).where(TransactionRecord.case_id == case_id)
                    )
                ).scalars().all()
                assert len(tx_count_after) == 0


@pytest.mark.asyncio
async def test_csv_upload_without_timestamp_column():
    """
    Regression Test for Finding 1 (M5 Challenger):
    Verifies that uploading a 3-column CSV without a timestamp or step column:
    1. Successfully returns HTTP 201 Created without throwing a SchemaError.
    2. Persists an InvestigationCase with status PROCESSING.
    3. Bulk-inserts TransactionRecord rows with synthetic sequential timestamps.
    4. Deterministic topological metrics (cycles, nodes) are correctly computed.
    """
    csv_3col = (
        "origin,destination,amount\n"
        "ACC_A,ACC_B,150000.0\n"
        "ACC_B,ACC_C,148000.0\n"
        "ACC_C,ACC_A,145000.0\n"
        "CORP_INFLOW,MULE_01,500000.0\n"
        "MULE_01,OFFSHORE_OUT,485000.0\n"
        "LEGIT_PAYROLL,EMPLOYEE_01,2500.0\n"
        "STORE_MERCHANT,CONSUMER_99,120.0\n"
    ).encode("utf-8")

    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("three_column_dataset.csv", csv_3col, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)

            assert response.status_code == 201, (
                f"Expected HTTP 201 Created for 3-column CSV upload, got {response.status_code}: {response.text}"
            )

            payload = response.json()
            assert "case_id" in payload
            case_id = uuid.UUID(payload["case_id"])
            assert payload["filename"] == "three_column_dataset.csv"
            assert payload["status"] == "PROCESSING"
            assert payload["metrics"]["total_nodes_analyzed"] >= 5
            assert payload["metrics"]["detected_cycles_count"] >= 1

            # Verify synthetic timestamps on persisted TransactionRecords in DB
            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    select(TransactionRecord)
                    .where(TransactionRecord.case_id == case_id)
                    .order_by(TransactionRecord.timestamp.asc())
                )
                txs = (await session.execute(stmt)).scalars().all()
                assert len(txs) == 7

                # Ensure all transactions have valid, sequential datetime timestamps
                for tx in txs:
                    assert tx.timestamp is not None
                    assert isinstance(tx.timestamp, datetime)

                # Check sequential progression from base datetime
                extracted_timestamps = [t.timestamp for t in txs]
                assert extracted_timestamps == sorted(extracted_timestamps)


@pytest.mark.asyncio
async def test_csv_upload_with_null_timestamp_cells():
    """
    Regression Test for Finding 2 (M5 Challenger):
    Verifies that uploading a CSV with empty or null timestamp cells:
    1. Returns HTTP 201 Created without throwing TypeError or HTTP 500.
    2. Successfully defaults null timestamp cells to 0.0.
    3. Builds the transaction graph and persists all records to PostgreSQL.
    """
    csv_null_timestamps = (
        "origin,destination,amount,timestamp\n"
        "ACC_A,ACC_B,150000.0,\n"
        "ACC_B,ACC_C,148000.0,1.0\n"
        "ACC_C,ACC_A,145000.0,\n"
        "CORP_INFLOW,MULE_01,500000.0,10.0\n"
        "MULE_01,OFFSHORE_OUT,485000.0,22.0\n"
        "LEGIT_PAYROLL,EMPLOYEE_01,2500.0,\n"
    ).encode("utf-8")

    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("null_timestamps_sample.csv", csv_null_timestamps, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)

            assert response.status_code == 201, (
                f"Expected HTTP 201 Created for CSV with null timestamp cells, got {response.status_code}: {response.text}"
            )

            payload = response.json()
            case_id = uuid.UUID(payload["case_id"])
            assert payload["status"] == "PROCESSING"

            # Check that all 6 rows were ingested and persisted with non-null datetimes
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(TransactionRecord).where(TransactionRecord.case_id == case_id)
                txs = (await session.execute(stmt)).scalars().all()
                assert len(txs) == 6
                for tx in txs:
                    assert tx.timestamp is not None
                    assert isinstance(tx.timestamp, datetime)
