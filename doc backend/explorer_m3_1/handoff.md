# Handoff Report: Milestone 3 Dedicated Tool Endpoints & Scalable Query Interface

**Agent**: `explorer_m3_1`  
**Milestone**: M3 (Dedicated Tool Endpoints Implementation & Query Interface)  
**Date**: 2026-09-12  
**Handoff Type**: Hard Handoff (Exploration Complete)  

---

## 1. Observation

1. **Existing Baseline Implementation**:
   - `backend/models/forensic.py`:
     - Lines 53-95: `InvestigationCase` defines UUID primary key, `metrics` (JSON_DOCUMENT), `subgraph` (JSON_DOCUMENT), `patterns` (JSON_DOCUMENT), and relationship to `TransactionRecord`.
     - Lines 97-124: `TransactionRecord` defines `case_id` (ForeignKey with index), `origin`, `destination`, `amount` (Numeric 18,2), `timestamp`, `is_suspicious` (Boolean index), `reasons` (JSON_DOCUMENT).
     - Lines 126-150: `LegalArticleVector` defines `article_code`, `law_name`, `content`, `embedding` (`Vector(1536)` with HNSW cosine index `idx_legal_vectors_hnsw`).
     - Lines 155-176: `generate_deterministic_embedding(text: str, dim: int = 1536) -> List[float]` produces unit-normalized 1536-D vectors via SHA-256 digest hashing.
     - Lines 178-323: `SEED_LEGAL_PRECEDENTS` contains 6 foundational Mexican AML statutes (`CFF-ART-69B`, `NIF-A2-MATERIALIDAD`, `UIF-ROI-24H`, `UIF-ROR-7500USD`, `LIC-ART-115-BLOQUEO`, `CPF-ART-400BIS`).
   - `backend/api/routes/investigations.py`:
     - Line 33: `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}` provides in-memory fallback cache.
     - Lines 36-61: `get_optional_db()` dependency yields `AsyncSession` when configured, or `None` for offline / in-memory mode.
     - Lines 181-228: Ingestion extracts `subgraph` nodes and edges with suspicion reasons (`CYCLE_STEP`, `PASSTHROUGH_BRIDGE`), persisting `TransactionRecord` rows.
   - `backend/main.py`:
     - Lines 57-60: Router registration currently registers `investigations_router` and `tts_router`. `agent_tools_router` needs to be created and registered with `prefix=settings.API_V1_STR`.
2. **Test Suite Baseline**:
   - Executed `python -m pytest backend/tests/ -v`.
   - Result: `35 passed in 14.22s` with 0 failures and 0 warnings.
3. **Database Dialect Discrepancy**:
   - Production database is TigerData PostgreSQL with pgvector extension (`<=>` cosine distance operator).
   - Test fixture uses SQLite in-memory (`sqlite+aiosqlite:///:memory:`). In `models/forensic.py` line 36-38, `@compiles(Vector, "sqlite")` converts `Vector` to `TEXT`.
   - Executing `LegalArticleVector.embedding.cosine_distance(...)` in SQLite results in an SQL compilation error because SQLite has no native cosine distance operator. The endpoint must branch on dialect: native pgvector for PostgreSQL, in-memory dot-product calculation for SQLite.

---

## 2. Logic Chain

1. *From Requirement R3 (`ORIGINAL_REQUEST.md`, lines 31-41)*:
   - Dedicated tool endpoints must be provided for external n8n AI agent workflows:
     - `POST /api/v1/tools/transactions`
     - `POST /api/v1/tools/entities`
     - `POST /api/v1/tools/patterns`
     - `POST /api/v1/tools/legal-precedents`
   - A dynamic query builder `POST /api/v1/tools/query` with an extensible `ToolRegistry` must allow composable querying with strict column whitelisting and parameterized SQL.
2. *From Database Architecture (`backend/models/forensic.py` & `core/database.py`)*:
   - Queries against `TransactionRecord` can be directly filtered using SQLAlchemy 2.0 expressions with mandatory `case_id` scoping to prevent multi-tenant cross-case leakage.
   - Entity metrics can be derived from `InvestigationCase.subgraph["nodes"]` (which contains NetworkX cycle and pass-through scores) with fallback to aggregating `TransactionRecord` rows for benign accounts that were pruned.
   - Patterns can be cleanly retrieved from `InvestigationCase.patterns` and filtered by hop length, ratio, or account.
   - Legal precedents vector search can execute native HNSW cosine distance (`distance_expr = LegalArticleVector.embedding.cosine_distance(target_vector)`) on PostgreSQL, while seamlessly computing Python dot-products in SQLite test environments.
3. *From Offline Fallback Architecture*:
   - To support demo mode and unconfigured `DATABASE_URL`, all 4 endpoints must inspect `INVESTIGATION_CASES` if `db is None`.
   - If `query_text` is provided without `query_vector`, the endpoint invokes `generate_deterministic_embedding(query_text)` to dynamically compute the query vector, while also applying keyword matching as fallback.
4. *From Integrity Mode (`Integrity mode: demo`)*:
   - No mock bypasses or hardcoded static responses are permitted. All outputs are computed dynamically from the database or in-memory case state.

---

## 3. Caveats

1. **Transaction Storage in `INVESTIGATION_CASES`**: Currently, `investigations.py` does not explicitly store non-suspicious `TransactionRecord` rows in `INVESTIGATION_CASES[case_id]`. For full offline parity, the transactions endpoint should fall back to synthesizing records from `subgraph["edges"]` when `transactions` is not found, and the worker implementing M3 can also enrich `case_record["transactions"]` during upload.
2. **Vector Dimension**: The legal vector index is configured for 1536 dimensions. Any passed `query_vector` must match 1536 dimensions; when `query_text` is supplied, `generate_deterministic_embedding(query_text, dim=1536)` guarantees this match.

---

## 4. Conclusion

The technical specification, SQL queries, Pydantic contracts, and dual fallback mechanisms for Milestone 3 are fully designed and documented in `.agents/explorer_m3_1/analysis.md`. The implementation requires creating:
1. `backend/schemas/agent_tools.py`: Request/response models.
2. `backend/api/routes/agent_tools.py`: 4 dedicated endpoints, dynamic `/query` endpoint, and `ToolRegistry`.
3. Registering the router in `backend/main.py`.
4. `backend/tests/test_agent_tools.py`: Unit and integration tests validating all endpoints in both database and offline modes.

---

## 5. Verification Method

To independently verify the exploration and findings:

1. **Verify Baseline Test Suite**:
   ```powershell
   python -m pytest backend/tests/ -v
   ```
   *Expected*: All 35 tests pass.

2. **Inspect Specifications & Schemas**:
   Inspect `.agents/explorer_m3_1/analysis.md` for the complete contracts and query implementations.
