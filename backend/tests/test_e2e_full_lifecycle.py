"""
End-to-End Full Lifecycle Integration Test Suite (Milestone 5)
for the Forensic Auditor Python Backend Platform.

Executes a complete, unified 10-step end-to-end integration test:
- Step 1: Health check `GET /health` -> 200 OK.
- Step 2: Ingest CSV `POST /api/v1/investigations/upload` -> 201 Created with valid case_id.
- Step 3: Direct DB assertion -> verify InvestigationCase and TransactionRecord rows are persisted.
- Step 4: Paginated list `GET /api/v1/investigations` -> verify case is listed with PROCESSING status.
- Step 5: Detail retrieval `GET /api/v1/investigations/{case_id}` -> verify full subgraph and topological metrics.
- Step 6: Dedicated tool queries:
  - POST /api/v1/tools/transactions with amount and suspicion filters.
  - POST /api/v1/tools/entities profiling nodes.
  - POST /api/v1/tools/patterns retrieving cycles and mules.
  - POST /api/v1/tools/legal-precedents with semantic query text matching CFF 69-B / Mexican AML statutes.
- Step 7: Dynamic query builder:
  - POST /api/v1/tools/query with target transactions and composable filters.
- Step 8: Stream execution `GET /api/v1/investigations/{case_id}/stream` -> receive SSE thoughts and terminal verdict.
- Step 9: Post-stream DB assertion -> verify case status is COMPLETED and verdict is persisted.
- Step 10: TTS synthesis `POST /api/v1/tts/synthesize` -> verify audio stream or synthetic fallback.

Also covers edge cases:
- Dynamic query security whitelisting rejection (SQL injection immunity).
- Dynamic query multi-target profiling (entities and patterns).
- Cascade deletion verification in database.
- Complete lifecycle in offline in-memory fallback mode.
"""

import contextlib
from decimal import Decimal
import json
from typing import Any, Dict, List
import uuid
import httpx
import pytest
from sqlalchemy import func, select

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.main import app
from backend.models.forensic import (
    InvestigationCase,
    LegalArticleVector,
    TransactionRecord,
    seed_legal_knowledge,
)
from backend.schemas.agent_tools import (
    FilterOperator,
    PatternType,
    SortOrder,
    TargetEntity,
)

# Rich synthetic dataset with:
# 1. Directed 3-node cycle: ACC_CYCLE_A -> ACC_CYCLE_B -> ACC_CYCLE_C -> ACC_CYCLE_A
# 2. Passthrough mule account: CORP_ORIGIN -> MULE_ACCOUNT -> OFFSHORE_SHELL (ratio 0.97, delta 12h)
# 3. Benign noise to be pruned: LEGIT_PAYROLL -> EMP_01, LEGIT_STORE -> CONSUMER_01
SYNTHETIC_FORENSIC_E2E_CSV = """origin,destination,amount,timestamp
ACC_CYCLE_A,ACC_CYCLE_B,150000.0,1.0
ACC_CYCLE_B,ACC_CYCLE_C,148000.0,2.0
ACC_CYCLE_C,ACC_CYCLE_A,145000.0,3.0
CORP_ORIGIN,MULE_ACCOUNT,500000.0,10.0
MULE_ACCOUNT,OFFSHORE_SHELL,485000.0,22.0
LEGIT_PAYROLL,EMP_01,2500.0,4.0
LEGIT_STORE,CONSUMER_01,120.0,5.0
""".encode("utf-8")


@contextlib.asynccontextmanager
async def isolated_e2e_db():
    """
    Sets up an isolated in-memory SQLite database environment, initializes
    the schema and seed Mexican AML jurisprudence, resets caches, and cleans
    up upon exit.
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()

    # Ensure legal precedents knowledge base is populated
    factory = get_session_factory()
    async with factory() as session:
        await seed_legal_knowledge(session)

    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


# =============================================================================
# Primary Unified 10-Step End-to-End Forensic Lifecycle Test
# =============================================================================

@pytest.mark.asyncio
async def test_e2e_full_10_step_lifecycle():
    """
    Executes the complete unified 10-step lifecycle from health check, ingestion,
    database persistence, case management, dedicated tools, dynamic query builder,
    SSE streaming, verdict persistence, to speech synthesis.
    """
    async with isolated_e2e_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

            # -----------------------------------------------------------------
            # Step 1: Health check GET /health -> 200 OK
            # -----------------------------------------------------------------
            health_res = await client.get("/health")
            assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
            health_json = health_res.json()
            assert health_json.get("status") == "healthy"
            assert "environment" in health_json or "version" in health_json or "service" in health_json

            # -----------------------------------------------------------------
            # Step 2: Ingest CSV POST /api/v1/investigations/upload -> 201 Created
            # -----------------------------------------------------------------
            files = {
                "file": ("forensic_case_e2e.csv", SYNTHETIC_FORENSIC_E2E_CSV, "text/csv")
            }
            upload_res = await client.post("/api/v1/investigations/upload", files=files)
            assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
            upload_data = upload_res.json()

            assert "case_id" in upload_data, "Missing case_id in upload response"
            case_id_str = upload_data["case_id"]
            case_uuid = uuid.UUID(case_id_str)

            assert upload_data["filename"] == "forensic_case_e2e.csv"
            assert upload_data["status"] == "PROCESSING"

            # Verify deterministic topological pruning & extraction metrics
            metrics = upload_data["metrics"]
            assert metrics["total_nodes_analyzed"] >= 6
            assert metrics["total_edges_analyzed"] == 7
            assert metrics["detected_cycles_count"] >= 1
            assert metrics["passthrough_accounts_count"] >= 1
            assert metrics["pruned_edges_count"] >= 2  # Payroll and store pruned
            assert metrics["pruning_efficiency_pct"] > 0.0
            assert metrics["suspicious_volume_mxn"] > 1400000.0

            # Verify subgraph structure
            subgraph = upload_data["subgraph"]
            assert len(subgraph["nodes"]) >= 3
            assert len(subgraph["edges"]) >= 3
            assert any("CIRCULAR_FLOW_CYCLE" in n.get("reasons", []) for n in subgraph["nodes"])

            # Verify pattern catalog
            patterns = upload_data["patterns"]
            assert len(patterns.get("cycles", [])) >= 1
            assert len(patterns.get("passthrough_accounts", [])) >= 1

            # -----------------------------------------------------------------
            # Step 3: Direct DB assertion -> InvestigationCase & TransactionRecords
            # -----------------------------------------------------------------
            factory = get_session_factory()
            async with factory() as session:
                # Assert InvestigationCase row in SQLite
                case_stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                case_row = (await session.execute(case_stmt)).scalar_one_or_none()

                assert case_row is not None, "InvestigationCase record not found in database"
                assert case_row.id == case_uuid
                assert case_row.filename == "forensic_case_e2e.csv"
                assert case_row.status == "PROCESSING"
                assert case_row.verdict is None, "Verdict must be None prior to SSE stream completion"
                assert case_row.metrics["detected_cycles_count"] >= 1
                assert case_row.ingestion_metadata["total_records"] == 7

                # Assert TransactionRecord bulk rows
                tx_stmt = (
                    select(TransactionRecord)
                    .where(TransactionRecord.case_id == case_uuid)
                    .order_by(TransactionRecord.amount.desc())
                )
                tx_rows = (await session.execute(tx_stmt)).scalars().all()
                assert len(tx_rows) == 7, f"Expected 7 persisted transactions, found {len(tx_rows)}"

                # Verify amounts and flags
                suspicious_txs = [t for t in tx_rows if t.is_suspicious]
                benign_txs = [t for t in tx_rows if not t.is_suspicious]
                assert len(suspicious_txs) >= 4, "Expected at least 4 suspicious transactions (cycle + mule)"
                assert len(benign_txs) >= 2, "Expected at least 2 benign pruned transactions"

                # Check cycle transactions
                cycle_tx = next((t for t in tx_rows if t.origin == "ACC_CYCLE_A" and t.destination == "ACC_CYCLE_B"), None)
                assert cycle_tx is not None
                assert cycle_tx.is_suspicious is True
                assert cycle_tx.amount == Decimal("150000.00")
                assert any("CYCLE" in r for r in cycle_tx.reasons)

                # Check mule transaction
                mule_tx = next((t for t in tx_rows if t.origin == "MULE_ACCOUNT" and t.destination == "OFFSHORE_SHELL"), None)
                assert mule_tx is not None
                assert mule_tx.is_suspicious is True
                assert mule_tx.amount == Decimal("485000.00")

                # Check benign payroll
                payroll_tx = next((t for t in tx_rows if t.origin == "LEGIT_PAYROLL"), None)
                assert payroll_tx is not None
                assert payroll_tx.is_suspicious is False
                assert payroll_tx.reasons == []

            # -----------------------------------------------------------------
            # Step 4: Paginated list GET /api/v1/investigations -> verify case listed
            # -----------------------------------------------------------------
            list_res = await client.get("/api/v1/investigations?page=1&page_size=10")
            assert list_res.status_code == 200, f"List investigations failed: {list_res.text}"
            list_data = list_res.json()

            assert list_data["total"] >= 1
            assert list_data["page"] == 1
            assert list_data["page_size"] == 10
            matching_case = next((c for c in list_data["items"] if str(c.get("case_id") or c.get("id")) == case_id_str), None)
            assert matching_case is not None, f"Case {case_id_str} not returned in paginated list"
            assert matching_case["filename"] == "forensic_case_e2e.csv"
            assert matching_case["status"] == "PROCESSING"
            if matching_case.get("metrics"):
                assert matching_case["metrics"]["total_nodes_analyzed"] >= 6
                assert matching_case["metrics"]["detected_cycles_count"] >= 1

            # Test status filter on list
            filtered_list_res = await client.get("/api/v1/investigations?status=PROCESSING")
            assert filtered_list_res.status_code == 200
            assert any(str(c.get("case_id") or c.get("id")) == case_id_str for c in filtered_list_res.json()["items"])

            # -----------------------------------------------------------------
            # Step 5: Detail retrieval GET /api/v1/investigations/{case_id}
            # -----------------------------------------------------------------
            detail_res = await client.get(f"/api/v1/investigations/{case_id_str}")
            assert detail_res.status_code == 200, f"Detail retrieval failed: {detail_res.text}"
            detail_data = detail_res.json()

            assert (detail_data.get("case_id") or detail_data.get("id")) == case_id_str
            assert detail_data["filename"] == "forensic_case_e2e.csv"
            assert detail_data["status"] == "PROCESSING"
            assert detail_data["verdict"] is None
            assert detail_data["metrics"]["detected_cycles_count"] >= 1
            assert detail_data["metrics"]["passthrough_accounts_count"] >= 1
            assert len(detail_data["subgraph"]["nodes"]) >= 3
            assert len(detail_data["subgraph"]["edges"]) >= 3
            assert len(detail_data["patterns"]["cycles"]) >= 1

            # -----------------------------------------------------------------
            # Step 6: Dedicated tool queries
            # -----------------------------------------------------------------
            # 6.1 POST /api/v1/tools/transactions with amount and suspicion filters
            tool_tx_res = await client.post(
                "/api/v1/tools/transactions",
                json={
                    "case_id": case_id_str,
                    "min_amount": 140000.0,
                    "is_suspicious": True,
                },
            )
            assert tool_tx_res.status_code == 200, f"Tool transactions failed: {tool_tx_res.text}"
            tool_tx_data = tool_tx_res.json()
            assert tool_tx_data["case_id"] == case_id_str
            assert tool_tx_data["total"] >= 4
            assert all(item["amount"] >= 140000.0 for item in tool_tx_data["items"])
            assert all(item["is_suspicious"] is True for item in tool_tx_data["items"])
            assert tool_tx_data["total_volume_mxn"] >= 1400000.0

            # 6.2 POST /api/v1/tools/entities profiling nodes
            tool_ent_res = await client.post(
                "/api/v1/tools/entities",
                json={
                    "case_id": case_id_str,
                    "is_suspicious": True,
                },
            )
            assert tool_ent_res.status_code == 200, f"Tool entities failed: {tool_ent_res.text}"
            tool_ent_data = tool_ent_res.json()
            assert tool_ent_data["case_id"] == case_id_str
            assert tool_ent_data["total_entities"] >= 3
            assert len(tool_ent_data["entities"]) >= 3

            # Check individual entity attributes
            for entity in tool_ent_data["entities"]:
                assert "entity_id" in entity
                assert entity["in_degree"] >= 0
                assert entity["out_degree"] >= 0
                assert "net_flow" in entity
                assert entity["risk_score"] >= 0.0
                assert entity["is_suspicious"] is True

            # Query single specific entity
            mule_ent_res = await client.post(
                "/api/v1/tools/entities",
                json={
                    "case_id": case_id_str,
                    "entity_id": "MULE_ACCOUNT",
                },
            )
            assert mule_ent_res.status_code == 200
            mule_ent_data = mule_ent_res.json()
            assert mule_ent_data["total_entities"] == 1
            assert mule_ent_data["entities"][0]["entity_id"] == "MULE_ACCOUNT"
            assert mule_ent_data["entities"][0]["total_inflow"] == 500000.0
            assert mule_ent_data["entities"][0]["total_outflow"] == 485000.0
            assert mule_ent_data["entities"][0]["net_flow"] == 15000.0

            # 6.3 POST /api/v1/tools/patterns retrieving cycles and mules
            tool_pat_res = await client.post(
                "/api/v1/tools/patterns",
                json={
                    "case_id": case_id_str,
                    "pattern_type": PatternType.ALL.value,
                },
            )
            assert tool_pat_res.status_code == 200, f"Tool patterns failed: {tool_pat_res.text}"
            tool_pat_data = tool_pat_res.json()
            assert tool_pat_data["case_id"] == case_id_str
            assert tool_pat_data["total_cycles_count"] >= 1
            assert tool_pat_data["total_mules_count"] >= 1

            # Validate cycle structure
            cycle = tool_pat_data["cycles"][0]
            assert cycle["length"] >= 3
            assert any("ACC_CYCLE_A" in node for node in cycle["path"])
            assert cycle["estimated_volume"] > 0

            # Validate mule structure
            mule = next((m for m in tool_pat_data["passthrough_mules"] if m["account"] == "MULE_ACCOUNT"), None)
            assert mule is not None, f"MULE_ACCOUNT not found in {tool_pat_data['passthrough_mules']}"
            assert mule["ratio"] >= 0.90
            assert mule["time_delta_hours"] <= 48.0

            # 6.4 POST /api/v1/tools/legal-precedents with query text
            tool_legal_res = await client.post(
                "/api/v1/tools/legal-precedents",
                json={
                    "query_text": "operaciones simuladas facturacion de comprobantes fiscales inexistentes articulo 69-B CFF",
                    "top_k": 3,
                },
            )
            assert tool_legal_res.status_code == 200, f"Tool legal-precedents failed: {tool_legal_res.text}"
            tool_legal_data = tool_legal_res.json()
            assert tool_legal_data["total_matches"] >= 1
            assert len(tool_legal_data["results"]) >= 1
            top_precedent = tool_legal_data["results"][0]
            assert "69-B" in top_precedent["article_code"] or "CFF" in top_precedent["law_name"] or "Código Fiscal" in top_precedent["law_name"]
            assert top_precedent["similarity_score"] > 0.0

            # -----------------------------------------------------------------
            # Step 7: Dynamic query builder POST /api/v1/tools/query
            # -----------------------------------------------------------------
            dynamic_tx_res = await client.post(
                "/api/v1/tools/query",
                json={
                    "target": TargetEntity.TRANSACTIONS.value,
                    "case_id": case_id_str,
                    "filters": [
                        {"field": "amount", "operator": FilterOperator.GTE.value, "value": 145000.0},
                        {"field": "is_suspicious", "operator": FilterOperator.EQ.value, "value": True},
                    ],
                    "sort_by": "amount",
                    "sort_order": SortOrder.DESC.value,
                    "limit": 10,
                    "offset": 0,
                },
            )
            assert dynamic_tx_res.status_code == 200, f"Dynamic query failed: {dynamic_tx_res.text}"
            dynamic_data = dynamic_tx_res.json()
            assert dynamic_data["target"] == "transactions"
            assert dynamic_data["case_id"] == case_id_str
            assert dynamic_data["total"] >= 4
            assert len(dynamic_data["records"]) >= 4

            # Verify records meet filter conditions and sort order
            amounts = [float(r["amount"]) for r in dynamic_data["records"]]
            assert amounts == sorted(amounts, reverse=True), "Records not sorted descending by amount"
            assert all(a >= 145000.0 for a in amounts)
            assert all(r["is_suspicious"] is True for r in dynamic_data["records"])

            # -----------------------------------------------------------------
            # Step 8: Stream execution GET /api/v1/investigations/{case_id}/stream
            # -----------------------------------------------------------------
            received_events: List[Dict[str, Any]] = []
            async with client.stream("GET", f"/api/v1/investigations/{case_id_str}/stream") as stream_res:
                assert stream_res.status_code == 200
                assert "text/event-stream" in stream_res.headers["content-type"]

                current_event_name = None
                async for raw_line in stream_res.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        current_event_name = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and current_event_name:
                        data_content = line.split(":", 1)[1].strip()
                        payload = json.loads(data_content)
                        received_events.append({"event": current_event_name, "data": payload})
                        current_event_name = None

            thought_events = [e for e in received_events if e["event"] == "thought"]
            verdict_events = [e for e in received_events if e["event"] == "verdict"]

            assert len(thought_events) >= 5, f"Expected >= 5 thought steps, got {len(thought_events)}"
            assert len(verdict_events) == 1, f"Expected exactly 1 terminal verdict, got {len(verdict_events)}"

            terminal_verdict = verdict_events[0]["data"]
            assert terminal_verdict["case_id"] == case_id_str
            assert terminal_verdict["risk_level"] in ("CRÍTICO", "ALTO")
            assert "Estructuración" in terminal_verdict["fraud_type"] or "Lavado" in terminal_verdict["fraud_type"]
            assert terminal_verdict["total_amount_mxn"] > 1400000.0
            assert len(terminal_verdict["entities_involved"]) >= 3
            assert "legal_recommendation" in terminal_verdict
            assert len(terminal_verdict["legal_recommendation"]) > 10
            assert "audit_summary_text" in terminal_verdict
            audit_summary = terminal_verdict["audit_summary_text"]
            assert len(audit_summary) > 50

            # -----------------------------------------------------------------
            # Step 9: Post-stream DB assertion -> status COMPLETED & verdict persisted
            # -----------------------------------------------------------------
            async with factory() as post_session:
                post_stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                updated_case = (await post_session.execute(post_stmt)).scalar_one_or_none()

                assert updated_case is not None
                assert updated_case.status == "COMPLETED", (
                    f"Expected case status COMPLETED after SSE stream, got {updated_case.status}"
                )
                assert updated_case.verdict is not None, "Case verdict must not be None after SSE stream"
                assert updated_case.verdict["case_id"] == case_id_str
                assert updated_case.verdict["risk_level"] == terminal_verdict["risk_level"]
                assert updated_case.verdict["audit_summary_text"] == audit_summary
                assert updated_case.updated_at is not None

            # Verify GET /investigations/{case_id} reflects COMPLETED status
            completed_detail = (await client.get(f"/api/v1/investigations/{case_id_str}")).json()
            assert completed_detail["status"] == "COMPLETED"
            assert completed_detail["verdict"] is not None
            assert completed_detail["verdict"]["case_id"] == case_id_str

            # -----------------------------------------------------------------
            # Step 10: TTS synthesis POST /api/v1/tts/synthesize
            # -----------------------------------------------------------------
            tts_res = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": audit_summary},
            )
            assert tts_res.status_code == 200, f"TTS synthesis failed: {tts_res.text}"
            assert "audio/mpeg" in tts_res.headers.get("content-type", "")
            assert len(tts_res.content) > 0, "TTS audio response body must not be empty"

            # Check audio source header
            audio_source = tts_res.headers.get("X-Audio-Source")
            if audio_source:
                assert audio_source in ("synthetic-fallback-mode", "synthetic-fallback-frame", "elevenlabs-stream"), (
                    f"Unexpected X-Audio-Source header: {audio_source}"
                )
                # Validate synthetic silent MPEG frame sync word: 0xFF 0xFB (MPEG-1 Layer 3)
                assert tts_res.content[0] == 0xFF
                assert (tts_res.content[1] & 0xE0) == 0xE0


# =============================================================================
# Additional Hardened E2E Tests: Edge Cases, Security, & Resilience
# =============================================================================

@pytest.mark.asyncio
async def test_e2e_dynamic_query_security_whitelisting_rejection():
    """
    Verifies that the dynamic query builder strictly rejects un-whitelisted fields,
    malicious column names, and SQL injection probes with HTTP 422 Unprocessable Entity.
    """
    async with isolated_e2e_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Upload a case first
            files = {"file": ("test_sec.csv", SYNTHETIC_FORENSIC_E2E_CSV, "text/csv")}
            upload_res = await client.post("/api/v1/investigations/upload", files=files)
            case_id = upload_res.json()["case_id"]

            # Injection attempt 1: non-whitelisted column in filters
            bad_filter_res = await client.post(
                "/api/v1/tools/query",
                json={
                    "target": "transactions",
                    "case_id": case_id,
                    "filters": [
                        {"field": "password; DROP TABLE transactions; --", "operator": "eq", "value": "test"}
                    ],
                },
            )
            assert bad_filter_res.status_code == 422

            # Injection attempt 2: non-whitelisted column in sort_by
            bad_sort_res = await client.post(
                "/api/v1/tools/query",
                json={
                    "target": "transactions",
                    "case_id": case_id,
                    "sort_by": "secret_column_name",
                    "sort_order": "asc",
                },
            )
            assert bad_sort_res.status_code == 422

            # Missing mandatory case_id for case-scoped target
            missing_case_res = await client.post(
                "/api/v1/tools/query",
                json={
                    "target": "transactions",
                    "filters": [{"field": "amount", "operator": "gt", "value": 100.0}],
                },
            )
            assert missing_case_res.status_code == 422


@pytest.mark.asyncio
async def test_e2e_cascade_deletion_verification():
    """
    Verifies database relational integrity: deleting an InvestigationCase
    row cascades and deletes all associated TransactionRecord rows.
    """
    async with isolated_e2e_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("cascade_test.csv", SYNTHETIC_FORENSIC_E2E_CSV, "text/csv")}
            upload_res = await client.post("/api/v1/investigations/upload", files=files)
            case_id_str = upload_res.json()["case_id"]
            case_uuid = uuid.UUID(case_id_str)

            factory = get_session_factory()
            async with factory() as session:
                # Confirm records exist
                tx_count_stmt = select(func.count(TransactionRecord.id)).where(TransactionRecord.case_id == case_uuid)
                count_before = (await session.execute(tx_count_stmt)).scalar()
                assert count_before == 7

                # Delete the parent case
                case_stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
                case_obj = (await session.execute(case_stmt)).scalar_one()
                await session.delete(case_obj)
                await session.commit()

                # Confirm transactions were cascade-deleted
                count_after = (await session.execute(tx_count_stmt)).scalar()
                assert count_after == 0


@pytest.mark.asyncio
async def test_e2e_nonexistent_case_error_handling():
    """
    Verifies that querying nonexistent case UUIDs across detail, stream,
    and dedicated tool endpoints returns clean HTTP 404 responses.
    """
    async with isolated_e2e_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            fake_uuid = str(uuid.uuid4())

            # 1. Detail endpoint -> 404
            det_res = await client.get(f"/api/v1/investigations/{fake_uuid}")
            assert det_res.status_code == 404

            # 2. Stream endpoint -> 404
            stream_res = await client.get(f"/api/v1/investigations/{fake_uuid}/stream")
            assert stream_res.status_code == 404

            # 3. Dedicated tool: transactions -> 404
            tx_res = await client.post("/api/v1/tools/transactions", json={"case_id": fake_uuid})
            assert tx_res.status_code == 404

            # 4. Dedicated tool: entities -> 404
            ent_res = await client.post("/api/v1/tools/entities", json={"case_id": fake_uuid})
            assert ent_res.status_code == 404

            # 5. Dedicated tool: patterns -> 404
            pat_res = await client.post("/api/v1/tools/patterns", json={"case_id": fake_uuid})
            assert pat_res.status_code == 404


@pytest.mark.asyncio
async def test_e2e_in_memory_offline_full_lifecycle():
    """
    Verifies complete end-to-end pipeline functionality in offline mode
    when DATABASE_URL is unconfigured (using in-memory fallback caches).
    """
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = ""
    await close_db()
    INVESTIGATION_CASES.clear()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Health check
            h_res = await client.get("/health")
            assert h_res.status_code == 200

            # 2. Upload
            files = {"file": ("offline_case.csv", SYNTHETIC_FORENSIC_E2E_CSV, "text/csv")}
            up_res = await client.post("/api/v1/investigations/upload", files=files)
            assert up_res.status_code == 201
            case_id = up_res.json()["case_id"]

            # 3. List
            list_res = await client.get("/api/v1/investigations")
            assert list_res.status_code == 200
            assert any((c.get("case_id") or c.get("id")) == case_id for c in list_res.json()["items"])

            # 4. Detail
            det_res = await client.get(f"/api/v1/investigations/{case_id}")
            assert det_res.status_code == 200
            assert det_res.json()["status"] == "PROCESSING"

            # 5. Tools
            tx_res = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert tx_res.status_code == 200
            assert tx_res.json()["total"] >= 1

            ent_res = await client.post("/api/v1/tools/entities", json={"case_id": case_id})
            assert ent_res.status_code == 200
            assert ent_res.json()["total_entities"] >= 1

            pat_res = await client.post("/api/v1/tools/patterns", json={"case_id": case_id})
            assert pat_res.status_code == 200
            assert pat_res.json()["total_cycles_count"] >= 1

            legal_res = await client.post(
                "/api/v1/tools/legal-precedents",
                json={"query_text": "CFF 69-B operaciones simuladas"},
            )
            assert legal_res.status_code == 200
            assert legal_res.json()["total_matches"] >= 1

            # 6. Stream & verdict
            async with client.stream("GET", f"/api/v1/investigations/{case_id}/stream") as stream_res:
                assert stream_res.status_code == 200
                async for _ in stream_res.aiter_lines():
                    pass

            # 7. Post-stream detail verification in-memory
            post_det = (await client.get(f"/api/v1/investigations/{case_id}")).json()
            assert post_det["status"] == "COMPLETED"
            assert post_det["verdict"] is not None

            # 8. TTS
            tts_res = await client.post(
                "/api/v1/tts/synthesize",
                json={"text": post_det["verdict"]["audit_summary_text"]},
            )
            assert tts_res.status_code == 200
            assert "audio/mpeg" in tts_res.headers["content-type"]
    finally:
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()
