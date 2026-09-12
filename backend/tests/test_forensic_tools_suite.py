"""
Comprehensive Automated Test Suite for the 11 Forensic Agent Tools:
1. find_related_entities
2. compare_entities
3. search_transactions
4. analyze_payment_patterns
5. search_financial_history
6. get_cashout
7. trace_money_flow
8. find_related_transactions
9. find_transaction_chains
10. find_shared_entities
11. detect_circular_flow
Plus dynamic composable queries on accounts, parties, cash_transactions, account_mappings.
"""

import contextlib
from decimal import Decimal
import uuid
import httpx
import pytest

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.main import app
from backend.models.forensic import (
    IN_MEMORY_BANKING_DATA,
    load_in_memory_banking_data,
    seed_core_banking_data,
    seed_legal_knowledge,
)

SAMPLE_AML_CSV = """origin,destination,amount,timestamp
ACC_100,ACC_200,100000.0,1.0
ACC_200,ACC_300,98000.0,2.0
ACC_300,ACC_100,95000.0,3.0
CORP_X,MULE_Y,500000.0,10.0
MULE_Y,DEST_Z,490000.0,15.0
SHARED_A,SHARED_C,12000.0,20.0
SHARED_B,SHARED_C,14000.0,21.0
SHARED_C,SHARED_D,25000.0,22.0
""".encode("utf-8")


@contextlib.asynccontextmanager
async def setup_test_db():
    """Sets up an isolated SQLite in-memory database with all models and seed data."""
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    await init_db()
    INVESTIGATION_CASES.clear()

    factory = get_session_factory()
    async with factory() as session:
        await seed_legal_knowledge(session)
        await seed_core_banking_data(session)

    try:
        yield
    finally:
        await close_db()
        settings.DATABASE_URL = original_db_url
        INVESTIGATION_CASES.clear()


async def upload_test_case(client: httpx.AsyncClient) -> str:
    files = {"file": ("test_flow.csv", SAMPLE_AML_CSV, "text/csv")}
    resp = await client.post("/api/v1/investigations/upload", files=files)
    assert resp.status_code == 201
    return resp.json()["case_id"]


# =============================================================================
# 1. Tool: search_transactions
# =============================================================================
@pytest.mark.asyncio
async def test_tool_search_transactions():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Test primary path /transactions
            resp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "min_amount": 50000.0,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 4
            for item in data["items"]:
                assert item["amount"] >= 50000.0

            # Test alias /search_transactions with entity_id filter
            resp_alias = await client.post("/api/v1/tools/search_transactions", json={
                "case_id": case_id,
                "entity_id": "ACC_100",
            })
            assert resp_alias.status_code == 200
            data_alias = resp_alias.json()
            assert data_alias["total"] >= 2
            for item in data_alias["items"]:
                assert "ACC_100" in (item["origin"], item["destination"])


# =============================================================================
# 2. Tool: find_related_entities
# =============================================================================
@pytest.mark.asyncio
async def test_tool_find_related_entities():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Look up related entities for ACC_100
            resp = await client.post("/api/v1/tools/related-entities", json={
                "entity_id": "ACC_100",
                "case_id": case_id,
                "min_tx_count": 1,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["target_entity_id"] == "ACC_100"
            assert data["total_related"] >= 2
            related_ids = [item["entity_id"] for item in data["items"]]
            assert "ACC_200" in related_ids or "ACC_300" in related_ids

            # Test alias /find_related_entities
            resp_alias = await client.post("/api/v1/tools/find_related_entities", json={
                "entity_id": "ACC_200",
                "case_id": case_id,
                "min_tx_count": 1,
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["total_related"] >= 1


# =============================================================================
# 3. Tool: compare_entities
# =============================================================================
@pytest.mark.asyncio
async def test_tool_compare_entities():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Check entities 0 and 1 from sample accounts
            resp = await client.post("/api/v1/tools/compare-entities", json={
                "entity_ids": ["0", "1", "2"],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["entities_analyzed"] == 3
            assert len(data["comparisons"]) == 3

            # Test alias /compare_entities
            resp_alias = await client.post("/api/v1/tools/compare_entities", json={
                "entity_ids": ["0", "0"],
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["entities_analyzed"] >= 1


# =============================================================================
# 4. Tool: analyze_payment_patterns
# =============================================================================
@pytest.mark.asyncio
async def test_tool_analyze_payment_patterns():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            resp = await client.post("/api/v1/tools/analyze-payment-patterns", json={
                "case_id": case_id,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["case_id"] == case_id
            assert data["has_fraudulent_patterns"] is True
            assert data["has_circular_patterns"] is True
            assert data["detected_cycles_count"] >= 1

            # Test alias
            resp_alias = await client.post("/api/v1/tools/analyze_payment_patterns", json={
                "case_id": case_id,
                "entity_id": "ACC_100",
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["has_circular_patterns"] is True


# =============================================================================
# 5. Tool: search_financial_history
# =============================================================================
@pytest.mark.asyncio
async def test_tool_search_financial_history():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Query account 0
            resp = await client.post("/api/v1/tools/financial-history", json={
                "account_id": "0",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["account_id"] == "0"
            assert data["account_details"] is not None
            assert data["party_details"] is not None or data["owner_name"] is not None

            # Test alias with party_id
            resp_alias = await client.post("/api/v1/tools/search_financial_history", json={
                "party_id": "0",
            })
            assert resp_alias.status_code == 200
            data_alias = resp_alias.json()
            assert data_alias["party_id"] == "0"


# =============================================================================
# 6. Tool: get_cashout
# =============================================================================
@pytest.mark.asyncio
async def test_tool_get_cashout():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tools/cashout", json={
                "account_id": "0",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["account_id"] == "0"
            assert data["total_cashouts"] >= 1
            assert data["total_amount"] > 0.0

            # Test alias
            resp_alias = await client.post("/api/v1/tools/get_cashout", json={
                "account_id": "0",
                "min_amount": 50.0,
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["total_cashouts"] >= 1


# =============================================================================
# 7. Tool: trace_money_flow
# =============================================================================
@pytest.mark.asyncio
async def test_tool_trace_money_flow():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Trace from CORP_X to DEST_Z
            resp = await client.post("/api/v1/tools/trace-money-flow", json={
                "source_account": "CORP_X",
                "destination_account": "DEST_Z",
                "case_id": case_id,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_paths"] >= 1
            path_nodes = data["paths"][0]["path"]
            assert path_nodes == ["CORP_X", "MULE_Y", "DEST_Z"]

            # Test alias
            resp_alias = await client.post("/api/v1/tools/trace_money_flow", json={
                "source_account": "ACC_100",
                "case_id": case_id,
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["total_paths"] >= 1


# =============================================================================
# 8. Tool: find_related_transactions
# =============================================================================
@pytest.mark.asyncio
async def test_tool_find_related_transactions():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Query transactions first to get a real ID
            txs_resp = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            core_tx_id = txs_resp.json()["items"][0]["id"]

            resp = await client.post("/api/v1/tools/related-transactions", json={
                "transaction_id": core_tx_id,
                "case_id": case_id,
                "hops": 2,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["transaction_id"] == core_tx_id
            assert data["results"]["direct_transaction"] is not None
            assert data["results"]["total_secondary"] >= 1

            # Test alias
            resp_alias = await client.post("/api/v1/tools/find_related_transactions", json={
                "transaction_id": core_tx_id,
                "case_id": case_id,
            })
            assert resp_alias.status_code == 200


# =============================================================================
# 9. Tool: find_transaction_chains
# =============================================================================
@pytest.mark.asyncio
async def test_tool_find_transaction_chains():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # Path with mule: CORP_X -> MULE_Y -> DEST_Z
            resp = await client.post("/api/v1/tools/transaction-chains", json={
                "source_account": "CORP_X",
                "destination_account": "DEST_Z",
                "case_id": case_id,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_chains"] >= 1
            chain = data["chains"][0]
            assert "MULE_Y" in chain["intermediaries"]
            assert chain["length"] == 2

            # Test alias
            resp_alias = await client.post("/api/v1/tools/find_transaction_chains", json={
                "source_account": "CORP_X",
                "destination_account": "DEST_Z",
                "case_id": case_id,
            })
            assert resp_alias.status_code == 200


# =============================================================================
# 10. Tool: find_shared_entities
# =============================================================================
@pytest.mark.asyncio
async def test_tool_find_shared_entities():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # SHARED_A -> SHARED_C -> SHARED_D and SHARED_B -> SHARED_C -> SHARED_D
            resp = await client.post("/api/v1/tools/shared-entities", json={
                "case_id": case_id,
                "min_shared_hops": 2,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_shared_pairs"] >= 1
            pair = data["items"][0]
            assert "SHARED_A" in pair["entities"] and "SHARED_B" in pair["entities"]
            assert pair["common_target_sequence"] == ["SHARED_C", "SHARED_D"]

            # Test alias
            resp_alias = await client.post("/api/v1/tools/find_shared_entities", json={
                "case_id": case_id,
            })
            assert resp_alias.status_code == 200


# =============================================================================
# 11. Tool: detect_circular_flow
# =============================================================================
@pytest.mark.asyncio
async def test_tool_detect_circular_flow():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            resp = await client.post("/api/v1/tools/circular-flow", json={
                "case_id": case_id,
                "max_cycle_length": 5,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_cycles"] >= 1
            assert data["total_cyclical_volume"] > 0.0

            # Test alias with entity filter
            resp_alias = await client.post("/api/v1/tools/detect_circular_flow", json={
                "case_id": case_id,
                "entity_id": "ACC_100",
            })
            assert resp_alias.status_code == 200
            assert resp_alias.json()["total_cycles"] >= 1


# =============================================================================
# 12. Dynamic Query Tool: Core Banking Targets (accounts, parties, cash_tx)
# =============================================================================
@pytest.mark.asyncio
async def test_dynamic_query_banking_targets():
    async with setup_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Query accounts
            resp_acct = await client.post("/api/v1/tools/query", json={
                "target": "accounts",
                "filters": [{"field": "acct_id", "operator": "eq", "value": "0"}],
            })
            assert resp_acct.status_code == 200
            assert resp_acct.json()["total"] >= 1

            # Query parties
            resp_party = await client.post("/api/v1/tools/query", json={
                "target": "parties",
                "filters": [{"field": "party_id", "operator": "eq", "value": "0"}],
            })
            assert resp_party.status_code == 200
            assert resp_party.json()["total"] >= 1

            # Query cash_transactions
            resp_cash = await client.post("/api/v1/tools/query", json={
                "target": "cash_transactions",
                "filters": [{"field": "account_id", "operator": "eq", "value": "0"}],
            })
            assert resp_cash.status_code == 200
            assert resp_cash.json()["total"] >= 1

