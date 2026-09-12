# Milestone 2 Review & Adversarial Analysis: Investigation Lifecycle & Persistent Case Management

**Reviewer**: `reviewer_m2_2` (Reviewer 2 & Adversarial Critic)  
**Date**: 2026-09-12  
**Target Milestone**: Milestone 2 (Investigation Lifecycle & Persistent Case Management)  
**Deliverables Reviewed**:
- `backend/schemas/investigation.py`
- `backend/api/routes/investigations.py`
- `backend/tests/test_investigations.py`
- `.agents/worker_m2_1/handoff.md`
- `.agents/worker_m2_1/changes.md`

---

## 1. Executive Review Summary

**Verdict**: **APPROVE**  
**Integrity Status**: **CLEAN (No violations detected)**  
**Overall Risk Assessment**: **LOW**

Worker `worker_m2_1` implemented the complete investigation persistence lifecycle with full fidelity to `ORIGINAL_REQUEST.md` (§R2) and `PROJECT.md`:
1. `POST /api/v1/investigations/upload`: Parses CSVs using Polars, applies deterministic graph filtering via NetworkX, bulk-persists `InvestigationCase` and `TransactionRecord` entities into PostgreSQL, and dual-writes to memory for offline resilience.
2. `GET /api/v1/investigations`: Robust paginated listing supporting 1-indexed pagination (`page >= 1`), strict bounds (`page_size` 1–100), case-insensitive status filtering, and accurate page count calculations.
3. `GET /api/v1/investigations/{case_id}`: Clean detail retrieval with exact 404 handling for nonexistent UUIDs and 422 for malformed strings.
4. `GET /api/v1/investigations/{case_id}/stream`: Real-time SSE streaming with 6 thought phases and terminal verdict event, supporting both proxying to external `N8N_WEBHOOK_URL` and automatic simulation fallback. Updates status to `COMPLETED` and saves verdict in database upon completion.
5. Automated test suite runs with 100% pass rate (`18 passed in 7.72s`), and dedicated adversarial stress tests passed across all boundary and failure modes.

---

## 2. Integrity Verification

As mandated by adversarial reviewer protocol, an active integrity assessment was executed:
- **Hardcoded test results or expected outputs embedded in source code**: **NONE FOUND**. The endpoints execute genuine Polars parsing, NetworkX topological calculations, and dynamic SQL statements via SQLAlchemy 2.0.
- **Dummy or facade implementations**: **NONE FOUND**. Schema validation, transaction classification, database persistence, and SSE event loops are fully implemented with real operational code.
- **Shortcuts bypassing intended tasks**: **NONE FOUND**.
- **Fabricated verification outputs or logs**: **NONE FOUND**. Verified independently by executing `python -m pytest backend/tests/ -v` (18 passed) and direct ASGI stream execution.
- **Self-certifying work without independent verification**: **REJECTED**. Independent test suite was constructed and executed in isolation.

---

## 3. Adversarial Stress-Test Findings & Verification

An independent test harness (`.agents/reviewer_m2_2/test_adversarial.py`) was executed to evaluate key failure modes:

| Test Scenario | Attack / Stress Vector | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| **Pagination: Page < 1** | `?page=0`, `?page=-1`, `?page=-999` | HTTP 422 Validation Error | Returns HTTP 422 with Pydantic detail | **PASS** |
| **Pagination: Size Bounds** | `?page_size=0`, `?page_size=-5`, `?page_size=101` | HTTP 422 Validation Error | Returns HTTP 422 with Pydantic detail | **PASS** |
| **Pagination: Maximum Bound** | `?page_size=100` | HTTP 200 OK | Returns HTTP 200 with 100 items limit | **PASS** |
| **Pagination: Empty Database** | `?page=1&page_size=20` on empty DB | HTTP 200 with `total=0, total_pages=0, items=[]` | Returns total=0, total_pages=0, items=[] | **PASS** |
| **Pagination: Page Out of Bounds** | `?page=99&page_size=20` with 5 items | HTTP 200 with `total=5, items=[]` | Returns total=5, items=[] | **PASS** |
| **Pagination: Status Filter** | `?status=completed`, `COMPLETED`, `cOmPlEtEd` | Case-insensitive matching | Matches all 3 cases uniformly | **PASS** |
| **Retrieval: Nonexistent UUID** | `GET /investigations/{random_uuid}` | HTTP 404 Clean JSON error | HTTP 404 `Investigation case '...' not found.` | **PASS** |
| **Retrieval: Malformed UUID** | `GET /investigations/not-a-uuid` | HTTP 422 Validation Error | HTTP 422 with path parameter error | **PASS** |
| **Stream: Nonexistent UUID** | `GET /investigations/{random_uuid}/stream` | HTTP 404 upfront before streaming | HTTP 404 `Investigation case '...' not found.` | **PASS** |
| **Stream: Malformed UUID** | `GET /investigations/not-a-uuid/stream` | HTTP 422 upfront before streaming | HTTP 422 with path parameter error | **PASS** |
| **n8n Webhook: Unconfigured (None)** | `settings.N8N_WEBHOOK_URL = None` | Seamless fallback to 6 thoughts + 1 verdict | Emits 6 thoughts + 1 verdict, saves DB verdict | **PASS** |
| **n8n Webhook: Unreachable** | `settings.N8N_WEBHOOK_URL = "http://127.0.0.1:59999/unreachable"` | Logs warning, catches ConnectError, simulated fallback | Emits 6 thoughts + 1 verdict, saves DB verdict | **PASS** |
| **n8n Webhook: Reachable SSE Stream** | Mock HTTPX SSE stream from n8n agent | Proxies events, extracts verdict, persists to DB | Case status updated to COMPLETED with n8n verdict | **PASS** |
| **SSE Disconnect: Mid-stream** | Direct ASGI `http.disconnect` after 2 chunks | Immediate generator halt; status remains `PROCESSING` | No session leak, case stays PROCESSING, no bogus verdict | **PASS** |

---

## 4. Code Quality Findings & Observations

### Minor / Observational (Non-Blocking)

1. **Database Session Holding during Long SSE Streams**:
   - **Where**: `backend/api/routes/investigations.py`, line 548 (`stream_investigation_thoughts`).
   - **Observation**: The endpoint accepts `db: Optional[AsyncSession] = Depends(get_optional_db)`. In FastAPI, dependencies yielding resources remain open until the response finishes or disconnects. In this endpoint, `db` is used only once to verify case existence and fetch initial metadata, after which `StreamingResponse` streams for 2–3+ seconds. Verdict persistence at stream conclusion uses a dedicated, short-lived session from `get_session_factory()`.
   - **Impact**: Under high concurrency (e.g. 50 simultaneous streams), pooled connections could be held idle while the stream is emitting.
   - **Recommendation**: In a future hardening pass, the initial lookup can either be wrapped in an explicit short-lived session context, or `get_optional_db` can be detached from the streaming handler to minimize connection pool footprint.

2. **Query Filtering Clause Ordering in Pagination**:
   - **Where**: `backend/api/routes/investigations.py`, lines 314–320.
   - **Observation**: `cases_stmt` has `.order_by(...).offset(...).limit(...)` attached before `.where(func.upper(InvestigationCase.status) == clean_status)`.
   - **Impact**: SQLAlchemy 2.0 correctly compiles the `WHERE` clause prior to `ORDER BY` and `LIMIT`/`OFFSET` (verified via AST inspection). However, attaching `.where()` before `.order_by()` and `.limit()` is considered best practice for query readability.

---

## 5. Verified Claims

1. `POST /api/v1/investigations/upload` persists `InvestigationCase` and `TransactionRecord` rows to database: **VERIFIED** (`test_csv_upload_persistence_with_database`, confirmed in SQLite and ORM).
2. Dual-write in-memory fallback works when `DATABASE_URL` is unset: **VERIFIED** (`test_csv_upload_in_memory_fallback`, `test_paginated_listing_in_memory_fallback`).
3. Cascading delete on `InvestigationCase` removes child `TransactionRecord` records: **VERIFIED** (`test_cascade_deletion_removes_transactions`).
4. SSE stream terminates with `verdict` event and updates `InvestigationCase.status` to `COMPLETED` in PostgreSQL: **VERIFIED** (`test_sse_streaming_and_database_verdict_persistence`).
5. All 18 automated tests in `backend/tests/` pass cleanly without errors: **VERIFIED** (`18 passed in 7.72s`).

---

## 6. Coverage Gaps & Unverified Items

- None. All requirements specified under Milestone 2 (§R2) and acceptance criteria have been rigorously tested and independently verified.
