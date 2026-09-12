"""
Automated Test Suite for Milestone 3:
Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents.
Tests all 4 dedicated endpoints, dynamic composable query engine, security whitelisting,
SQL injection immunity, operators, pagination, sorting, and dual execution modes.
"""

import contextlib
from decimal import Decimal
import json
from typing import Optional
import uuid
import httpx
import pytest

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.core.config import settings
from backend.core.database import close_db, init_db
from backend.main import app
from backend.models.forensic import (
    generate_deterministic_embedding,
    seed_legal_knowledge,
)
from backend.schemas.agent_tools import (
    DynamicQueryRequest,
    DynamicQueryResponse,
    FilterOperator,
    QueryFilter,
    SortOrder,
    TargetEntity,
)
from backend.services.tool_registry import TargetMetadata, tool_registry

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
    """Configures isolated test database with seeded legal knowledge and reset state."""
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()

    # Seed legal knowledge into SQLite
    from backend.core.database import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        await seed_legal_knowledge(session)

    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


async def upload_test_case(client: httpx.AsyncClient) -> str:
    """Helper to upload synthetic dataset and return case_id."""
    files = {"file": ("test_tools_case.csv", SYNTHETIC_AML_CSV, "text/csv")}
    resp = await client.post("/api/v1/investigations/upload", files=files)
    assert resp.status_code == 201
    return resp.json()["case_id"]


# =============================================================================
# 1. Dedicated Tool: Transactions Tests
# =============================================================================

@pytest.mark.asyncio
async def test_dedicated_transactions_basic_and_filtering():
    """Tests /api/v1/tools/transactions with origin, destination, amounts, and suspicion."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # 1. Base query: all transactions for case
            resp = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert resp.status_code == 200
            data = resp.json()
            assert data["case_id"] == case_id
            assert data["total"] == 7
            assert len(data["items"]) == 7
            assert data["total_volume_mxn"] > 1400000.0

            # 2. Origin filter
            resp_orig = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "origin": "ACC_A",
            })
            assert resp_orig.status_code == 200
            d_orig = resp_orig.json()
            assert d_orig["total"] == 1
            assert d_orig["items"][0]["destination"] == "ACC_B"
            assert d_orig["items"][0]["amount"] == 150000.0

            # 3. Destination filter
            resp_dest = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "destination": "OFFSHORE_OUT",
            })
            assert resp_dest.status_code == 200
            d_dest = resp_dest.json()
            assert d_dest["total"] == 1
            assert d_dest["items"][0]["origin"] == "MULE_01"

            # 4. Suspicion flag filter
            resp_susp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "is_suspicious": True,
            })
            assert resp_susp.status_code == 200
            assert resp_susp.json()["total"] == 5

            resp_benign = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "is_suspicious": False,
            })
            assert resp_benign.status_code == 200
            assert resp_benign.json()["total"] == 2

            # 5. Amount bounds
            resp_amt = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "min_amount": 100000.0,
                "max_amount": 200000.0,
            })
            assert resp_amt.status_code == 200
            assert resp_amt.json()["total"] == 3

            # 6. Pagination
            resp_p1 = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "limit": 3,
                "offset": 0,
            })
            assert resp_p1.status_code == 200
            assert len(resp_p1.json()["items"]) == 3

            resp_p2 = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "limit": 3,
                "offset": 3,
            })
            assert resp_p2.status_code == 200
            assert len(resp_p2.json()["items"]) == 3
            ids_p1 = {item["id"] for item in resp_p1.json()["items"]}
            ids_p2 = {item["id"] for item in resp_p2.json()["items"]}
            assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_dedicated_transactions_validation_errors():
    """Tests /api/v1/tools/transactions input validation and bounds errors."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Inverted amount bounds
            resp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "min_amount": 50000.0,
                "max_amount": 10000.0,
            })
            assert resp.status_code == 422

            # Nonexistent case_id
            non_existent = str(uuid.uuid4())
            resp_404 = await client.post("/api/v1/tools/transactions", json={"case_id": non_existent})
            assert resp_404.status_code == 404

            # Malformed UUID
            resp_mal = await client.post("/api/v1/tools/transactions", json={"case_id": "not-a-uuid"})
            assert resp_mal.status_code in (400, 422)


# =============================================================================
# 2. Dedicated Tool: Entities Tests
# =============================================================================

@pytest.mark.asyncio
async def test_dedicated_entities_profiling():
    """Tests /api/v1/tools/entities bulk profiling and single entity profiling."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Bulk profiling
            resp = await client.post("/api/v1/tools/entities", json={"case_id": case_id})
            assert resp.status_code == 200
            data = resp.json()
            assert data["case_id"] == case_id
            assert data["total_entities"] >= 4
            entities = data["entities"]
            assert len(entities) >= 4

            # Specific entity profiling
            resp_mule = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "MULE_01",
            })
            assert resp_mule.status_code == 200
            d_mule = resp_mule.json()
            assert d_mule["total_entities"] == 1
            mule_node = d_mule["entities"][0]
            assert mule_node["entity_id"] == "MULE_01"
            assert mule_node["total_inflow"] == 500000.0
            assert mule_node["total_outflow"] == 485000.0
            assert mule_node["net_flow"] == 15000.0
            assert mule_node["risk_score"] >= 0.5
            assert mule_node["is_suspicious"] is True
            assert "CORP_INFLOW" in mule_node["counterparties_in"]
            assert "OFFSHORE_OUT" in mule_node["counterparties_out"]

            # Filter by min_risk_score
            resp_risk = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "min_risk_score": 0.5,
            })
            assert resp_risk.status_code == 200
            for e in resp_risk.json()["entities"]:
                assert e["risk_score"] >= 0.5

            # Unknown entity in valid case returns 404
            resp_unknown = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "GHOST_ACCOUNT_999",
            })
            assert resp_unknown.status_code == 404

            # Unknown case returns 404
            resp_case_404 = await client.post("/api/v1/tools/entities", json={
                "case_id": str(uuid.uuid4()),
            })
            assert resp_case_404.status_code == 404


# =============================================================================
# 3. Dedicated Tool: Patterns Tests
# =============================================================================

@pytest.mark.asyncio
async def test_dedicated_patterns_retrieval():
    """Tests /api/v1/tools/patterns for cycles and pass-through accounts."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Pattern type: ALL
            resp_all = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "pattern_type": "all",
            })
            assert resp_all.status_code == 200
            d_all = resp_all.json()
            assert d_all["total_cycles_count"] >= 1
            assert d_all["total_mules_count"] >= 1
            assert len(d_all["cycles"]) >= 1
            assert len(d_all["passthrough_mules"]) >= 1

            # Pattern type: CYCLES only
            resp_cycles = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "pattern_type": "cycles",
                "min_cycle_length": 3,
                "max_cycle_length": 5,
            })
            assert resp_cycles.status_code == 200
            d_cyc = resp_cycles.json()
            assert d_cyc["total_cycles_count"] >= 1
            assert d_cyc["total_mules_count"] == 0
            assert len(d_cyc["passthrough_mules"]) == 0
            cycle = d_cyc["cycles"][0]
            assert cycle["length"] == 3
            assert cycle["estimated_volume"] > 0

            # Pattern type: PASSTHROUGH_MULES only
            resp_mules = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "pattern_type": "passthrough_mules",
                "min_passthrough_ratio": 0.90,
            })
            assert resp_mules.status_code == 200
            d_mules = resp_mules.json()
            assert d_mules["total_mules_count"] >= 1
            assert d_mules["total_cycles_count"] == 0
            mule_accounts = [m["account"] for m in d_mules["passthrough_mules"]]
            assert "MULE_01" in mule_accounts
            mule = next(m for m in d_mules["passthrough_mules"] if m["account"] == "MULE_01")
            assert mule["ratio"] >= 0.90

            # Inverted cycle length bounds
            resp_inv = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "min_cycle_length": 5,
                "max_cycle_length": 2,
            })
            assert resp_inv.status_code == 422


# =============================================================================
# 4. Dedicated Tool: Legal Precedents Tests
# =============================================================================

@pytest.mark.asyncio
async def test_dedicated_legal_precedents_vector_search():
    """Tests /api/v1/tools/legal-precedents vector similarity search."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Natural language query for CFF 69-B (EFOS / inexistencia de operaciones)
            resp = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "empresas que facturan operaciones simuladas inexistencia de comprobantes fiscales",
                "top_k": 3,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["top_k"] == 3
            assert data["total_matches"] >= 1
            assert len(data["results"]) >= 1
            top_art = data["results"][0]
            assert "article_code" in top_art
            assert top_art["similarity_score"] >= -1.0
            assert top_art["distance"] is not None

            # 2. Filter by law_name (e.g. Código Fiscal)
            resp_cff = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "presuncion de transmision indebida",
                "law_name_filter": "Código Fiscal",
                "top_k": 2,
            })
            assert resp_cff.status_code == 200
            d_cff = resp_cff.json()
            for r in d_cff["results"]:
                assert "Código Fiscal" in r["law_name"]

            # 3. Explicit query vector
            vec_1536 = generate_deterministic_embedding("lavado de dinero operaciones con recursos de procedencia ilicita")
            resp_vec = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "dummy query",
                "query_vector": vec_1536,
                "top_k": 2,
            })
            assert resp_vec.status_code == 200
            assert len(resp_vec.json()["results"]) == 2

            # 4. Invalid query vector dimension (e.g. 512 dim)
            resp_invalid_dim = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "test",
                "query_vector": [0.1] * 512,
            })
            assert resp_invalid_dim.status_code == 422

            # 5. Impossible threshold returns 0 matches cleanly
            resp_empty = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "random unmatched query",
                "similarity_threshold": 1.0,
            })
            assert resp_empty.status_code == 200
            assert resp_empty.json()["total_matches"] == 0
            assert resp_empty.json()["results"] == []


# =============================================================================
# 5. Dynamic Composable Query Engine Tests (`/api/v1/tools/query`)
# =============================================================================

@pytest.mark.asyncio
async def test_dynamic_query_transactions_operators():
    """Tests /api/v1/tools/query on transactions using all relational operators."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # eq
            resp = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "eq", "value": "ACC_A"}],
            })
            assert resp.status_code == 200
            assert resp.json()["total"] == 1

            # neq
            resp_neq = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "neq", "value": "ACC_A"}],
            })
            assert resp_neq.status_code == 200
            assert resp_neq.json()["total"] == 6

            # gt & lt
            resp_gt = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "amount", "operator": "gt", "value": 100000.0}],
            })
            assert resp_gt.status_code == 200
            assert resp_gt.json()["total"] == 5

            resp_lt = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "amount", "operator": "lt", "value": 1000.0}],
            })
            assert resp_lt.status_code == 200
            assert resp_lt.json()["total"] == 1
            assert resp_lt.json()["records"][0]["origin"] == "STORE_MERCHANT"

            # gte & lte
            resp_gte = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [
                    {"field": "amount", "operator": "gte", "value": 2500.0},
                    {"field": "amount", "operator": "lte", "value": 145000.0},
                ],
            })
            assert resp_gte.status_code == 200
            assert resp_gte.json()["total"] == 2

            # like / ilike
            resp_like = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "destination", "operator": "ilike", "value": "offshore"}],
            })
            assert resp_like.status_code == 200
            assert resp_like.json()["total"] == 1
            assert resp_like.json()["records"][0]["destination"] == "OFFSHORE_OUT"

            # in
            resp_in = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "in", "value": ["ACC_A", "ACC_B"]}],
            })
            assert resp_in.status_code == 200
            assert resp_in.json()["total"] == 2

            # not_in
            resp_nin = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "not_in", "value": ["ACC_A", "ACC_B"]}],
            })
            assert resp_nin.status_code == 200
            assert resp_nin.json()["total"] == 5


@pytest.mark.asyncio
async def test_dynamic_query_sorting_and_pagination():
    """Tests dynamic query sort_by, sort_order, limit, and offset."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Descending sort by amount
            resp_desc = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "sort_by": "amount",
                "sort_order": "desc",
                "limit": 2,
                "offset": 0,
            })
            assert resp_desc.status_code == 200
            records = resp_desc.json()["records"]
            assert len(records) == 2
            assert records[0]["amount"] == 500000.0
            assert records[1]["amount"] == 485000.0

            # Ascending sort by amount
            resp_asc = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "sort_by": "amount",
                "sort_order": "asc",
                "limit": 2,
                "offset": 0,
            })
            assert resp_asc.status_code == 200
            asc_records = resp_asc.json()["records"]
            assert len(asc_records) == 2
            assert asc_records[0]["amount"] == 120.0
            assert asc_records[1]["amount"] == 2500.0


@pytest.mark.asyncio
async def test_dynamic_query_security_and_injection_prevention():
    """Tests dynamic query column whitelisting, SQL injection immunity, and scoping."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # 1. SQL injection in column name: rejected by whitelist
            resp_sqli_col = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin; DROP TABLE transactions;--", "operator": "eq", "value": "ACC_A"}],
            })
            assert resp_sqli_col.status_code in (400, 422)

            # 2. Unwhitelisted field
            resp_bad_field = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "password_hash", "operator": "eq", "value": "secret"}],
            })
            assert resp_bad_field.status_code in (400, 422)

            # 3. Unwhitelisted sort_by field
            resp_bad_sort = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "sort_by": "secret_column",
            })
            assert resp_bad_sort.status_code in (400, 422)

            # 4. Mandatory scoping violation: transactions without case_id
            resp_no_scope = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "filters": [{"field": "is_suspicious", "operator": "eq", "value": True}],
            })
            assert resp_no_scope.status_code in (400, 422)

            # 5. Invalid 'in' operator value (scalar instead of array)
            resp_in_scalar = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "in", "value": "scalar_value"}],
            })
            assert resp_in_scalar.status_code in (400, 422)


@pytest.mark.asyncio
async def test_dynamic_query_all_targets():
    """Tests dynamic query across all supported targets and aliases."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # 1. Target: cases (unscoped)
            resp_cases = await client.post("/api/v1/tools/query", json={
                "target": "cases",
                "filters": [{"field": "status", "operator": "eq", "value": "PROCESSING"}],
            })
            assert resp_cases.status_code == 200
            assert resp_cases.json()["total"] >= 1

            # 2. Target: entities
            resp_ent = await client.post("/api/v1/tools/query", json={
                "target": "entities",
                "case_id": case_id,
                "filters": [{"field": "risk_score", "operator": "gte", "value": 0.5}],
            })
            assert resp_ent.status_code == 200
            assert resp_ent.json()["total"] >= 1

            # 3. Target: nodes (alias for entities)
            resp_nodes = await client.post("/api/v1/tools/query", json={
                "target": "nodes",
                "case_id": case_id,
                "filters": [{"field": "is_suspicious", "operator": "eq", "value": True}],
            })
            assert resp_nodes.status_code == 200
            assert resp_nodes.json()["total"] >= 1

            # 4. Target: patterns
            resp_pat = await client.post("/api/v1/tools/query", json={
                "target": "patterns",
                "case_id": case_id,
                "filters": [{"field": "pattern_type", "operator": "eq", "value": "CYCLE"}],
            })
            assert resp_pat.status_code == 200
            assert resp_pat.json()["total"] >= 1

            # 5. Target: cycles (alias)
            resp_cyc = await client.post("/api/v1/tools/query", json={
                "target": "cycles",
                "case_id": case_id,
                "filters": [{"field": "length", "operator": "gte", "value": 2}],
            })
            assert resp_cyc.status_code == 200
            assert resp_cyc.json()["total"] >= 1

            # 6. Target: passthrough_accounts (alias)
            resp_pt = await client.post("/api/v1/tools/query", json={
                "target": "passthrough_accounts",
                "case_id": case_id,
                "filters": [{"field": "ratio", "operator": "gte", "value": 0.9}],
            })
            assert resp_pt.status_code == 200
            assert resp_pt.json()["total"] >= 1

            # 7. Target: edges
            resp_edges = await client.post("/api/v1/tools/query", json={
                "target": "edges",
                "case_id": case_id,
                "filters": [{"field": "amount", "operator": "gt", "value": 100000.0}],
            })
            assert resp_edges.status_code == 200
            assert resp_edges.json()["total"] >= 1

            # 8. Target: legal_precedents (and legal_vectors alias)
            resp_leg = await client.post("/api/v1/tools/query", json={
                "target": "legal_precedents",
                "filters": [{"field": "article_code", "operator": "eq", "value": "CFF-ART-69B"}],
            })
            assert resp_leg.status_code == 200
            assert resp_leg.json()["total"] == 1
            assert resp_leg.json()["records"][0]["article_code"] == "CFF-ART-69B"


# =============================================================================
# 6. Offline / In-Memory Fallback Parity Tests
# =============================================================================

@pytest.mark.asyncio
async def test_in_memory_fallback_full_parity():
    """Tests that dedicated endpoints and dynamic query work with zero DB configured."""
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = None
    INVESTIGATION_CASES.clear()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("offline_test.csv", SYNTHETIC_AML_CSV, "text/csv")}
            up_resp = await client.post("/api/v1/investigations/upload", files=files)
            assert up_resp.status_code == 201
            case_id = up_resp.json()["case_id"]

            # 1. Transactions in memory
            resp_tx = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert resp_tx.status_code == 200
            assert resp_tx.json()["total"] >= 1

            # 2. Entities in memory
            resp_ent = await client.post("/api/v1/tools/entities", json={"case_id": case_id})
            assert resp_ent.status_code == 200
            assert resp_ent.json()["total_entities"] >= 1

            # 3. Patterns in memory
            resp_pat = await client.post("/api/v1/tools/patterns", json={"case_id": case_id})
            assert resp_pat.status_code == 200
            assert resp_pat.json()["total_cycles_count"] >= 1

            # 4. Legal precedents in memory
            resp_leg = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "inexistencia de operaciones amparo fiscal",
                "top_k": 2,
            })
            assert resp_leg.status_code == 200
            assert len(resp_leg.json()["results"]) == 2

            # 5. Dynamic query in memory
            resp_dyn = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "is_suspicious", "operator": "eq", "value": True}],
            })
            assert resp_dyn.status_code == 200
            assert resp_dyn.json()["total"] >= 1
    finally:
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


# =============================================================================
# 7. Custom Runtime Target Registration
# =============================================================================

@pytest.mark.asyncio
async def test_runtime_custom_tool_registration():
    """Verifies that new tools can be registered dynamically at runtime on ToolRegistry."""
    # Register custom handler
    @tool_registry.register(
        "custom_audit_summary",
        allowed_columns={"summary_type", "score"},
        allowed_sort_columns={"score"},
        requires_case_id=True,
        description="Custom forensic audit summary tool.",
    )
    async def custom_handler(request: DynamicQueryRequest, meta: TargetMetadata, db=None):
        return DynamicQueryResponse(
            target="custom_audit_summary",
            case_id=request.case_id,
            total=1,
            count=1,
            limit=request.limit,
            offset=request.offset,
            applied_filters=request.filters,
            records=[{"summary_type": "HIGH_RISK_AUDIT", "score": 98.5}],
            execution_time_ms=0.5,
        )

    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            resp = await client.post("/api/v1/tools/query", json={
                "target": "custom_audit_summary",
                "case_id": case_id,
                "filters": [{"field": "score", "operator": "gt", "value": 90.0}],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["target"] == "custom_audit_summary"
            assert data["records"][0]["summary_type"] == "HIGH_RISK_AUDIT"
            assert data["records"][0]["score"] == 98.5


# =============================================================================
# 8. Challenge & Boundary Edge Case Tests
# =============================================================================

@pytest.mark.asyncio
async def test_edge_case_time_window_and_inverted_timestamps():
    """Tests time window filtering and inverted start_time/end_time rejection."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Valid timestamp bounds
            resp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "start_time": "2020-01-01T00:00:00Z",
                "end_time": "2030-01-01T00:00:00Z",
            })
            assert resp.status_code == 200
            assert resp.json()["total"] == 7

            # Inverted timestamps: end_time < start_time
            resp_inv = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "start_time": "2026-09-12T12:00:00Z",
                "end_time": "2026-09-10T12:00:00Z",
            })
            assert resp_inv.status_code == 422


@pytest.mark.asyncio
async def test_edge_case_pagination_limits_and_negative_offsets():
    """Tests that limit <= 0, limit > 1000, and offset < 0 are strictly rejected."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # limit = 0
            resp_zero = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "limit": 0,
            })
            assert resp_zero.status_code == 422

            # limit = 5000 (> 1000)
            resp_too_large = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "limit": 5000,
            })
            assert resp_too_large.status_code == 422

            # offset = -5 (< 0)
            resp_neg_offset = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "offset": -5,
            })
            assert resp_neg_offset.status_code == 422


@pytest.mark.asyncio
async def test_edge_case_empty_in_and_not_in_operators():
    """Tests that empty arrays in 'in' and 'not_in' evaluate safely without SQL syntax error."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # empty 'in' operator -> returns 0 records
            resp_in_empty = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "in", "value": []}],
            })
            assert resp_in_empty.status_code == 200
            assert resp_in_empty.json()["total"] == 0
            assert resp_in_empty.json()["records"] == []

            # empty 'not_in' operator -> returns all records
            resp_nin_empty = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_id,
                "filters": [{"field": "origin", "operator": "not_in", "value": []}],
            })
            assert resp_nin_empty.status_code == 200
            assert resp_nin_empty.json()["total"] == 7


@pytest.mark.asyncio
async def test_edge_case_case_id_in_filters_satisfies_scoping():
    """Tests that specifying case_id inside filters list satisfies mandatory scoping."""
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            resp = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "filters": [
                    {"field": "case_id", "operator": "eq", "value": case_id},
                    {"field": "is_suspicious", "operator": "eq", "value": True},
                ],
            })
            assert resp.status_code == 200
            assert resp.json()["total"] == 5


@pytest.mark.asyncio
async def test_query_datetime_in_operator():
    """
    Regression Test for Finding 3 (M5 Challenger):
    Verifies that POST /api/v1/tools/query with 'in' and 'not_in' operators
    against the 'timestamp' column correctly converts ISO string lists to datetime objects,
    producing exact matches in SQLAlchemy.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # 1. Fetch case transactions to obtain actual stored ISO timestamps
            tx_res = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert tx_res.status_code == 200
            tx_items = tx_res.json()["items"]
            assert len(tx_items) >= 2

            ts_a = tx_items[0]["timestamp"]
            ts_b = tx_items[1]["timestamp"]
            assert ts_a is not None and ts_b is not None

            # 2. Query dynamic query builder with 'in' operator using string timestamps
            query_in = {
                "target": "transactions",
                "case_id": case_id,
                "filters": [
                    {
                        "field": "timestamp",
                        "operator": "in",
                        "value": [ts_a, ts_b]
                    }
                ]
            }
            res_in = await client.post("/api/v1/tools/query", json=query_in)
            assert res_in.status_code == 200, f"Expected 200, got {res_in.status_code}: {res_in.text}"

            data_in = res_in.json()
            assert data_in["total"] >= 2, (
                f"Expected at least 2 records matching ISO timestamps in list, got total={data_in['total']}"
            )
            assert data_in["count"] == len(data_in["records"])
            matched_ts_set = {ts_a, ts_b}
            for rec in data_in["records"]:
                assert rec["timestamp"] in matched_ts_set

            # 3. Query dynamic query builder with 'not_in' operator excluding ts_a
            query_nin = {
                "target": "transactions",
                "case_id": case_id,
                "filters": [
                    {
                        "field": "timestamp",
                        "operator": "not_in",
                        "value": [ts_a]
                    }
                ]
            }
            res_nin = await client.post("/api/v1/tools/query", json=query_nin)
            assert res_nin.status_code == 200
            data_nin = res_nin.json()

            expected_total = len(tx_items) - sum(1 for t in tx_items if t["timestamp"] == ts_a)
            assert data_nin["total"] == expected_total
            for rec in data_nin["records"]:
                assert rec["timestamp"] != ts_a

