# Milestone 2 Code Changes

**Agent**: `worker_m2_1`  
**Milestone**: M2 (Investigation Lifecycle & Persistent Case Management)  
**Date**: 2026-09-12  

---

## 1. Files Created / Modified

### 1.1 `backend/schemas/investigation.py` (Created)
- Implemented Pydantic v2 schemas:
  - `CaseStatus`: Enum with `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.
  - `GraphNode`: Bank account node model with `id`, `total_in`, `total_out`, `in_degree`, `out_degree`, `reasons`, and `risk_score`.
  - `GraphEdge`: Directed edge model with `source`, `target`, `amount`, `count`, `timestamps`, `reasons`.
  - `SubgraphData`: Isolated topology model with `nodes` and `edges`.
  - `InvestigationMetrics`: Topological pruning metrics (`total_nodes_analyzed`, `suspicious_nodes_count`, `pruned_nodes_count`, `total_edges_analyzed`, `suspicious_edges_count`, `pruned_edges_count`, `suspicious_volume_mxn`, `detected_cycles_count`, `passthrough_accounts_count`, `pruning_efficiency_pct`).
  - `CyclePattern` & `PassthroughAccountPattern`: Pattern models for detected directed cycles and high-velocity mule accounts.
  - `InvestigationPatterns`: Composite model wrapping `cycles` and `passthrough_accounts`.
  - `VerdictPatternsSummary`: Pattern summary for terminal verdict payload.
  - `VerdictPayload`: Comprehensive forensic verdict model matching frontend contract (`frontend/types/investigation.ts`).
  - `ThoughtEvent`: Event schema for real-time SSE reasoning steps 1-6.
  - `InvestigationUploadResponse`: Response schema for `POST /upload` with HTTP 201.
  - `InvestigationSummary`: Case summary schema with pre-extraction model validator for `has_verdict` and `risk_level`.
  - `InvestigationPaginationResponse`: Pagination container model with `total`, `page`, `page_size`, `total_pages`, `items`.
  - `InvestigationDetailResponse`: Full case detail model with pre-extraction model validator mapping ORM/in-memory attributes.

### 1.2 `backend/schemas/__init__.py` (Created)
- Exported all Pydantic v2 investigation models and enums in `__all__` for centralized import access.

### 1.3 `backend/api/routes/investigations.py` (Modified)
- Added `get_optional_db()` dependency yielding an `AsyncSession` if `settings.DATABASE_URL` is configured, or `None` for offline in-memory fallback.
- Added `parse_timestamp_to_datetime()` normalizer converting float simulation steps, Unix epochs, or ISO strings to timezone-aware UTC datetime.
- Updated `POST /upload`:
  - Enforced CSV validation (rejecting non-CSV with 400 and empty content with 422).
  - Correlated cleaned Polars DataFrame rows with NetworkX suspicious edges and nodes.
  - Instantiated `InvestigationCase` with status `"PROCESSING"`.
  - Bulk-inserted individual `TransactionRecord` rows with proper suspicion flags (`is_suspicious: bool`) and reason tags (`"CYCLE_STEP"`, `"PASSTHROUGH_BRIDGE"`, etc.).
  - Maintained dual-write to `INVESTIGATION_CASES` dictionary for offline resilience.
  - Returned HTTP 201 with `InvestigationUploadResponse`.
- Added `GET /`:
  - Implemented page-based pagination with `page: int = Query(1, ge=1)` and `page_size: int = Query(20, ge=1, le=100)`.
  - Added case-insensitive `status` query filter (`func.upper(InvestigationCase.status) == status.upper()`).
  - Computed total count and total pages.
  - Returned `InvestigationPaginationResponse` ordered by `created_at` descending.
- Added `GET /{case_id}`:
  - Validated UUID format via FastAPI path parameter typing (`case_id: uuid.UUID`).
  - Queried PostgreSQL by `id`, falling back to `INVESTIGATION_CASES`.
  - Returned HTTP 404 if case not found.
  - Returned `InvestigationDetailResponse` with complete metrics, subgraph, patterns, and verdict.
- Updated `GET /{case_id}/stream`:
  - Pre-validated case existence in PostgreSQL / memory, returning HTTP 404 before initiating SSE stream if missing.
  - Decoupled streaming generator from long-lived DB transactions to prevent connection pool exhaustion and session closure errors.
  - Implemented `persist_case_verdict()` opening a short-lived `AsyncSession` via `get_session_factory()` upon stream completion to atomically update `InvestigationCase.verdict` and `status = "COMPLETED"`.
  - Streamed 6 `thought` events and terminal `verdict` event, supporting n8n webhook proxying with automatic fallback to simulated 6-phase reasoning.

### 1.4 `backend/tests/test_investigations.py` (Created)
- Built 9 dedicated automated test cases verifying Milestone 2 functionality:
  1. `test_csv_upload_persistence_with_database`: Confirms `InvestigationCase` and all 7 `TransactionRecord` rows are correctly saved in SQLite/PostgreSQL with suspicion classification and reasons.
  2. `test_csv_upload_in_memory_fallback`: Confirms offline upload works when `DATABASE_URL` is unset.
  3. `test_csv_upload_validation_errors`: Confirms 400 on non-CSV and 422 on empty file or missing columns.
  4. `test_paginated_listing_with_database`: Confirms pagination slicing, status filtering (`completed`, `PROCESSING`), and parameter bounds (`page=0`, `page_size=0`, `page_size=101`).
  5. `test_paginated_listing_in_memory_fallback`: Confirms pagination works in offline mode.
  6. `test_investigation_detail_retrieval`: Confirms detail lookup by UUID, 404 on non-existent UUID, and 422 on invalid UUID format.
  7. `test_sse_streaming_and_database_verdict_persistence`: Confirms 6 thought events, 1 verdict event, and atomic transition to `COMPLETED` with verdict in database.
  8. `test_sse_streaming_non_existent_case_returns_404`: Confirms 404 before stream start.
  9. `test_cascade_deletion_removes_transactions`: Confirms deleting `InvestigationCase` automatically cascades and purges all child `TransactionRecord` rows.

---

## 2. Test Verification Summary

Command executed: `python -m pytest backend/tests/ -v`  
Result: **18 passed in 7.41s** (100% pass rate, 0 errors, 0 warnings).
