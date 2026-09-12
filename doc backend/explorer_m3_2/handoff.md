# Milestone 3 Handoff Report: Dynamic Tool Registry & Query Builder Pattern

**Agent**: explorer_m3_2  
**Role**: Explorer / Architectural Analyst (Milestone 3)  
**Parent**: aa7bce53-1d36-4848-bf78-a047dfb94d28  
**Working Directory**: `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m3_2`  
**Handoff Type**: Hard (Investigation complete and self-contained)  

---

## 1. Observation

### 1.1 Requirements & Specifications
- **`ORIGINAL_REQUEST.md` (Lines 31–41, §R3)**:
  > "Create an extensible, versioned agent tool router in `backend/api/routes/agent_tools.py` (registered in `backend/main.py`) to support current and future n8n AI agent tools without requiring backend schema alterations:
  > - **Dedicated Tool Endpoints**: `POST /api/v1/tools/transactions`, `POST /api/v1/tools/entities`, `POST /api/v1/tools/patterns`, `POST /api/v1/tools/legal-precedents`.
  > - **Dynamic Tool Registry & Query Builder**: `POST /api/v1/tools/query`: dynamic, composable query endpoint accepting structured JSON criteria (entity target, field filters, sort, limit) that safely builds and executes queries against case data. Extensible tool handler registry pattern allowing new agent tool query definitions to be registered with minimal configuration."

- **`ORIGINAL_REQUEST.md` (Lines 70–75)**:
  > "Acceptance Criteria:
  > - `POST /api/v1/tools/transactions` filters transactions by case, account, amount, and suspicion.
  > - `POST /api/v1/tools/entities` returns detailed inflows, outflows, and risk tags for queried accounts.
  > - `POST /api/v1/tools/patterns` returns detected cycles and pass-through accounts.
  > - `POST /api/v1/tools/legal-precedents` executes vector similarity search against legal precedents.
  > - `POST /api/v1/tools/query` safely executes structured composable filter queries."

### 1.2 Existing Codebase State
- **`backend/main.py` (Lines 58–60)**:
  ```python
  # Router Registration
  app.include_router(investigations_router, prefix=settings.API_V1_STR)
  app.include_router(tts_router, prefix=settings.API_V1_STR)
  ```
  `agent_tools_router` is currently not registered or created in `backend/main.py`.

- **`backend/models/forensic.py` (Lines 53–150)**:
  - `InvestigationCase`: UUID `id`, `filename`, `status`, `created_at`, `updated_at`, `ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`.
  - `TransactionRecord`: UUID `id`, UUID `case_id` (FK to `investigation_cases.id`, indexed), `origin` (indexed), `destination` (indexed), `amount` (Numeric(18,2)), `timestamp` (DateTime(timezone=True)), `is_suspicious` (Boolean, indexed), `reasons` (JSON).
  - `LegalArticleVector`: UUID `id`, `article_code` (unique, indexed), `law_name`, `content`, `embedding` (Vector(1536) with HNSW cosine index).

- **`backend/api/routes/investigations.py` (Lines 33, 36–61, 260–274)**:
  - Global `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}` provides dual-write caching during CSV upload for offline resilience when PostgreSQL is not connected.
  - `get_optional_db()` dependency yields an `AsyncSession` if `DATABASE_URL` is set and valid, or `None` if running offline or in mock test mode.

- **`backend/services/deterministic_filter.py` (Lines 180–257)**:
  - Subgraph output nodes contain: `id`, `total_in`, `total_out`, `in_degree`, `out_degree`, `reasons`, `risk_score`.
  - Subgraph output edges contain: `source`, `target`, `amount`, `count`, `timestamps`, `reasons`.
  - Patterns output contains: `cycles` (`path`, `length`, `estimated_volume`) and `passthrough_accounts` (`account_id`, `inflow`, `outflow`, `ratio`, `window_hours`).

- **`.agents/spec_miner_m3_1/analysis.md` (Lines 90–174, 431–508)**:
  - Defined Pydantic models for `DynamicQueryRequest`, `DynamicQueryResponse`, `QueryFilter`, `FilterOperator`, `SortOrder`, and target whitelists for `transactions`, `nodes`, `edges`, `cycles`, `passthrough_accounts`, and `legal_vectors`.

---

## 2. Logic Chain

1. **Decoupling via Registry Pattern**:
   - *Observation*: R3 demands an extensible tool handler registry where new tool queries can be added with minimal configuration and zero schema changes.
   - *Deduction*: Placing query translation logic inside route functions would tightly couple HTTP routes to specific entity structures. Designing `ToolRegistry` in `backend/services/tool_registry.py` with decorator support (`@tool_registry.register(target, ...)`) enables any service or module to register query targets cleanly.

2. **Eliminating SQL Injection via Parameterized ASTs**:
   - *Observation*: Dynamic queries allow clients to pass arbitrary field names, operators, and comparison values.
   - *Deduction*: Any string concatenation or formatting into SQL statements (`f"SELECT * WHERE {field} = '{value}'"`) introduces high-severity SQL injection vulnerabilities.
   - *Resolution*:
     a) Only field names belonging to the target's explicit `allowed_columns` whitelist are accepted; unwhitelisted field names are rejected with HTTP 400 before query construction.
     b) Once validated, fields are resolved as ORM mapped columns via `getattr(Model, field)`.
     c) Operators are mapped to native SQLAlchemy binary expressions (`column == value`, `column.like(pattern)`, `column.in_(list)`).
     d) Values are bound automatically as parameters (`:param_1`, `:param_2`) by SQLAlchemy 2.0, completely preventing code injection.

3. **Enforcing Mandatory `case_id` Scoping**:
   - *Observation*: In a multi-case forensic backend, transactions, entities, and patterns belong strictly to an individual investigation case.
   - *Deduction*: If an AI agent could issue a dynamic query on `transactions` without specifying a `case_id`, it would expose financial transactions belonging to other companies or investigations (cross-case data leak).
   - *Resolution*: The `ToolRegistry` marks `transactions`, `entities`, and `patterns` as `requires_case_id=True`. If `request.case_id` (or a `case_id == ...` filter) is missing, the query engine immediately aborts with HTTP 400 Bad Request, never touching the database.

4. **Dual Storage Execution (PostgreSQL & In-Memory Fallback)**:
   - *Observation*: `investigations.py` uses `INVESTIGATION_CASES` for offline resilience when remote PostgreSQL is unconfigured or in testing environments.
   - *Deduction*: If `tool_registry.execute_query` assumed `db` was always non-null, queries would crash with 500 Internal Server Error when running without active PostgreSQL.
   - *Resolution*: Target handlers implement dual execution: when `db` is present, they execute parameterized SQLAlchemy queries; when `db is None`, they evaluate identical filters over `INVESTIGATION_CASES` using pure Python predicates.

5. **Sorting and Pagination Safety**:
   - *Observation*: Arbitrary `sort_by` inputs could trigger SQL injection or cause database index scans to fail. Unbounded limits could exhaust server memory.
   - *Deduction*: `limit` must be clamped between 1 and 1000 (default 50), `offset` must be non-negative, and `sort_by` must be validated against `allowed_sort_columns`.

---

## 3. Caveats

1. **JSON Attribute Filtering**: For `TransactionRecord.reasons`, which is stored as a JSON array (`JSON_DOCUMENT`), SQL `like` or Python `in` searches work for keyword matching, but deep PostgreSQL JSONB path operators (`@>`, `?`) are dialect-specific and differ in SQLite. The query builder handles string containment (`like`/`ilike`) universally across PostgreSQL and SQLite.
2. **Entity Node Persistence**: Entity nodes are computed during ingestion and persisted within `InvestigationCase.subgraph["nodes"]`. The `entities` query handler extracts nodes directly from `subgraph["nodes"]` rather than recalculating them via expensive GROUP BY queries across millions of transactions on every request.
3. **Legal Knowledge Vectors**: The dynamic query builder filters `legal_precedents` using metadata attributes (`article_code`, `law_name`, `content`). For vector embedding similarity search, the dedicated endpoint `POST /api/v1/tools/legal-precedents` should be used with cosine distance.

---

## 4. Conclusion

The architectural design for Milestone 3 Dynamic Tool Registry and Query Builder is fully developed, secure, and ready for builder implementation:

1. **`backend/services/tool_registry.py`**:
   - Implement `ToolRegistry` class with `register()` decorator and method.
   - Define metadata and handlers for: `transactions`, `cases`, `entities` (alias `nodes`), `patterns` (aliases `cycles`, `passthrough_accounts`), `legal_precedents` (alias `legal_vectors`).
   - Implement safe parameterized SQLAlchemy query compiler and in-memory fallback evaluator.
   - Enforce column whitelisting, operator whitelisting, and mandatory `case_id` scoping.
2. **`backend/api/routes/agent_tools.py`**:
   - Create router `router = APIRouter(prefix="/tools", tags=["agent-tools"])`.
   - Expose `POST /api/v1/tools/query` calling `tool_registry.execute_query(request, db)`.
   - Expose dedicated endpoints (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`).
3. **`backend/main.py`**:
   - Import `agent_tools_router` and register: `app.include_router(agent_tools_router, prefix=settings.API_V1_STR)`.
4. Full implementation blueprints and specifications are documented in `.agents/explorer_m3_2/analysis.md`.

---

## 5. Verification Method

To independently verify the implementation once coded:

1. **Verify Router Registration in `backend/main.py`**:
   ```powershell
   python -c "from backend.main import app; routes = [r.path for r in app.routes]; assert '/api/v1/tools/query' in routes; print('Route registration verified:', [r for r in routes if 'tools' in r])"
   ```

2. **Verify Tool Registry Initialization & Targets**:
   ```powershell
   python -c "from backend.services.tool_registry import tool_registry; targets = tool_registry.list_targets(); assert len(targets) >= 5; print('Registered targets:', [t['target'] for t in targets])"
   ```

3. **Verify SQL Injection Immunity**:
   ```python
   # Issue query with malicious field name:
   payload = {
       "target": "transactions",
       "case_id": "00000000-0000-0000-0000-000000000000",
       "filters": [{"field": "origin; DROP TABLE transactions;--", "operator": "eq", "value": "ACC_1"}]
   }
   # Verify server returns HTTP 400 Bad Request with field rejection message.
   ```

4. **Verify Mandatory `case_id` Scoping**:
   ```python
   # Issue query without case_id:
   payload = {
       "target": "transactions",
       "filters": [{"field": "is_suspicious", "operator": "eq", "value": True}]
   }
   # Verify server returns HTTP 400 Bad Request: "Mandatory scoping violation: 'case_id' is required..."
   ```

5. **Run Automated Test Suite**:
   ```powershell
   pytest backend/tests/test_agent_tools.py -v
   ```
