# Handoff Report: Milestone 2 — Investigation Persistence & Pagination Contracts

**Agent**: `spec_miner_m2_1`  
**Milestone**: M2 (Investigation Persistence & Pagination Contracts)  
**Date**: 2026-09-12  
**Handoff Type**: Hard Handoff (Task Complete)  

---

## 1. Observation

1. **Existing Models & Database Layer**:
   - `backend/models/forensic.py` (lines 53-125) defines `InvestigationCase` with fields (`id`, `filename`, `status`, `created_at`, `updated_at`, `ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`) and `TransactionRecord` with fields (`id`, `case_id`, `origin`, `destination`, `amount`, `timestamp`, `is_suspicious`, `reasons`).
   - `backend/core/database.py` (lines 175-191) exports `get_db() -> AsyncGenerator[AsyncSession, None]`, with automatic commit on success, rollback on error, and session close.
   - `backend/tests/test_database.py` passes 7 tests verifying URL normalization, engine pooling, SQLite cross-compilation with `@compiles(Vector, "sqlite")`, model CRUD, cascade deletion, and seed legal precedents.
2. **Current Route Implementation**:
   - `backend/api/routes/investigations.py` (lines 16-17) currently uses a local in-memory store:
     ```python
     INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}
     ```
   - Only two routes are defined: `POST /upload` (line 20) and `GET /{case_id}/stream` (line 192).
   - Missing routes: `GET /api/v1/investigations` (paginated listing) and `GET /api/v1/investigations/{case_id}` (detail retrieval).
   - `POST /upload` does not currently inject `get_db()` or insert into `investigation_cases` or `transactions`.
   - `GET /{case_id}/stream` does not query the database or persist the final verdict and `COMPLETED` status upon completion.
3. **Frontend Contract Requirements**:
   - `frontend/types/investigation.ts` (lines 28-80) defines `GraphNode`, `GraphEdge`, `InvestigationMetrics`, `SubgraphData`, `VerdictEvent`, and `UploadResponse`.
   - `frontend/components/FileUpload.tsx` (lines 67-78) expects `POST /api/v1/investigations/upload` to return HTTP 201 with `UploadResponse` JSON schema.
4. **Project Test Suite Status**:
   - Executed `python -m pytest -v backend/tests` via `run_command` (task id `206894a5-56d6-4175-9693-b6a1cefefcb7/task-76`).
   - Output: `9 passed in 4.27s` (clean 100% pass on all existing tests).

---

## 2. Logic Chain

1. **Step 1 — Source Specification & Requirements**:
   `ORIGINAL_REQUEST.md` (Requirement R2) explicitly commands:
   - Persist case and all transactions into PostgreSQL on `POST /upload`.
   - Return paginated cases with status, timestamps, and summary metrics on `GET /investigations`.
   - Retrieve stored case details, topological metrics, and isolated subgraph on `GET /investigations/{case_id}`.
   - Stream SSE thoughts, emit final verdict, and persist verdict and `COMPLETED` status on `GET /investigations/{case_id}/stream`.
2. **Step 2 — Schema Design & Pydantic v2 Separation**:
   Currently, there are no formal Pydantic schema files in `backend/` (routes return unvalidated dicts).
   Creating `backend/schemas/investigation.py` introduces strict validation and documentation for:
   - `InvestigationUploadResponse`
   - `InvestigationPaginationResponse` (with `InvestigationSummary`)
   - `InvestigationDetailResponse`
   - `ThoughtEvent` and `VerdictPayload`
   All schemas use `ConfigDict(from_attributes=True)` to map seamlessly from SQLAlchemy ORM models.
3. **Step 3 — Bulk Transaction Ingestion**:
   In `POST /upload`, `read_amlsim_csv()` returns a Polars `DataFrame`. NetworkX pruning extracts suspicious edges. By matching `(origin, destination)` pairs in $O(1)$ time, every transaction row can be tagged with `is_suspicious: bool` and its corresponding reasons, then bulk-inserted using `session.add_all(transactions)` to avoid per-row overhead.
4. **Step 4 — Timestamp Normalization**:
   `TransactionRecord.timestamp` requires `DateTime(timezone=True)`. AMLSim datasets may supply simulation steps (`1.0`, `2.0`) or Unix epochs (`1672531200.0`). Normalizing values $> 10^8$ via `datetime.fromtimestamp()` and smaller step values via `datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=ts)` ensures consistent type compliance.
5. **Step 5 — Pagination & Filtering Semantics**:
   - Enforcing `page >= 1` and `1 <= page_size <= 100` protects the database against negative offset and denial-of-service memory pressure.
   - Ordering by `created_at.desc()` ensures newest investigations appear first.
   - Using `func.upper(InvestigationCase.status) == status.upper().strip()` allows case-insensitive filtering (`status=completed` matches `COMPLETED`).
6. **Step 6 — SSE Verdict Persistence**:
   In `GET /{case_id}/stream`, verifying the case in PostgreSQL before initiating the SSE generator prevents sending invalid streaming headers for missing cases. Upon yielding the terminal `verdict` event, executing an async DB update sets `case.verdict = verdict_payload`, `case.status = "COMPLETED"`, and `case.updated_at = func.now()`.

---

## 3. Caveats

1. **Large Dataset Memory Profile**: Ingestion of extremely large CSV files (> 100,000 rows) via `file.read()` loads the raw byte buffer into memory. While Polars handles millions of rows efficiently, database insertion should be executed in chunks (e.g. 1,000 transactions per batch) to avoid exceeding SQLite or PostgreSQL bind variable limits.
2. **n8n Webhook Latency**: When `N8N_WEBHOOK_URL` is enabled, upstream latency is dictated by n8n. The existing 10-second timeout with fallback simulation ensures that client requests never hang.
3. **In-Memory SQLite Test Compatibility**: SQLite does not natively support PostgreSQL's `JSONB` or `Vector`. The compiler hooks in `backend/models/forensic.py` (lines 36-48) translate these to `JSON` and `TEXT`, allowing in-memory testing without a live PostgreSQL instance.

---

## 4. Conclusion

The specification, schema architecture, database migration blueprint, and edge-case contracts for Milestone 2 are completely mapped out and documented in `.agents/spec_miner_m2_1/analysis.md`. The design:
- Requires **zero breaking changes** to Milestone 1 ORM models (`backend/models/forensic.py`).
- Introduces `backend/schemas/investigation.py` with complete Pydantic v2 schemas.
- Extends `backend/api/routes/investigations.py` with the 2 missing endpoints (`GET /` and `GET /{case_id}`) and migrates `/upload` and `/{case_id}/stream` to full SQLAlchemy async persistence.
- Meets 100% of the requirements specified in `ORIGINAL_REQUEST.md` R2 and the user prompt.

---

## 5. Verification Method

To independently verify the contracts and specifications:

1. **Inspect Artifacts**:
   - View `.agents/spec_miner_m2_1/analysis.md` for the complete feature tables, edge case tables, and Pydantic models.
   - View `backend/models/forensic.py` to confirm that all required fields for `InvestigationCase` and `TransactionRecord` are already implemented.
   - View `frontend/types/investigation.ts` to confirm 100% schema alignment with client expectations.
2. **Execute Existing Test Suite**:
   ```powershell
   python -m pytest -v backend/tests
   ```
   Ensures the baseline remains 100% passing (`9 passed`).
3. **Invalidation Conditions**:
   - If any proposed schema breaks `frontend/types/investigation.ts` (e.g., changing `case_id` or `metrics` keys).
   - If `TransactionRecord` timestamp mapping causes SQLAlchemy `StatementError` on simulation step inputs.
