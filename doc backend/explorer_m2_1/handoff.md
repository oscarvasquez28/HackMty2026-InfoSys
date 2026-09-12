# Handoff Report: Milestone 2 — Upload Ingestion & Database Relational Persistence

## 1. Observation
- **Database Layer (`backend/core/database.py:175-191`)**:
  - `get_db()` yields `AsyncSession`, but if `settings.DATABASE_URL` is empty, `get_engine()` raises `RuntimeError("DATABASE_URL is not configured...")` at lines 156-160.
- **ORM Schema (`backend/models/forensic.py:53-124`)**:
  - `InvestigationCase` maps table `investigation_cases` with UUID `id`, `filename`, `status`, `created_at`, `updated_at`, and JSON columns `ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`.
  - `TransactionRecord` maps table `transactions` with UUID `id`, UUID `case_id` (FK with cascade delete), `origin`, `destination`, `amount` (`Numeric(18, 2)`), `timestamp` (`DateTime(timezone=True)`), `is_suspicious` (`Boolean`), and `reasons` (`JSON_DOCUMENT`).
- **Ingestion & Pruning Services**:
  - `backend/services/ingestion.py:28-102` (`read_amlsim_csv`) returns `cleaned_df` (`origin`, `destination`, `amount`, `timestamp` as float) and `metadata` dict (`total_records`, `total_volume`, `unique_accounts`).
  - `backend/services/deterministic_filter.py:139-259` (`apply_deterministic_filter`) returns `{"subgraph": {"nodes": [...], "edges": [...]}, "metrics": {...}, "patterns": {...}}`.
- **Existing Routes (`backend/api/routes/investigations.py:14-215`)**:
  - `POST /upload` currently stores cases only in `INVESTIGATION_CASES: Dict[str, Dict[str, Any]]` at line 58.
  - `GET /investigations` (paginated listing) does not exist yet.
  - `GET /investigations/{case_id}` (detail lookup) does not exist yet.
  - `GET /investigations/{case_id}/stream` streams SSE events from memory but does not update PostgreSQL upon completion.
- **Current Tests (`backend/tests/test_pipeline.py`)**:
  - `python -m pytest` passes 9 tests, running against in-memory data without a configured `DATABASE_URL`.

---

## 2. Logic Chain
1. **Schema Linkage**: Each uploaded dataset represents one `InvestigationCase`. All transaction rows in `cleaned_df` represent individual `TransactionRecord` instances whose `case_id` equals `case_obj.id`.
2. **Correlation Logic**: To populate `is_suspicious` and `reasons` for each transaction record:
   - Suspicious edges from NetworkX pruning are formatted in `filter_results["subgraph"]["edges"]` with `source`, `target`, and `reasons` (e.g. `CYCLE_STEP`, `PASSTHROUGH_BRIDGE`).
   - Suspicious nodes are formatted in `filter_results["subgraph"]["nodes"]` with `id` and `reasons` (e.g. `CIRCULAR_FLOW_CYCLE`, `HIGH_VELOCITY_PASSTHROUGH_90PCT`).
   - Constructing lookup dictionaries `suspicious_edge_map: Dict[Tuple[str, str], List[str]]` and `suspicious_node_map: Dict[str, List[str]]` allows $O(1)$ correlation for each row in Polars DataFrame.
3. **Database Insertion**:
   - `case_obj = InvestigationCase(...)`
   - `transaction_records = [TransactionRecord(...) for row in df.to_dicts()]`
   - `session.add(case_obj)`
   - `session.add_all(transaction_records)`
   - `await session.commit()`
4. **Listing & Retrieval Query Formulation**:
   - `GET /investigations`:
     - Total count: `select(func.count()).select_from(InvestigationCase)`
     - Paginated rows: `select(InvestigationCase).order_by(InvestigationCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)`
   - `GET /investigations/{case_id}`:
     - Fetch case by UUID: `select(InvestigationCase).where(InvestigationCase.id == case_uuid)`
5. **Streaming & Verdict Persistence**:
   - In `StreamingResponse`, holding an active DB session open across `asyncio.sleep` intervals runs the risk of connection pool exhaustion and closed-session exceptions if FastAPI dependencies tear down early.
   - Therefore, opening a brief, dedicated session via `get_session_factory()` when the stream finishes allows atomic update: `case_obj.verdict = verdict_payload; case_obj.status = "COMPLETED"; await session.commit()`.
6. **Graceful Fallback**:
   - To preserve offline demo capability and prevent test breakage, provide `get_optional_db()` dependency that yields `None` when `settings.DATABASE_URL` is empty.
   - In all routes, maintain `INVESTIGATION_CASES` cache so that if `db is None`, operations proceed without error.

---

## 3. Caveats
- **Large Dataset Volume**: For datasets with >50,000 transactions, `session.add_all()` creates 50,000 ORM instances. If datasets scale to hundreds of thousands of rows in future iterations, `session.execute(insert(TransactionRecord), list_of_dicts)` or COPY/chunked batching should be considered.
- **Timestamp Formats**: AMLSim steps are numeric floats (e.g. `1.0`, `2.0`), which `datetime.fromtimestamp(val, tz=timezone.utc)` maps starting from Unix epoch (1970). `parse_timestamp_to_datetime` handles float, ISO string, or numeric steps safely.
- **SQLite In-Memory Type Differences**: In SQLite test environments, `JSONB` compiles to `JSON` and `Vector` compiles to `TEXT` thanks to compiler hooks in `backend/models/forensic.py:36-47`.

---

## 4. Conclusion
1. Implement `get_optional_db()` in `backend/core/database.py` to support dual-mode (PostgreSQL production vs. offline in-memory).
2. Update `backend/api/routes/investigations.py` to:
   - Persist `InvestigationCase` and bulk `TransactionRecord` rows in `POST /upload`.
   - Implement `GET /investigations` with `select(func.count())` and `offset().limit()`.
   - Implement `GET /investigations/{case_id}` retrieving case by UUID.
   - Update `GET /investigations/{case_id}/stream` to persist final verdict and status in PostgreSQL using `get_session_factory()`.
3. Add a dedicated test file `backend/tests/test_investigations.py` verifying model persistence, pagination, detail retrieval, and verdict updates.

---

## 5. Verification Method
1. **Run full automated test suite**:
   ```powershell
   python -m pytest
   ```
2. **Inspect affected files**:
   - `backend/core/database.py` (optional db dependency)
   - `backend/api/routes/investigations.py` (persistence & new endpoints)
   - `backend/tests/test_investigations.py` (new tests)
3. **Invalidation conditions**:
   - `POST /upload` fails to insert records into `transactions` table.
   - `GET /investigations` returns incorrect total count or pagination slice.
   - SSE streaming crashes or fails to set `verdict` and `status="COMPLETED"` in database.
   - Running tests without `DATABASE_URL` causes regressions.
