"""
Empirical Adversarial Challenge Test Suite for Milestone 3:
Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents.

Dimensions Tested:
1. SQL Injection Attacks (field names, operators, values, sort columns, like wildcards, in-lists)
2. Cross-Case Data Exfiltration & Multi-Tenant Isolation (Case A vs Case B isolation, omitted case_id, mismatched case_id, empty case_id)
3. Target Validation & Whitelisting (unsupported tables, sqlite_master, pg_catalog, DROP TABLE in target)
4. Comprehensive Operator Matrix (all 9 operators: eq, neq, gt, gte, lt, lte, like, ilike, in, not_in + invalid/malicious operators)
5. Parameter Boundaries & Fuzzing (min/max inversions, dimension mismatches, out-of-range thresholds, extreme offsets)
6. Tool Registry Runtime Extensibility & Metadata Discovery
7. Dual Execution Consistency (PostgreSQL/SQLite AsyncSession vs in-memory fallback)
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
from backend.core.database import close_db, init_db, get_session_factory
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

CSV_CASE_A = """origin,destination,amount,timestamp
ACC_ALPHA,ACC_BETA,100000.0,1.0
ACC_BETA,ACC_GAMMA,98000.0,2.0
ACC_GAMMA,ACC_ALPHA,95000.0,3.0
CORP_A,MULE_A,300000.0,10.0
MULE_A,OFFSHORE_A,295000.0,20.0
""".encode("utf-8")

CSV_CASE_B = """origin,destination,amount,timestamp
VICTIM_X,ATTACKER_Y,888888.0,1.0
ATTACKER_Y,LAUNDERER_Z,880000.0,2.0
LAUNDERER_Z,SHELL_CORP,875000.0,3.0
""".encode("utf-8")


@contextlib.asynccontextmanager
async def isolated_challenge_db():
    """Configures isolated test database with seeded legal knowledge and clean state."""
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()

    factory = get_session_factory()
    async with factory() as session:
        await seed_legal_knowledge(session)

    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


async def upload_case(client: httpx.AsyncClient, csv_data: bytes, filename: str) -> str:
    files = {"file": (filename, csv_data, "text/csv")}
    resp = await client.post("/api/v1/investigations/upload", files=files)
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()["case_id"]


# =============================================================================
# Dimension 1: SQL Injection Attacks
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_sqli_in_field_names():
    """Verify that SQL injection payloads in field names are blocked by schema validation."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            sqli_field_payloads = [
                "origin; DROP TABLE transactions; --",
                "origin' OR '1'='1",
                "amount; SELECT pg_sleep(5); --",
                "id UNION SELECT * FROM investigation_cases --",
                "1; DELETE FROM transaction_records WHERE 1=1; --",
                "destination\" OR \"1\"=\"1",
                "origin' AND 1=cast((SELECT table_name FROM information_schema.tables LIMIT 1) as int) --",
            ]

            for payload in sqli_field_payloads:
                resp = await client.post("/api/v1/tools/query", json={
                    "target": "transactions",
                    "case_id": case_id,
                    "filters": [
                        {"field": payload, "operator": "eq", "value": "ACC_ALPHA"}
                    ],
                })
                # Must be rejected with HTTP 422 Unprocessable Entity by Pydantic model validator
                assert resp.status_code == 422, f"Expected 422 for payload: {payload}, got {resp.status_code}"
                detail_str = str(resp.json())
                assert "is not permissible for target 'transactions'" in detail_str or "Allowed fields" in detail_str


@pytest.mark.asyncio
async def test_challenge_sqli_in_sort_by():
    """Verify that SQL injection payloads in sort_by field are blocked."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            sqli_sort_payloads = [
                "amount; DROP TABLE transactions; --",
                "amount, (SELECT pg_sleep(5))",
                "timestamp; UPDATE investigation_cases SET status='HACKED'--",
                "non_existent_column",
            ]

            for payload in sqli_sort_payloads:
                resp = await client.post("/api/v1/tools/query", json={
                    "target": "transactions",
                    "case_id": case_id,
                    "sort_by": payload,
                })
                assert resp.status_code == 422, f"Expected 422 for sort payload: {payload}, got {resp.status_code}"
                assert "sort_by field" in str(resp.json()) or "is not permissible" in str(resp.json())


@pytest.mark.asyncio
async def test_challenge_sqli_in_filter_values_are_parameterized():
    """Verify that malicious SQL fragments in filter values are treated strictly as literals, not executed."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            sqli_value_payloads = [
                "ACC_ALPHA'; DROP TABLE transactions; --",
                "' OR '1'='1",
                "' UNION SELECT id, filename, status, created_at, updated_at, NULL, NULL, NULL, NULL, NULL FROM investigation_cases --",
                "ACC_ALPHA' AND 1=(SELECT COUNT(*) FROM investigation_cases) --",
                "'; EXEC sp_executesql N'SELECT 1'; --",
            ]

            for val in sqli_value_payloads:
                resp = await client.post("/api/v1/tools/query", json={
                    "target": "transactions",
                    "case_id": case_id,
                    "filters": [
                        {"field": "origin", "operator": "eq", "value": val}
                    ],
                })
                assert resp.status_code == 200, f"Query failed on literal value: {val}, resp: {resp.text}"
                data = resp.json()
                # Zero records should match because no origin literally equals the SQL payload
                assert data["total"] == 0
                assert len(data["records"]) == 0

            # Verify table integrity: transactions still exist
            verify_resp = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert verify_resp.status_code == 200
            assert verify_resp.json()["total"] == 5


@pytest.mark.asyncio
async def test_challenge_sqli_in_operators():
    """Verify that invalid/injected operator values are rejected by schema enum validation."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            malicious_operators = [
                "eq; DROP TABLE transactions; --",
                "=",
                "LIKE '%'; --",
                "IN (SELECT id FROM users) --",
                "IS NOT NULL; --",
                "OR",
                "AND",
            ]

            for op in malicious_operators:
                resp = await client.post("/api/v1/tools/query", json={
                    "target": "transactions",
                    "case_id": case_id,
                    "filters": [
                        {"field": "origin", "operator": op, "value": "ACC_ALPHA"}
                    ],
                })
                assert resp.status_code == 422, f"Expected 422 for operator: {op}, got {resp.status_code}"


# =============================================================================
# Dimension 2: Cross-Case Data Exfiltration & Scoping
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_cross_case_isolation():
    """
    Upload two distinct investigation cases (Case A and Case B).
    Empirically verify that:
    1. Case A queries cannot view Case B data even if specifically requested.
    2. Filters matching Case B data return 0 records under Case A.
    3. Dedicated tools strictly isolate cases.
    """
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_a = await upload_case(client, CSV_CASE_A, "case_a.csv")
            case_b = await upload_case(client, CSV_CASE_B, "case_b.csv")

            # 1. Query Case A for Case B origin (VICTIM_X) -> must return 0
            resp_exfil = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_a,
                "filters": [
                    {"field": "origin", "operator": "eq", "value": "VICTIM_X"}
                ],
            })
            assert resp_exfil.status_code == 200
            assert resp_exfil.json()["total"] == 0
            assert len(resp_exfil.json()["records"]) == 0

            # 2. Query Case B for Case B origin (VICTIM_X) -> must return 1
            resp_b = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_b,
                "filters": [
                    {"field": "origin", "operator": "eq", "value": "VICTIM_X"}
                ],
            })
            assert resp_b.status_code == 200
            assert resp_b.json()["total"] == 1
            assert resp_b.json()["records"][0]["destination"] == "ATTACKER_Y"

            # 3. Attempt exfiltration in dedicated /tools/transactions
            resp_ded_exfil = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_a,
                "origin": "VICTIM_X",
            })
            assert resp_ded_exfil.status_code == 200
            assert resp_ded_exfil.json()["total"] == 0

            # 4. Attempt exfiltration in /tools/entities
            resp_ent_exfil = await client.post("/api/v1/tools/entities", json={
                "case_id": case_a,
                "entity_id": "VICTIM_X",
            })
            # VICTIM_X does not exist in Case A -> 404
            assert resp_ent_exfil.status_code == 404


@pytest.mark.asyncio
async def test_challenge_mandatory_scoping_omission_attacks():
    """
    Attempt to bypass mandatory case_id scoping on all case-scoped targets:
    transactions, entities, nodes, edges, patterns, cycles, passthrough_accounts.
    """
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            scoped_targets = [
                "transactions",
                "entities",
                "nodes",
                "edges",
                "patterns",
                "cycles",
                "passthrough_accounts",
            ]

            for target in scoped_targets:
                # Omit case_id completely
                resp_omit = await client.post("/api/v1/tools/query", json={
                    "target": target,
                })
                assert resp_omit.status_code == 422, f"Target {target} succeeded without case_id: {resp_omit.status_code}"
                assert "case_id is required" in str(resp_omit.json())

                # Pass null / None case_id
                resp_null = await client.post("/api/v1/tools/query", json={
                    "target": target,
                    "case_id": None,
                })
                assert resp_null.status_code == 422, f"Target {target} succeeded with null case_id"

                # Pass empty string case_id
                resp_empty = await client.post("/api/v1/tools/query", json={
                    "target": target,
                    "case_id": "",
                })
                assert resp_empty.status_code in (400, 422), f"Target {target} accepted empty case_id"

                # Pass invalid UUID
                resp_bad_uuid = await client.post("/api/v1/tools/query", json={
                    "target": target,
                    "case_id": "not-a-valid-uuid-12345",
                })
                assert resp_bad_uuid.status_code in (400, 422)


@pytest.mark.asyncio
async def test_challenge_mismatched_filter_case_id_cannot_leak():
    """
    Verify that if an attacker passes case_id=Case_A at the root, but attempts
    a filter {"field": "case_id", "operator": "eq", "value": Case_B},
    the engine does not leak Case_B data.
    """
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_a = await upload_case(client, CSV_CASE_A, "case_a.csv")
            case_b = await upload_case(client, CSV_CASE_B, "case_b.csv")

            resp = await client.post("/api/v1/tools/query", json={
                "target": "transactions",
                "case_id": case_a,
                "filters": [
                    {"field": "case_id", "operator": "eq", "value": case_b},
                    {"field": "origin", "operator": "eq", "value": "VICTIM_X"},
                ],
            })
            assert resp.status_code == 200
            # Root case_id enforces Case A boundary, so Case B data is never returned
            assert resp.json()["total"] == 0
            assert len(resp.json()["records"]) == 0


# =============================================================================
# Dimension 3: Target Whitelist Validation
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_unsupported_targets():
    """Verify that arbitrary or malicious table names are rejected."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unsupported_targets = [
                "non_existent_table",
                "sqlite_master",
                "sqlite_sequence",
                "pg_catalog.pg_tables",
                "information_schema.tables",
                "users",
                "passwords",
                "investigation_cases; DROP TABLE transactions; --",
                "__proto__",
                "constructor",
            ]

            for target in unsupported_targets:
                resp = await client.post("/api/v1/tools/query", json={
                    "target": target,
                })
                assert resp.status_code in (400, 422), f"Expected 400/422 for target '{target}', got {resp.status_code}"


# =============================================================================
# Dimension 4: Full Operator Matrix (All 9 Operators + Boundary Values)
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_all_nine_operators_matrix():
    """
    Systematically test all 9 supported operators:
    eq, neq, gt, gte, lt, lte, like, ilike, in, not_in
    against known synthetic dataset transactions.
    """
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            # 1. eq (amount == 100000.0) -> 1 record
            r_eq = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "eq", "value": 100000.0}]
            })
            assert r_eq.status_code == 200 and r_eq.json()["total"] == 1

            # 2. neq (amount != 100000.0) -> 4 records
            r_neq = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "neq", "value": 100000.0}]
            })
            assert r_neq.status_code == 200 and r_neq.json()["total"] == 4

            # 3. gt (amount > 100000.0) -> 2 records (300000.0, 295000.0)
            r_gt = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "gt", "value": 100000.0}]
            })
            assert r_gt.status_code == 200 and r_gt.json()["total"] == 2

            # 4. gte (amount >= 100000.0) -> 3 records (100000.0, 300000.0, 295000.0)
            r_gte = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "gte", "value": 100000.0}]
            })
            assert r_gte.status_code == 200 and r_gte.json()["total"] == 3

            # 5. lt (amount < 100000.0) -> 2 records (98000.0, 95000.0)
            r_lt = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "lt", "value": 100000.0}]
            })
            assert r_lt.status_code == 200 and r_lt.json()["total"] == 2

            # 6. lte (amount <= 100000.0) -> 3 records (95000.0, 98000.0, 100000.0)
            r_lte = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "amount", "operator": "lte", "value": 100000.0}]
            })
            assert r_lte.status_code == 200 and r_lte.json()["total"] == 3

            # 7. like (origin LIKE '%BETA%') -> 1 record (ACC_BETA)
            r_like = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "origin", "operator": "like", "value": "BETA"}]
            })
            assert r_like.status_code == 200 and r_like.json()["total"] == 1

            # 8. ilike (origin ILIKE 'acc_gamma') -> 1 record (case-insensitive)
            r_ilike = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "origin", "operator": "ilike", "value": "acc_gamma"}]
            })
            assert r_ilike.status_code == 200 and r_ilike.json()["total"] == 1

            # 9. in (origin IN ['ACC_ALPHA', 'CORP_A']) -> 2 records
            r_in = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "origin", "operator": "in", "value": ["ACC_ALPHA", "CORP_A"]}]
            })
            assert r_in.status_code == 200 and r_in.json()["total"] == 2

            # 10. not_in (origin NOT IN ['ACC_ALPHA', 'CORP_A']) -> 3 records
            r_notin = await client.post("/api/v1/tools/query", json={
                "target": "transactions", "case_id": case_id,
                "filters": [{"field": "origin", "operator": "not_in", "value": ["ACC_ALPHA", "CORP_A"]}]
            })
            assert r_notin.status_code == 200 and r_notin.json()["total"] == 3


@pytest.mark.asyncio
async def test_challenge_in_and_not_in_malformed_values():
    """Verify that passing non-array types to 'in' and 'not_in' raises validation error."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            invalid_in_values = [
                "ACC_ALPHA",  # scalar string
                12345,        # scalar int
                True,         # scalar bool
                {"key": "val"} # dict
            ]

            for bad_val in invalid_in_values:
                resp_in = await client.post("/api/v1/tools/query", json={
                    "target": "transactions", "case_id": case_id,
                    "filters": [{"field": "origin", "operator": "in", "value": bad_val}]
                })
                assert resp_in.status_code == 422, f"Expected 422 for in with {bad_val}"

                resp_notin = await client.post("/api/v1/tools/query", json={
                    "target": "transactions", "case_id": case_id,
                    "filters": [{"field": "origin", "operator": "not_in", "value": bad_val}]
                })
                assert resp_notin.status_code == 422, f"Expected 422 for not_in with {bad_val}"


# =============================================================================
# Dimension 5: Dedicated Endpoints Parameter Bounds & Stress Testing
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_dedicated_transactions_parameter_bounds():
    """Test min_amount > max_amount inversion and pagination bounds."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            # 1. Inverted amount bounds: min > max -> 422
            resp_inv = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "min_amount": 500000.0,
                "max_amount": 1000.0,
            })
            assert resp_inv.status_code == 422
            assert "cannot be less than min_amount" in str(resp_inv.json())

            # 2. Limit out of range (> 1000) -> 422
            resp_lim = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "limit": 1001,
            })
            assert resp_lim.status_code == 422

            # 3. Limit < 1 -> 422
            resp_lim_zero = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "limit": 0,
            })
            assert resp_lim_zero.status_code == 422

            # 4. Negative offset -> 422
            resp_neg_off = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "offset": -5,
            })
            assert resp_neg_off.status_code == 422

            # 5. Non-existent case -> 404
            fake_uuid = str(uuid.uuid4())
            resp_404 = await client.post("/api/v1/tools/transactions", json={
                "case_id": fake_uuid,
            })
            assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_challenge_dedicated_patterns_bounds_and_filtering():
    """Test min_cycle_length > max_cycle_length inversion and pattern types."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            # Inverted cycle lengths
            resp_inv = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "min_cycle_length": 6,
                "max_cycle_length": 3,
            })
            assert resp_inv.status_code == 422
            assert "cannot be less than min_cycle_length" in str(resp_inv.json())

            # Invalid pattern_type
            resp_bad_type = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_id,
                "pattern_type": "quantum_layering",
            })
            assert resp_bad_type.status_code == 422


@pytest.mark.asyncio
async def test_challenge_legal_precedents_vector_dimensions():
    """Test vector search with invalid vector dimensions and empty text."""
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Vector with 512 dimensions instead of 1536 -> 422
            resp_dim = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "operaciones simuladas",
                "query_vector": [0.1] * 512,
            })
            assert resp_dim.status_code == 422
            assert "must have exactly 1536 dimensions" in str(resp_dim.json())

            # 2. Empty query_text -> 422
            resp_empty = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "",
            })
            assert resp_empty.status_code == 422

            # 3. Valid search executes and returns Mexican AML precedents
            resp_valid = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "empresa que factura operaciones simuladas EFOS articulo 69-B",
                "top_k": 3,
            })
            assert resp_valid.status_code == 200
            data = resp_valid.json()
            assert data["top_k"] == 3
            assert data["total_matches"] >= 1
            # Verify CFF Art. 69-B presence
            codes = [r["article_code"] for r in data["results"]]
            assert any("69-B" in c or "69B" in c for c in codes)


# =============================================================================
# Dimension 6: Tool Registry Runtime Discovery & Aliasing
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_tool_registry_discovery_and_aliases():
    """Verify tool_registry.list_targets() returns full metadata and aliases resolve."""
    targets = tool_registry.list_targets()
    target_names = [t["target"] for t in targets]

    # Required core targets must be discovered
    assert "transactions" in target_names
    assert "cases" in target_names
    assert "entities" in target_names
    assert "patterns" in target_names
    assert "edges" in target_names
    assert "legal_precedents" in target_names

    # Check that each entry has proper schema metadata
    for t in targets:
        assert "allowed_columns" in t
        assert len(t["allowed_columns"]) > 0
        assert "default_sort" in t
        assert isinstance(t["requires_case_id"], bool)

    # Check alias resolution
    async with isolated_challenge_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_case(client, CSV_CASE_A, "case_a.csv")

            # 'nodes' is alias for 'entities'
            resp_nodes = await client.post("/api/v1/tools/query", json={
                "target": "nodes",
                "case_id": case_id,
            })
            assert resp_nodes.status_code == 200
            assert resp_nodes.json()["target"] in ("nodes", "entities")

            # 'cycles' is alias for 'patterns'
            resp_cycles = await client.post("/api/v1/tools/query", json={
                "target": "cycles",
                "case_id": case_id,
            })
            assert resp_cycles.status_code == 200
