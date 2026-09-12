"""
Challenger 2 Empirical Adversarial Test Suite for Milestone 3.
Thoroughly stress-tests the 4 dedicated endpoints:
1. /api/v1/tools/transactions: Complex compound filters, boundary ranges, zero matches, pagination.
2. /api/v1/tools/entities: Zero in/out transactions, unknown entity IDs, high-degree nodes, risk sorting.
3. /api/v1/tools/patterns: No patterns vs dense cycles, mule thresholding, length bounds.
4. /api/v1/tools/legal-precedents: Custom 1536d query vectors, dimension validation, top_k ranking, keyword fallback.

Tests both Database mode (SQLAlchemy AsyncSession) and In-Memory fallback mode.
"""

import contextlib
from datetime import datetime, timezone
from decimal import Decimal
import math
import uuid
import httpx
import pytest

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.core.config import settings
from backend.core.database import close_db, get_session_factory, init_db
from backend.main import app
from backend.models.forensic import (
    InvestigationCase,
    LegalArticleVector,
    SEED_LEGAL_PRECEDENTS,
    TransactionRecord,
    generate_deterministic_embedding,
    seed_legal_knowledge,
)
from backend.schemas.agent_tools import PatternType


@contextlib.asynccontextmanager
async def isolated_test_db():
    """Configures isolated test database with seeded legal knowledge and clean in-memory state."""
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


# =============================================================================
# Helper: Seed Complex Case with Varied Entities, Transactions, and Patterns
# =============================================================================
async def create_complex_test_case(db_mode: bool = True) -> str:
    """
    Creates an investigation case with:
    - Multiple transactions with varying origin, destination, amounts, timestamps, and suspicion flags.
    - Zero in/out isolated node.
    - High-degree hub node (50 incoming, 30 outgoing counterparties).
    - Dense cycles (lengths 2, 3, 4, 5 with distinct volumes).
    - Multiple pass-through accounts (various turnover ratios).
    """
    case_uuid = uuid.uuid4()
    case_id_str = str(case_uuid)

    # 1. High-degree hub node counterparties
    in_senders = [f"IN_SENDER_{i:02d}" for i in range(50)]
    out_receivers = [f"OUT_RECEIVER_{i:02d}" for i in range(30)]

    edges = []
    transactions = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Hub incoming transactions
    for idx, s in enumerate(in_senders):
        amt = 10000.0 + idx * 500.0
        tx_id = str(uuid.uuid4())
        edges.append({
            "source": s,
            "target": "HUB_ACCOUNT",
            "amount": amt,
            "timestamps": [now_iso],
            "reasons": ["high_degree_inflow"] if idx % 2 == 0 else [],
        })
        transactions.append({
            "id": tx_id,
            "case_id": case_id_str,
            "origin": s,
            "destination": "HUB_ACCOUNT",
            "amount": amt,
            "timestamp": now_iso,
            "is_suspicious": (idx % 2 == 0),
            "reasons": ["high_degree_inflow"] if idx % 2 == 0 else [],
        })

    # Hub outgoing transactions
    for idx, r in enumerate(out_receivers):
        amt = 15000.0 + idx * 400.0
        tx_id = str(uuid.uuid4())
        edges.append({
            "source": "HUB_ACCOUNT",
            "target": r,
            "amount": amt,
            "timestamps": [now_iso],
            "reasons": ["high_degree_outflow"] if idx % 3 == 0 else [],
        })
        transactions.append({
            "id": tx_id,
            "case_id": case_id_str,
            "origin": "HUB_ACCOUNT",
            "destination": r,
            "amount": amt,
            "timestamp": now_iso,
            "is_suspicious": (idx % 3 == 0),
            "reasons": ["high_degree_outflow"] if idx % 3 == 0 else [],
        })

    # Additional transactions for compound filter testing
    special_txs = [
        ("ACC_ALPHA", "ACC_BETA", 150000.0, True, ["round_trip_layering"]),
        ("ACC_ALPHA", "ACC_GAMMA", 25000.0, False, []),
        ("ACC_ALPHA", "ACC_DELTA", 350000.0, True, ["structuring_smurf"]),
        ("ACC_BETA", "ACC_ALPHA", 149000.0, True, ["circular_return"]),
        ("LEGIT_CORP", "RETAIL_01", 500.0, False, []),
    ]
    for orig, dest, amt, is_susp, reasons in special_txs:
        tx_id = str(uuid.uuid4())
        edges.append({
            "source": orig,
            "target": dest,
            "amount": amt,
            "timestamps": [now_iso],
            "reasons": reasons,
        })
        transactions.append({
            "id": tx_id,
            "case_id": case_id_str,
            "origin": orig,
            "destination": dest,
            "amount": amt,
            "timestamp": now_iso,
            "is_suspicious": is_susp,
            "reasons": reasons,
        })

    # Nodes: isolated node + hub node + alpha/beta/gamma nodes
    nodes = [
        {
            "id": "ISOLATED_NODE_0",
            "in_degree": 0,
            "out_degree": 0,
            "total_in": 0.0,
            "total_out": 0.0,
            "risk_score": 0.0,
            "reasons": [],
        },
        {
            "id": "HUB_ACCOUNT",
            "in_degree": 50,
            "out_degree": 30,
            "total_in": sum(10000.0 + i * 500.0 for i in range(50)),
            "total_out": sum(15000.0 + i * 400.0 for i in range(30)),
            "risk_score": 0.95,
            "reasons": ["super_hub_node", "extreme_counterparty_degree"],
        },
        {
            "id": "ACC_ALPHA",
            "in_degree": 1,
            "out_degree": 3,
            "total_in": 149000.0,
            "total_out": 525000.0,
            "risk_score": 0.85,
            "reasons": ["layering_initiator"],
        },
        {
            "id": "ACC_BETA",
            "in_degree": 1,
            "out_degree": 1,
            "total_in": 150000.0,
            "total_out": 149000.0,
            "risk_score": 0.92,
            "reasons": ["cycle_intermediate"],
        },
    ]

    # Patterns: Dense cycles of varying lengths and pass-through accounts
    patterns = {
        "cycles": [
            {"path": ["ACC_ALPHA", "ACC_BETA", "ACC_ALPHA"], "length": 2, "estimated_volume": 500000.0},
            {"path": ["C3_A", "C3_B", "C3_C", "C3_A"], "length": 3, "estimated_volume": 100000.0},
            {"path": ["C4_A", "C4_B", "C4_C", "C4_D", "C4_A"], "length": 4, "estimated_volume": 250000.0},
            {"path": ["C5_A", "C5_B", "C5_C", "C5_D", "C5_E", "C5_A"], "length": 5, "estimated_volume": 50000.0},
        ],
        "passthrough_accounts": [
            {"account_id": "MULE_RAPID_01", "inflow": 400000.0, "outflow": 395000.0, "ratio": 0.9875, "window_hours": 12.0},
            {"account_id": "MULE_HIGH_02", "inflow": 600000.0, "outflow": 594000.0, "ratio": 0.9900, "window_hours": 8.0},
            {"account_id": "MULE_MODERATE_03", "inflow": 200000.0, "outflow": 184000.0, "ratio": 0.9200, "window_hours": 36.0},
            {"account_id": "NORMAL_TURNOVER_04", "inflow": 100000.0, "outflow": 85000.0, "ratio": 0.8500, "window_hours": 48.0},
        ],
    }

    subgraph = {
        "nodes": nodes,
        "edges": edges,
    }

    if db_mode:
        factory = get_session_factory()
        async with factory() as session:
            case = InvestigationCase(
                id=case_uuid,
                filename="complex_test_case.csv",
                status="COMPLETED",
                ingestion_metadata={"rows": len(transactions)},
                metrics={"total_nodes": len(nodes), "total_edges": len(edges)},
                subgraph=subgraph,
                patterns=patterns,
            )
            session.add(case)

            for t in transactions:
                tx_record = TransactionRecord(
                    id=uuid.UUID(t["id"]),
                    case_id=case_uuid,
                    origin=t["origin"],
                    destination=t["destination"],
                    amount=Decimal(str(t["amount"])),
                    timestamp=datetime.fromisoformat(t["timestamp"]),
                    is_suspicious=t["is_suspicious"],
                    reasons=t["reasons"],
                )
                session.add(tx_record)
            await session.commit()
    else:
        # In-memory storage dictionary
        INVESTIGATION_CASES[case_id_str] = {
            "id": case_id_str,
            "filename": "complex_test_case.csv",
            "status": "COMPLETED",
            "subgraph": subgraph,
            "patterns": patterns,
            "transactions": transactions,
        }

    return case_id_str


async def create_empty_patterns_case(db_mode: bool = True) -> str:
    """Creates a case with strictly no cycles and no pass-through accounts."""
    case_uuid = uuid.uuid4()
    case_id_str = str(case_uuid)
    subgraph = {
        "nodes": [{"id": "NODE_A", "total_in": 1000.0, "total_out": 0.0, "risk_score": 0.1, "reasons": []}],
        "edges": [],
    }
    patterns = {"cycles": [], "passthrough_accounts": []}

    if db_mode:
        factory = get_session_factory()
        async with factory() as session:
            case = InvestigationCase(
                id=case_uuid,
                filename="empty_patterns_case.csv",
                status="COMPLETED",
                subgraph=subgraph,
                patterns=patterns,
            )
            session.add(case)
            await session.commit()
    else:
        INVESTIGATION_CASES[case_id_str] = {
            "id": case_id_str,
            "filename": "empty_patterns_case.csv",
            "status": "COMPLETED",
            "subgraph": subgraph,
            "patterns": patterns,
            "transactions": [],
        }

    return case_id_str


# =============================================================================
# 1. Empirical Challenge: /tools/transactions
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_transactions_compound_filters_db():
    """
    Empirical Challenge on /tools/transactions (DB mode):
    Compound filters combining:
    - origin + min_amount + is_suspicious
    - destination + max_amount + is_suspicious
    - zero match combination
    - inverted bounds validation
    """
    async with isolated_test_db():
        case_id = await create_complex_test_case(db_mode=True)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Compound filter: origin="ACC_ALPHA", min_amount=100000.0, is_suspicious=True
            # Matches ACC_ALPHA -> ACC_BETA (150k, True) and ACC_ALPHA -> ACC_DELTA (350k, True)
            # Should NOT match ACC_ALPHA -> ACC_GAMMA (25k, False)
            resp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "origin": "ACC_ALPHA",
                "min_amount": 100000.0,
                "is_suspicious": True,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            assert data["total_volume_mxn"] == 500000.0
            for item in data["items"]:
                assert item["origin"] == "ACC_ALPHA"
                assert item["amount"] >= 100000.0
                assert item["is_suspicious"] is True

            # 2. Compound filter: destination="ACC_DELTA", max_amount=400000.0, is_suspicious=True
            resp2 = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "destination": "ACC_DELTA",
                "max_amount": 400000.0,
                "is_suspicious": True,
            })
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["total"] == 1
            assert data2["items"][0]["destination"] == "ACC_DELTA"
            assert data2["items"][0]["amount"] == 350000.0

            # 3. Compound filter yielding zero matches: origin="ACC_ALPHA", min_amount=9999999.0, is_suspicious=True
            resp3 = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "origin": "ACC_ALPHA",
                "min_amount": 9999999.0,
                "is_suspicious": True,
            })
            assert resp3.status_code == 200
            data3 = resp3.json()
            assert data3["total"] == 0
            assert data3["total_volume_mxn"] == 0.0
            assert len(data3["items"]) == 0

            # 4. Pagination slicing on compound filters
            # Hub incoming suspicious transactions: 25 of them (every even idx out of 50)
            resp_page = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "destination": "HUB_ACCOUNT",
                "is_suspicious": True,
                "limit": 5,
                "offset": 0,
            })
            assert resp_page.status_code == 200
            data_page = resp_page.json()
            assert data_page["total"] == 25
            assert len(data_page["items"]) == 5
            assert data_page["limit"] == 5
            assert data_page["offset"] == 0

            # 5. Inverted bounds validation (min_amount > max_amount) -> 422
            resp_inv = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "min_amount": 500000.0,
                "max_amount": 100000.0,
            })
            assert resp_inv.status_code == 422


@pytest.mark.asyncio
async def test_challenge_transactions_compound_filters_in_memory():
    """
    Empirical Challenge on /tools/transactions (In-Memory fallback mode):
    Ensures feature parity when database dependency is not available.
    """
    settings.DATABASE_URL = "unconfigured"
    INVESTIGATION_CASES.clear()

    try:
        case_id = await create_complex_test_case(db_mode=False)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tools/transactions", json={
                "case_id": case_id,
                "origin": "ACC_ALPHA",
                "min_amount": 100000.0,
                "is_suspicious": True,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert data["total_volume_mxn"] == 500000.0
            assert len(data["items"]) == 2
    finally:
        INVESTIGATION_CASES.clear()


# =============================================================================
# 2. Empirical Challenge: /tools/entities
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_entities_profiling_edge_topologies_db():
    """
    Empirical Challenge on /tools/entities (DB mode):
    - Zero in/out transactions (isolated node: ISOLATED_NODE_0).
    - Unknown entity ID (returns HTTP 404 with descriptive detail).
    - High-degree super-hub node (50 incoming, 30 outgoing counterparties).
    - Risk score filtering and descending sort.
    """
    async with isolated_test_db():
        case_id = await create_complex_test_case(db_mode=True)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Zero in/out transactions: ISOLATED_NODE_0
            resp_iso = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "ISOLATED_NODE_0",
            })
            assert resp_iso.status_code == 200
            data_iso = resp_iso.json()
            assert data_iso["total_entities"] == 1
            node_iso = data_iso["entities"][0]
            assert node_iso["entity_id"] == "ISOLATED_NODE_0"
            assert node_iso["in_degree"] == 0
            assert node_iso["out_degree"] == 0
            assert node_iso["total_inflow"] == 0.0
            assert node_iso["total_outflow"] == 0.0
            assert node_iso["net_flow"] == 0.0
            assert node_iso["risk_score"] == 0.0
            assert node_iso["is_suspicious"] is False
            assert node_iso["counterparties_in"] == []
            assert node_iso["counterparties_out"] == []

            # 2. Unknown entity ID -> HTTP 404
            resp_unk = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "UNKNOWN_ACCOUNT_99999",
            })
            assert resp_unk.status_code == 404
            assert "UNKNOWN_ACCOUNT_99999" in resp_unk.json()["detail"]

            # 3. High-degree super-hub node: HUB_ACCOUNT
            resp_hub = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "HUB_ACCOUNT",
            })
            assert resp_hub.status_code == 200
            data_hub = resp_hub.json()
            node_hub = data_hub["entities"][0]
            assert node_hub["entity_id"] == "HUB_ACCOUNT"
            assert node_hub["in_degree"] == 50
            assert node_hub["out_degree"] == 30
            assert len(node_hub["counterparties_in"]) == 50
            assert len(node_hub["counterparties_out"]) == 30
            # Alphabetically sorted counterparties
            assert node_hub["counterparties_in"] == sorted(node_hub["counterparties_in"])
            assert node_hub["counterparties_out"] == sorted(node_hub["counterparties_out"])
            # Inflow / Outflow arithmetic
            expected_in = sum(10000.0 + i * 500.0 for i in range(50))
            expected_out = sum(15000.0 + i * 400.0 for i in range(30))
            assert node_hub["total_inflow"] == expected_in
            assert node_hub["total_outflow"] == expected_out
            assert node_hub["net_flow"] == round(expected_in - expected_out, 2)
            assert node_hub["risk_score"] == 0.95
            assert node_hub["is_suspicious"] is True

            # 4. Filter by min_risk_score=0.8 and check descending sorting
            resp_filt = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "min_risk_score": 0.8,
            })
            assert resp_filt.status_code == 200
            data_filt = resp_filt.json()
            entities = data_filt["entities"]
            assert len(entities) >= 3  # HUB_ACCOUNT (0.95), ACC_BETA (0.92), ACC_ALPHA (0.85)
            # Strictly descending by risk_score
            scores = [e["risk_score"] for e in entities]
            assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_challenge_entities_profiling_in_memory():
    """
    Empirical Challenge on /tools/entities (In-Memory fallback mode):
    Verifies isolated nodes, hub nodes, and 404 unknown entity handling.
    """
    settings.DATABASE_URL = "unconfigured"
    INVESTIGATION_CASES.clear()

    try:
        case_id = await create_complex_test_case(db_mode=False)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp_iso = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "ISOLATED_NODE_0",
            })
            assert resp_iso.status_code == 200
            assert resp_iso.json()["entities"][0]["in_degree"] == 0

            resp_hub = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "HUB_ACCOUNT",
            })
            assert resp_hub.status_code == 200
            assert resp_hub.json()["entities"][0]["in_degree"] == 50

            resp_unk = await client.post("/api/v1/tools/entities", json={
                "case_id": case_id,
                "entity_id": "UNKNOWN_NOT_FOUND",
            })
            assert resp_unk.status_code == 404
    finally:
        INVESTIGATION_CASES.clear()


# =============================================================================
# 3. Empirical Challenge: /tools/patterns
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_patterns_empty_vs_dense_cycles_db():
    """
    Empirical Challenge on /tools/patterns (DB mode):
    - Case with NO patterns -> clean zero counts, empty lists, HTTP 200.
    - Case with DENSE cycles -> min_cycle_length, max_cycle_length, min_volume.
    - Pass-through mule thresholding -> min_passthrough_ratio, min_volume.
    - Inverted bounds validation -> HTTP 422.
    """
    async with isolated_test_db():
        case_empty = await create_empty_patterns_case(db_mode=True)
        case_dense = await create_complex_test_case(db_mode=True)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. No patterns case:
            resp_empty = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_empty,
                "pattern_type": "all",
            })
            assert resp_empty.status_code == 200
            data_empty = resp_empty.json()
            assert data_empty["total_cycles_count"] == 0
            assert data_empty["total_mules_count"] == 0
            assert data_empty["cycles"] == []
            assert data_empty["passthrough_mules"] == []

            # 2. Dense cycles case: all patterns
            resp_dense = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "pattern_type": "all",
            })
            assert resp_dense.status_code == 200
            data_dense = resp_dense.json()
            assert data_dense["total_cycles_count"] == 4
            assert data_dense["total_mules_count"] == 4

            # 3. Filter by pattern_type="cycles" and min_cycle_length=4
            # Dense cycles has lengths: [2, 3, 4, 5]. Lengths >= 4 are 4 and 5 (2 cycles).
            resp_c4 = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "pattern_type": "cycles",
                "min_cycle_length": 4,
            })
            assert resp_c4.status_code == 200
            data_c4 = resp_c4.json()
            assert data_c4["total_cycles_count"] == 2
            assert data_c4["total_mules_count"] == 0
            assert all(c["length"] >= 4 for c in data_c4["cycles"])

            # 4. Filter by max_cycle_length=3 and min_volume=150000.0
            # Lengths <= 3: length 2 (vol 500k), length 3 (vol 100k).
            # min_volume >= 150k keeps only length 2 (vol 500k).
            resp_c_vol = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "pattern_type": "cycles",
                "max_cycle_length": 3,
                "min_volume": 150000.0,
            })
            assert resp_c_vol.status_code == 200
            data_c_vol = resp_c_vol.json()
            assert data_c_vol["total_cycles_count"] == 1
            assert data_c_vol["cycles"][0]["length"] == 2
            assert data_c_vol["cycles"][0]["estimated_volume"] == 500000.0

            # 5. Filter pass-through mules: min_passthrough_ratio=0.95
            # Mules ratios: 0.9875, 0.9900, 0.9200, 0.8500. Ratios >= 0.95: 2 mules.
            resp_mules = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "pattern_type": "passthrough_mules",
                "min_passthrough_ratio": 0.95,
            })
            assert resp_mules.status_code == 200
            data_mules = resp_mules.json()
            assert data_mules["total_mules_count"] == 2
            assert data_mules["total_cycles_count"] == 0
            assert all(m["ratio"] >= 0.95 for m in data_mules["passthrough_mules"])

            # 6. Inverted bounds validation: min_cycle_length > max_cycle_length -> 422
            resp_inv = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "min_cycle_length": 5,
                "max_cycle_length": 3,
            })
            assert resp_inv.status_code == 422


@pytest.mark.asyncio
async def test_challenge_patterns_in_memory():
    """
    Empirical Challenge on /tools/patterns (In-Memory fallback mode):
    Verifies pattern extraction and filtering parity.
    """
    settings.DATABASE_URL = "unconfigured"
    INVESTIGATION_CASES.clear()

    try:
        case_dense = await create_complex_test_case(db_mode=False)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/v1/tools/patterns", json={
                "case_id": case_dense,
                "pattern_type": "cycles",
                "min_cycle_length": 4,
            })
            assert resp.status_code == 200
            assert resp.json()["total_cycles_count"] == 2
    finally:
        INVESTIGATION_CASES.clear()


# =============================================================================
# 4. Empirical Challenge: /tools/legal-precedents
# =============================================================================

@pytest.mark.asyncio
async def test_challenge_legal_precedents_custom_vector_and_ranking_db():
    """
    Empirical Challenge on /tools/legal-precedents (DB mode):
    - Exact match custom 1536d query vector (similarity ~ 1.0, distance = 0.0).
    - Inverted query vector (similarity ~ -1.0).
    - Top-k ranking verification (top_k=1, top_k=3, strictly monotonic descending similarity).
    - Dimension validation (vector length != 1536 -> HTTP 422).
    - Keyword fallback (query_text without query_vector).
    - Law name filter and similarity thresholding.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Exact match with CFF-ART-69B content embedding
            cff_content = SEED_LEGAL_PRECEDENTS[0]["content"]
            exact_vector = generate_deterministic_embedding(cff_content, dim=1536)

            resp_exact = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "Search CFF 69B exact",
                "query_vector": exact_vector,
                "top_k": 3,
            })
            assert resp_exact.status_code == 200
            data_exact = resp_exact.json()
            assert data_exact["top_k"] == 3
            assert len(data_exact["results"]) >= 1
            top_match = data_exact["results"][0]
            assert top_match["article_code"] == "CFF-ART-69B"
            assert top_match["similarity_score"] >= 0.9999
            assert top_match["distance"] <= 0.0001

            # 2. Inverted vector (-1 * exact_vector)
            inverted_vector = [-x for x in exact_vector]
            resp_inv = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "Search inverted",
                "query_vector": inverted_vector,
                "top_k": 6,
                "similarity_threshold": -1.0,
            })
            assert resp_inv.status_code == 200
            data_inv = resp_inv.json()
            # The lowest similarity for CFF-ART-69B should be -1.0, ranked dead last
            cff_matches = [r for r in data_inv["results"] if r["article_code"] == "CFF-ART-69B"]
            assert len(cff_matches) == 1
            assert cff_matches[0]["similarity_score"] <= -0.9999
            assert data_inv["results"][-1]["article_code"] == "CFF-ART-69B"

            # 3. Dimension validation: query_vector of 10 dimensions -> 422
            resp_dim = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "Invalid dimensions",
                "query_vector": [0.1] * 10,
            })
            assert resp_dim.status_code == 422

            # 4. Top-K limit and Monotonic Descending Order
            resp_top = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "operaciones simuladas facturacion empresas fantasma sat",
                "top_k": 5,
                "similarity_threshold": -1.0,
            })
            assert resp_top.status_code == 200
            data_top = resp_top.json()
            results = data_top["results"]
            assert len(results) <= 5
            # Verify monotonic descending order
            for i in range(len(results) - 1):
                assert results[i]["similarity_score"] >= results[i + 1]["similarity_score"]

            # 5. Query text fallback without query_vector
            # 5a. Exact text match yields 1.0 similarity via deterministic embedding
            resp_exact_text = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": cff_content,
                "top_k": 3,
            })
            assert resp_exact_text.status_code == 200
            data_exact_text = resp_exact_text.json()
            assert data_exact_text["results"][0]["article_code"] == "CFF-ART-69B"
            assert data_exact_text["results"][0]["similarity_score"] >= 0.9999

            # 5b. Natural language keywords without query_vector (generates deterministic vector)
            resp_kw = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "reporte de operacion inusual 24 horas transferencias estructuracion",
                "top_k": 3,
                "similarity_threshold": -1.0,
            })
            assert resp_kw.status_code == 200
            data_kw = resp_kw.json()
            assert data_kw["total_matches"] > 0
            assert len(data_kw["results"]) == 3
            for r in data_kw["results"]:
                assert "article_code" in r
                assert "similarity_score" in r
                assert "content" in r

            # 6. Law name filter
            resp_filter = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "operaciones lavado de dinero",
                "law_name_filter": "Código Fiscal",
                "top_k": 5,
            })
            assert resp_filter.status_code == 200
            data_filter = resp_filter.json()
            for r in data_filter["results"]:
                assert "Código Fiscal" in r["law_name"]

            # 7. Non-existent law filter -> 0 matches
            resp_none = await client.post("/api/v1/tools/legal-precedents", json={
                "query_text": "operaciones",
                "law_name_filter": "NON_EXISTENT_LEGAL_STATUTE",
            })
            assert resp_none.status_code == 200
            assert resp_none.json()["total_matches"] == 0
            assert len(resp_none.json()["results"]) == 0


@pytest.mark.asyncio
async def test_challenge_legal_precedents_in_memory():
    """
    Empirical Challenge on /tools/legal-precedents (In-Memory fallback mode):
    Verifies vector cosine dot product, top_k ranking, and keyword search fallback.
    """
    settings.DATABASE_URL = "unconfigured"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        cff_content = SEED_LEGAL_PRECEDENTS[0]["content"]
        exact_vector = generate_deterministic_embedding(cff_content, dim=1536)

        resp = await client.post("/api/v1/tools/legal-precedents", json={
            "query_text": "In-memory test exact CFF",
            "query_vector": exact_vector,
            "top_k": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["article_code"] == "CFF-ART-69B"
        assert data["results"][0]["similarity_score"] >= 0.9999

        # Keyword fallback
        resp_kw = await client.post("/api/v1/tools/legal-precedents", json={
            "query_text": "sustancia economica triada probatoria",
            "top_k": 2,
        })
        assert resp_kw.status_code == 200
        assert len(resp_kw.json()["results"]) > 0
