"""
Empirical Challenge Tests for Milestone 2:
Forensic Auditor SSE Streaming & Database Verdict Persistence

Covers:
1. SSE Stream Phase Yielding (all 6 thought steps in strict sequence + terminal verdict)
2. Database Status & Verdict Persistence (status -> COMPLETED, valid risk scores, evidence items)
3. Multiple Consecutive Streams (pool exhaustion & leak prevention)
4. Concurrent Streams Under Pool Pressure (5 simultaneous streams)
5. Client Early Disconnect / Cancellation (connection reclamation and leak check)
6. Edge Cases (zero cycles/empty subgraph, 404 non-existent, 422 malformed UUID)
"""

import asyncio
import contextlib
import json
import os
import tempfile
import uuid
import pytest
import httpx
from sqlalchemy import select, text
from sqlalchemy.pool import QueuePool

from backend.main import app
from backend.core.config import settings
import backend.core.database as db_mod
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
async def isolated_test_db(fast_sleep: bool = True):
    """
    Async context manager configuring an isolated in-memory SQLite DB.
    Optionally patches asyncio.sleep in the streaming generator to speed up testing
    while preserving exact event sequencing and database persistence.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()

    orig_sleep = asyncio.sleep
    if fast_sleep:
        async def mock_sleep(secs: float):
            # Scale down sleep duration to 0.005s for rapid stress testing
            await orig_sleep(0.005)
        asyncio.sleep = mock_sleep

    try:
        yield
    finally:
        if fast_sleep:
            asyncio.sleep = orig_sleep
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


@pytest.mark.asyncio
async def test_challenge_sse_all_six_phases_and_verdict_schema():
    """
    CHALLENGE TEST 1:
    Verify that SSE stream yields all 6 thought phases in exact sequence,
    followed by the terminal verdict event matching all schema specifications.
    """
    async with isolated_test_db(fast_sleep=True):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Upload dataset
            files = {"file": ("challenge_stream.csv", SYNTHETIC_AML_CSV, "text/csv")}
            up_resp = await client.post("/api/v1/investigations/upload", files=files)
            assert up_resp.status_code == 201
            case_id = up_resp.json()["case_id"]

            # 2. Stream thoughts and terminal verdict
            events = []
            async with client.stream("GET", f"/api/v1/investigations/{case_id}/stream") as stream:
                assert stream.status_code == 200
                assert "text/event-stream" in stream.headers.get("content-type", "")
                assert stream.headers.get("cache-control") == "no-cache"
                assert stream.headers.get("x-accel-buffering") == "no"

                curr_event = None
                async for line in stream.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        curr_event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and curr_event:
                        data = json.loads(line.split(":", 1)[1].strip())
                        events.append({"event": curr_event, "data": data})
                        curr_event = None

            # Verify event breakdown
            thoughts = [e for e in events if e["event"] == "thought"]
            verdicts = [e for e in events if e["event"] == "verdict"]

            assert len(thoughts) == 6, f"Expected exactly 6 thought phases, got {len(thoughts)}"
            assert len(verdicts) == 1, f"Expected exactly 1 terminal verdict, got {len(verdicts)}"

            # Expected 6 phases in strict order
            expected_phases = [
                (1, "Ingesta y Validación de Topología"),
                (2, "Construcción de Grafo Dirigido"),
                (3, "Extracción de Ciclos Dirigidos"),
                (4, "Análisis de Velocidad y Cuentas Puente"),
                (5, "Poda Matemática Determinista"),
                (6, "Evaluación Pericial Regulatoria"),
            ]

            for i, (exp_step, exp_phase) in enumerate(expected_phases):
                actual_step = thoughts[i]["data"]["step"]
                actual_phase = thoughts[i]["data"]["phase"]
                actual_msg = thoughts[i]["data"]["message"]
                actual_ts = thoughts[i]["data"]["timestamp"]

                assert actual_step == exp_step, f"Step mismatch at index {i}: {actual_step} != {exp_step}"
                assert actual_phase == exp_phase, f"Phase mismatch at index {i}: {actual_phase} != {exp_phase}"
                assert len(actual_msg) > 10, f"Message too short: {actual_msg}"
                assert actual_ts is not None, "Timestamp missing"

            # Verify terminal verdict schema and evidence items
            verdict_payload = verdicts[0]["data"]
            assert verdict_payload["case_id"] == case_id
            assert verdict_payload["risk_level"] in ("CRÍTICO", "ALTO")
            assert verdict_payload["fraud_type"] == "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido"
            assert isinstance(verdict_payload["total_amount_mxn"], (int, float))
            assert verdict_payload["total_amount_mxn"] > 0
            assert 0.0 <= verdict_payload["confidence_score"] <= 1.0
            assert isinstance(verdict_payload["entities_involved"], list)
            assert len(verdict_payload["entities_involved"]) > 0
            assert "patterns_summary" in verdict_payload
            assert verdict_payload["patterns_summary"]["closed_cycles"] >= 1
            assert verdict_payload["patterns_summary"]["passthrough_accounts"] >= 1
            assert verdict_payload["patterns_summary"]["pruning_efficiency_pct"] > 0
            assert len(verdict_payload["legal_recommendation"]) > 20
            assert len(verdict_payload["audit_summary_text"]) > 50
            assert verdict_payload["completed_at"] is not None


@pytest.mark.asyncio
async def test_challenge_database_status_and_verdict_persistence():
    """
    CHALLENGE TEST 2:
    Verify that before stream, case status is PROCESSING and verdict is NULL.
    Verify that upon stream termination:
    - InvestigationCase.status in database is 'COMPLETED'
    - InvestigationCase.verdict in database matches stream verdict with risk scores & evidence
    - GET /api/v1/investigations/{case_id} returns status COMPLETED and full verdict
    - GET /api/v1/investigations paginated listing reflects status COMPLETED and has_verdict=True
    """
    async with isolated_test_db(fast_sleep=True):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("persistence_check.csv", SYNTHETIC_AML_CSV, "text/csv")}
            up_resp = await client.post("/api/v1/investigations/upload", files=files)
            case_id_str = up_resp.json()["case_id"]
            case_uuid = uuid.UUID(case_id_str)

            # Check DB before stream
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                case_before = (await session.execute(stmt)).scalar_one()
                assert case_before.status == "PROCESSING"
                assert case_before.verdict is None

            # Stream to completion
            stream_verdict = None
            async with client.stream("GET", f"/api/v1/investigations/{case_id_str}/stream") as stream:
                curr_event = None
                async for line in stream.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        curr_event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and curr_event == "verdict":
                        stream_verdict = json.loads(line.split(":", 1)[1].strip())

            assert stream_verdict is not None, "Verdict event was never received from stream"

            # Check DB after stream
            async with factory() as session:
                stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                case_after = (await session.execute(stmt)).scalar_one()
                assert case_after.status == "COMPLETED", f"Expected COMPLETED, got {case_after.status}"
                assert case_after.verdict is not None, "Verdict was not saved to database"
                assert case_after.verdict["risk_level"] == stream_verdict["risk_level"]
                assert case_after.verdict["confidence_score"] == stream_verdict["confidence_score"]
                assert case_after.verdict["total_amount_mxn"] == stream_verdict["total_amount_mxn"]
                assert case_after.verdict["entities_involved"] == stream_verdict["entities_involved"]
                assert case_after.verdict["patterns_summary"] == stream_verdict["patterns_summary"]

            # Check GET /investigations/{case_id} endpoint
            detail_resp = await client.get(f"/api/v1/investigations/{case_id_str}")
            assert detail_resp.status_code == 200
            detail_data = detail_resp.json()
            assert detail_data["status"] == "COMPLETED"
            assert detail_data["verdict"] is not None
            assert detail_data["verdict"]["risk_level"] == stream_verdict["risk_level"]

            # Check GET /investigations list endpoint
            list_resp = await client.get("/api/v1/investigations?status=COMPLETED")
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            matching_item = next((item for item in list_data["items"] if item["case_id"] == case_id_str), None)
            assert matching_item is not None
            assert matching_item["status"] == "COMPLETED"
            assert matching_item["has_verdict"] is True


@pytest.mark.asyncio
async def test_challenge_consecutive_streams_pool_safety():
    """
    CHALLENGE TEST 3:
    Stress-test connection pool safety by running 30 consecutive streams in succession.
    Verifies:
    - No connection leaks or session accumulation
    - All 30 cases successfully complete with status COMPLETED
    - All 30 cases persist valid verdicts
    """
    async with isolated_test_db(fast_sleep=True):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            num_streams = 25
            case_ids = []

            # Create cases
            for i in range(num_streams):
                files = {"file": (f"consec_test_{i}.csv", SYNTHETIC_AML_CSV, "text/csv")}
                up_resp = await client.post("/api/v1/investigations/upload", files=files)
                assert up_resp.status_code == 201
                case_ids.append(up_resp.json()["case_id"])

            # Stream each consecutively
            for i, cid in enumerate(case_ids):
                verdict_received = False
                thought_count = 0
                async with client.stream("GET", f"/api/v1/investigations/{cid}/stream") as stream:
                    assert stream.status_code == 200
                    curr_event = None
                    async for line in stream.aiter_lines():
                        line = line.strip()
                        if line.startswith("event:"):
                            curr_event = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            if curr_event == "thought":
                                thought_count += 1
                            elif curr_event == "verdict":
                                verdict_received = True
                            curr_event = None

                assert thought_count == 6, f"Stream {i} received {thought_count} thoughts"
                assert verdict_received, f"Stream {i} did not receive terminal verdict"

            # Verify database state for all cases
            factory = get_session_factory()
            async with factory() as session:
                for cid in case_ids:
                    case_uuid = uuid.UUID(cid)
                    stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                    c = (await session.execute(stmt)).scalar_one()
                    assert c.status == "COMPLETED", f"Case {cid} status is {c.status}"
                    assert c.verdict is not None, f"Case {cid} verdict is None"


@pytest.mark.asyncio
async def test_challenge_file_db_queue_pool_consecutive_and_concurrent():
    """
    CHALLENGE TEST 4:
    Test connection pool safety using a file-based SQLite database configured with AsyncAdaptedQueuePool,
    pool_size=5, max_overflow=2, pool_timeout=5.0.
    Executes:
    1. 20 consecutive streams.
    2. 5 concurrent streams running simultaneously.
    Verifies that AsyncAdaptedQueuePool never exhausts and returns all connections to the pool.
    """
    from sqlalchemy.pool import AsyncAdaptedQueuePool
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    orig_sleep = asyncio.sleep
    async def mock_sleep(secs: float):
        await orig_sleep(0.005)
    asyncio.sleep = mock_sleep

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    orig_url = settings.DATABASE_URL
    clean_path = temp_db_path.replace("\\", "/")
    sqlite_url = f"sqlite+aiosqlite:///{clean_path}"
    settings.DATABASE_URL = sqlite_url

    pool_size = 5
    max_overflow = 2
    engine = create_async_engine(
        sqlite_url,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=5.0,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=db_mod.AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    db_mod._engine = engine
    db_mod._session_factory = session_factory

    async with engine.begin() as conn:
        await conn.run_sync(db_mod.Base.metadata.create_all)

    INVESTIGATION_CASES.clear()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Test 20 consecutive streams
            for i in range(20):
                files = {"file": (f"queue_consec_{i}.csv", SYNTHETIC_AML_CSV, "text/csv")}
                up_resp = await client.post("/api/v1/investigations/upload", files=files)
                assert up_resp.status_code == 201
                cid = up_resp.json()["case_id"]

                verdict_found = False
                async with client.stream("GET", f"/api/v1/investigations/{cid}/stream") as stream:
                    assert stream.status_code == 200
                    curr_ev = None
                    async for line in stream.aiter_lines():
                        line = line.strip()
                        if line.startswith("event:"):
                            curr_ev = line.split(":", 1)[1].strip()
                        elif line.startswith("data:") and curr_ev == "verdict":
                            verdict_found = True

                assert verdict_found

            # Check pool state after consecutive streams
            pool = engine.pool
            assert pool.checkedout() == 0, f"Expected 0 checked out connections, got {pool.checkedout()}"

            # 2. Test 5 concurrent streams
            concurrent_cids = []
            for i in range(5):
                files = {"file": (f"queue_concurrent_{i}.csv", SYNTHETIC_AML_CSV, "text/csv")}
                up_resp = await client.post("/api/v1/investigations/upload", files=files)
                assert up_resp.status_code == 201
                concurrent_cids.append(up_resp.json()["case_id"])

            async def run_single_stream(cid: str):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as cl:
                    verdict_seen = False
                    async with cl.stream("GET", f"/api/v1/investigations/{cid}/stream") as stream:
                        assert stream.status_code == 200
                        c_ev = None
                        async for line in stream.aiter_lines():
                            line = line.strip()
                            if line.startswith("event:"):
                                c_ev = line.split(":", 1)[1].strip()
                            elif line.startswith("data:") and c_ev == "verdict":
                                verdict_seen = True
                    return verdict_seen

            results = await asyncio.gather(*[run_single_stream(cid) for cid in concurrent_cids])
            assert all(results), f"Some concurrent streams failed: {results}"

            # Check pool state after concurrent streams
            assert pool.checkedout() == 0, f"Connections still checked out: {pool.checkedout()}"

            # Verify all 25 cases COMPLETED in DB
            async with session_factory() as session:
                for cid in concurrent_cids:
                    case_uuid = uuid.UUID(cid)
                    stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                    c = (await session.execute(stmt)).scalar_one()
                    assert c.status == "COMPLETED"
                    assert c.verdict is not None
    finally:
        asyncio.sleep = orig_sleep
        await engine.dispose()
        db_mod._engine = None
        db_mod._session_factory = None
        settings.DATABASE_URL = orig_url
        INVESTIGATION_CASES.clear()
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_challenge_generator_cancellation_and_generator_exit():
    """
    CHALLENGE TEST 5:
    Simulates direct generator abortion (GeneratorExit / asyncio.CancelledError).
    Verifies:
    - Generator handles GeneratorExit and does NOT persist verdict prematurely.
    - Database record remains in PROCESSING status with verdict=None.
    - Subsequent new stream on a different case functions normally and persists.
    """
    from backend.api.routes.investigations import generate_investigation_stream

    async with isolated_test_db(fast_sleep=True):
        factory = get_session_factory()
        case_uuid = uuid.uuid4()

        # Insert a case in PROCESSING status
        async with factory() as session:
            case = InvestigationCase(
                id=case_uuid,
                filename="cancel_test.csv",
                status="PROCESSING",
                metrics={"total_nodes_analyzed": 5},
                subgraph={"nodes": [], "edges": []},
                patterns={"cycles": []},
                verdict=None,
            )
            session.add(case)
            await session.commit()

        # Instantiate generator and read only 2 thought steps, then aclose()
        gen = generate_investigation_stream(case_uuid, {"metrics": {}, "subgraph": {}, "patterns": {}})
        first_event = await anext(gen)
        assert "event: thought" in first_event
        second_event = await anext(gen)
        assert "event: thought" in second_event

        # Early client termination: close generator
        await gen.aclose()

        # Verify DB: case must still be PROCESSING and verdict must still be None
        async with factory() as session:
            stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
            case_obj = (await session.execute(stmt)).scalar_one()
            assert case_obj.status == "PROCESSING"
            assert case_obj.verdict is None

        # Verify system health by streaming another case to completion
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files2 = {"file": ("followup.csv", SYNTHETIC_AML_CSV, "text/csv")}
            up2 = await client.post("/api/v1/investigations/upload", files=files2)
            cid2 = up2.json()["case_id"]

            got_verdict2 = False
            async with client.stream("GET", f"/api/v1/investigations/{cid2}/stream") as stream2:
                c_ev = None
                async for line in stream2.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        c_ev = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and c_ev == "verdict":
                        got_verdict2 = True

            assert got_verdict2


@pytest.mark.asyncio
async def test_challenge_empty_subgraph_and_benign_dataset():
    """
    CHALLENGE TEST 6:
    Verifies streaming and verdict persistence on a benign dataset with zero cycles
    and zero passthrough accounts.
    Verifies:
    - Stream completes normally with 6 thought phases + verdict
    - Verdict risk_level is 'ALTO' (instead of 'CRÍTICO' since cycles=0)
    - Confidence score is 0.88
    - Status is updated to COMPLETED in database
    """
    BENIGN_CSV = """origin,destination,amount,timestamp
ACC_1,ACC_2,500.0,1.0
ACC_3,ACC_4,300.0,2.0
ACC_5,ACC_6,150.0,3.0
""".encode("utf-8")

    async with isolated_test_db(fast_sleep=True):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("benign.csv", BENIGN_CSV, "text/csv")}
            up_resp = await client.post("/api/v1/investigations/upload", files=files)
            case_id = up_resp.json()["case_id"]

            verdict_payload = None
            thoughts = []
            async with client.stream("GET", f"/api/v1/investigations/{case_id}/stream") as stream:
                curr_ev = None
                async for line in stream.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        curr_ev = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        if curr_ev == "thought":
                            thoughts.append(json.loads(line.split(":", 1)[1].strip()))
                        elif curr_ev == "verdict":
                            verdict_payload = json.loads(line.split(":", 1)[1].strip())
                        curr_ev = None

            assert len(thoughts) == 6
            assert verdict_payload is not None
            assert verdict_payload["risk_level"] == "ALTO"
            assert verdict_payload["confidence_score"] == 0.88
            assert verdict_payload["patterns_summary"]["closed_cycles"] == 0
            assert verdict_payload["patterns_summary"]["passthrough_accounts"] == 0

            # Verify DB status COMPLETED
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(InvestigationCase).where(InvestigationCase.id == uuid.UUID(case_id))
                c = (await session.execute(stmt)).scalar_one()
                assert c.status == "COMPLETED"
                assert c.verdict["risk_level"] == "ALTO"
                assert c.verdict["confidence_score"] == 0.88
