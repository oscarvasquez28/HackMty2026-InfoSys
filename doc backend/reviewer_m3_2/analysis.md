# Milestone 3 Review & Adversarial Analysis

**Reviewer**: `reviewer_m3_2` (Reviewer 2)  
**Roles**: Reviewer, Adversarial Critic  
**Scope**: Milestone 3 — Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents  
**Target Modules**:
- `backend/schemas/agent_tools.py`
- `backend/services/tool_registry.py`
- `backend/api/routes/agent_tools.py`
- `backend/main.py`
- `backend/tests/test_agent_tools.py`

---

## 1. Executive Review Summary

**Verdict**: **APPROVE**  
**Integrity Assessment**: **CLEAN / NO VIOLATIONS DETECTED**  
**Overall Risk Assessment**: **LOW**

The Milestone 3 implementation thoroughly and genuinely fulfills all requirements set forth in `ORIGINAL_REQUEST.md` (§R3) and `.agents/orchestrator_1/PROJECT.md`. The design provides both high-level dedicated endpoints for n8n agents (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`) and an arbitrary composable dynamic query interface (`/query`) powered by a robust, extensible `ToolRegistry`.

The architecture demonstrates exemplary defense-in-depth against SQL injection and cross-case tenant contamination:
1. Column whitelisting is enforced at two distinct layers (Pydantic schema validation returning HTTP 422, and `ToolRegistry.execute_query` validation returning HTTP 400).
2. SQL statements are constructed exclusively through SQLAlchemy 2.0 binary expressions (`apply_sa_operator`) with bound parameters, preventing SQL injection even under adversarial payload injection.
3. Mandatory `case_id` scoping is enforced for all case-scoped targets (`transactions`, `entities`, `nodes`, `edges`, `patterns`, `cycles`, `passthrough_accounts`), mathematically preventing multi-tenant or cross-case data leakage.
4. The router is properly registered under `app.include_router(agent_tools_router, prefix=settings.API_V1_STR)` in `backend/main.py`.
5. Full dual execution parity is maintained: the system operates with high-performance asynchronous SQLAlchemy queries against PostgreSQL/SQLite, while gracefully providing complete in-memory filtering parity via `INVESTIGATION_CASES` when operating without an active database connection.

---

## 2. Integrity Verification (Anti-Cheat Audit)

In accordance with reviewer instructions, the codebase was explicitly audited for integrity violations:
- **Hardcoded test outputs**: Evaluated `backend/api/routes/agent_tools.py` and `backend/services/tool_registry.py`. All database paths execute dynamic SQLAlchemy queries (`select(TransactionRecord)...`, `select(InvestigationCase.subgraph)...`, `select(LegalArticleVector)...`). No hardcoded return values or test-specific branch hacks exist.
- **Dummy/Facade implementations**: Dynamic AST generator `apply_sa_operator` produces genuine SQLAlchemy binary expression clauses (`column == value`, `column.like(...)`, `column.in_(...)`). Entity profiling calculates degrees, flows, net volume, and counterparty sets directly from graph topology. Legal vector search computes true unit-normalized cosine similarity across 1536-dimensional embeddings.
- **Shortcuts & external delegation**: The tool registry and AST query engine were written from scratch specifically for this project without delegating to unapproved external tools or stubbing logic.
- **Independent verification**: The reviewer independently executed the complete test suite (50/50 passing in 14.99s) and executed standalone adversarial test scripts via httpx directly attacking query endpoints.

---

## 3. Detailed Code Review & Findings

### 3.1 `backend/schemas/agent_tools.py`
- **Quality & Conformance**: Clean Pydantic v2 declarative schemas utilizing `ConfigDict(from_attributes=True, populate_by_name=True)`.
- **Target & Operator Enums**: `TargetEntity` and `FilterOperator` define strict sets of supported entities and operators.
- **Whitelisting**: `TARGET_FIELD_WHITELISTS` explicitly bounds queryable attributes per target.
- **Cross-Bound Validation**:
  - `TransactionQueryRequest`: Validates `min_amount <= max_amount` and `start_time <= end_time`.
  - `PatternQueryRequest`: Validates `min_cycle_length <= max_cycle_length`.
  - `LegalPrecedentQueryRequest`: Validates `query_vector` has exactly 1536 dimensions if provided.
  - `QueryFilter`: Validates that `in` and `not_in` operators receive list/tuple/set values.
  - `DynamicQueryRequest`: Model validator enforces mandatory `case_id` presence for `CASE_SCOPED_TARGETS` and rejects unwhitelisted fields or unwhitelisted sort columns.

### 3.2 `backend/services/tool_registry.py`
- **Extensibility**: `ToolRegistry` implements a clean decorator-based registration pattern (`@tool_registry.register(...)`) supporting runtime target additions without schema alterations.
- **Parameterized SQL AST Compiler**: `apply_sa_operator` maps operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in`) to SQLAlchemy column operations with zero string concatenation.
- **Empty Array Handling**: For empty lists in `in_`, it safely outputs `column.in_([None]) & column.is_not(None)` which evaluates to false without SQL syntax errors. For `not_in`, it outputs `True`.
- **Target Handlers**: Built-in handlers for `transactions`, `cases`, `entities` (alias `nodes`), `patterns` (aliases `cycles`, `passthrough_accounts`), `edges`, and `legal_precedents` (alias `legal_vectors`).
- **In-Memory Fallback Evaluator**: `evaluate_in_memory_predicate` provides robust comparison logic supporting floats, ints, bools, strings, and set membership for zero-db offline development.

### 3.3 `backend/api/routes/agent_tools.py`
- **Endpoint Structure**: Exposes 5 RESTful endpoints under `/tools`:
  1. `POST /api/v1/tools/transactions`: Filters transactions with aggregation of `total_volume_mxn`.
  2. `POST /api/v1/tools/entities`: Profiles entity counterparties in/out, degrees, inflow/outflow, and risk scores.
  3. `POST /api/v1/tools/patterns`: Extracts cycles and pass-through mule accounts with threshold filtering.
  4. `POST /api/v1/tools/legal-precedents`: Performs vector similarity ranking against Mexican AML statutes (CFF 69-B, LFPIORPI, UIF).
  5. `POST /api/v1/tools/query`: Composable dynamic query endpoint delegating to `tool_registry.execute_query`.
- **Error Handling**: Nonexistent cases return HTTP 404; invalid UUIDs return HTTP 400; unwhitelisted fields return HTTP 400/422.

### 3.4 `backend/main.py`
- `agent_tools_router` is imported and mounted with `app.include_router(agent_tools_router, prefix=settings.API_V1_STR)` at line 61. Verified available at `/api/v1/tools/*`.

### 3.5 Findings
- **Finding 1 (Minor / Non-blocking Observation)**:
  - *Location*: `backend/services/tool_registry.py:390-394`
  - *Observation*: In `handle_transactions_query`, when `request.filters` contains a filter with `field == "case_id"`, it skips it (`if f.field == "case_id": continue`) because the root `where_clauses` already includes `TransactionRecord.case_id == case_uuid`.
  - *Assessment*: This is secure and harmless because `case_uuid` is already validated and enforced as the root filter. In an adversarial scenario where a client specifies `case_id = case1` at the root and attempts to inject `filters: [{"field": "case_id", "value": case2}]`, the handler safely scopes to `case1`, completely preventing access to `case2`.
  - *Recommendation*: Consider returning HTTP 400 if `f.field == "case_id"` conflicts with `request.case_id` to provide explicit feedback to API callers. Not a blocker.

---

## 4. Adversarial Stress-Testing & Attack Surface

### 4.1 SQL Injection Attacks
- **Vector 1: Column Name Injection**
  - *Payload*: `{"field": "origin; DROP TABLE transactions;--", "operator": "eq", "value": "ACC_A"}`
  - *Result*: Rejected at Pydantic layer with **HTTP 422 Unprocessable Entity** ("Field 'origin; DROP TABLE transactions;--' is not permissible for target 'transactions'").
  - *Verdict*: **PASSED (Immune)**.
- **Vector 2: Sort Column Injection**
  - *Payload*: `{"sort_by": "status; DROP TABLE cases;--"}`
  - *Result*: Rejected at Pydantic layer with **HTTP 422 Unprocessable Entity**.
  - *Verdict*: **PASSED (Immune)**.
- **Vector 3: Comparison Value Injection**
  - *Payload*: `{"field": "origin", "operator": "eq", "value": "' OR 1=1 --"}`
  - *Result*: Executed as parameterized literal comparison `TransactionRecord.origin == "' OR 1=1 --"`. Returns 0 records. Database table remains intact.
  - *Verdict*: **PASSED (Immune)**.
- **Vector 4: Operator Injection**
  - *Payload*: `{"operator": "DROP TABLE"}`
  - *Result*: Rejected at Pydantic enum validation with **HTTP 422 Unprocessable Entity**.
  - *Verdict*: **PASSED (Immune)**.

### 4.2 Cross-Case Tenant Contamination Attacks
- **Scenario 1: Query without `case_id` for case-scoped target**
  - *Payload*: `POST /api/v1/tools/query` with `target: "transactions"`, no `case_id` supplied.
  - *Result*: Rejected with **HTTP 422 Value error, case_id is required when querying target 'transactions'**.
  - *Verdict*: **PASSED (Isolated)**.
- **Scenario 2: Multi-case transaction leak attempt**
  - Setup: Inserted Case 1 (`case1_id`) with transaction `CASE1_ACC_A` and Case 2 (`case2_id`) with transaction `CASE2_ACC_X`.
  - Execution: Queried transactions scoped to `case1_id`.
  - Result: Only `CASE1_ACC_A` returned. `CASE2_ACC_X` was completely inaccessible.
  - *Verdict*: **PASSED (Isolated)**.
- **Scenario 3: Non-equality operator on `case_id`**
  - *Payload*: `filters: [{"field": "case_id", "operator": "neq", "value": "0000..."}]`
  - *Result*: Rejected with **HTTP 422** because `case_id` filter only satisfies scoping when `operator == "eq"`.
  - *Verdict*: **PASSED (Isolated)**.

### 4.3 Input Validation & Boundary Stress-Testing
- **Unknown Target**:
  - *Payload*: `target: "malicious_table"`
  - *Result*: Returns **HTTP 400 Bad Request** with clear list of allowed targets.
- **Invalid UUID format**:
  - *Payload*: `case_id: "not-a-valid-uuid"`
  - *Result*: Returns **HTTP 400 Bad Request** ("Invalid UUID format for case_id").
- **Empty Array Operators**:
  - `{"operator": "in", "value": []}` -> Returns 0 records cleanly without SQL syntax crash.
  - `{"operator": "not_in", "value": []}` -> Returns all records cleanly.

---

## 5. Verified Claims Summary

| Claim | Verification Method | Status |
|-------|---------------------|--------|
| All test cases pass cleanly | `pytest backend/tests/ -v` (50 passed in 14.99s) | **PASS** |
| Dedicated transactions tool filters correctly | Automated unit tests + live httpx integration calls | **PASS** |
| Dedicated entities tool calculates degrees and flow | Automated unit tests + live httpx integration calls | **PASS** |
| Dedicated patterns tool extracts cycles and mules | Automated unit tests + live httpx integration calls | **PASS** |
| Legal precedents vector search ranks by similarity | Unit tests verifying dot-product cosine similarity | **PASS** |
| Dynamic query executes all relational operators | Tested `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in` | **PASS** |
| Column whitelisting blocks arbitrary fields | Adversarial injection testing (HTTP 422/400) | **PASS** |
| Cross-case isolation strictly enforced | Multi-case test fixture verifying 0 cross-case records | **PASS** |
| Router mounted with `settings.API_V1_STR` | Verified routes in `backend/main.py` and OpenAPI schema | **PASS** |
| Dual execution (DB + in-memory) parity | Executed tests with `DATABASE_URL = None` | **PASS** |

---

## 6. Verdict

**APPROVE**  
The Milestone 3 deliverables represent exceptionally high code quality, strict adherence to architectural contracts, robust security design against SQL injection and tenant leakage, and 100% test pass rate with zero regressions. Ready for integration and Milestone 4.
