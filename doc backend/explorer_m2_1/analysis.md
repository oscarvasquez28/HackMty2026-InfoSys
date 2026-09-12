# Technical Analysis: Milestone 2 — Upload Ingestion & Database Relational Persistence

## 1. Executive Summary
Milestone 2 bridges the high-performance Polars/NetworkX data processing pipeline with the async PostgreSQL database layer implemented in Milestone 1. It replaces temporary in-memory-only case storage with persistent relational storage in TigerData PostgreSQL (via SQLAlchemy 2.0 async engine) while maintaining an offline in-memory fallback for environments where `DATABASE_URL` is not configured.

---

## 2. Problem Boundary & Module Analysis

### 2.1 Existing Ingestion Pipeline (`backend/services/ingestion.py`)
- **Input**: CSV file upload (IBM AMLSim format or standard banking logs).
- **Processing**: `read_amlsim_csv(source)` canonicalizes columns (`origin`, `destination`, `amount`, `timestamp`), cleanses nulls and non-positive amounts, and returns:
  - `cleaned_df`: Polars DataFrame with typed columns:
    - `origin` (`pl.Utf8`)
    - `destination` (`pl.Utf8`)
    - `amount` (`pl.Float64`)
    - `timestamp` (`pl.Float64`)
  - `metadata`: Dictionary with `total_records`, `total_volume`, `unique_accounts`, `original_columns`.

### 2.2 Deterministic Filter & Graph Pruning (`backend/services/deterministic_filter.py`)
- **Processing**: `apply_deterministic_filter(df)` constructs a NetworkX `DiGraph`, detects elementary cycles (length 2 to 5), and flags pass-through accounts (retention >= 90% within <= 48h).
- **Output Structure**:
  - `subgraph`:
    - `nodes`: List of dicts `{"id", "total_in", "total_out", "in_degree", "out_degree", "reasons", "risk_score"}`.
      - Potential reasons: `"CIRCULAR_FLOW_CYCLE"`, `"HIGH_VELOCITY_PASSTHROUGH_90PCT"`.
    - `edges`: List of dicts `{"source", "target", "amount", "count", "timestamps", "reasons"}`.
      - Potential reasons: `"CYCLE_STEP"`, `"PASSTHROUGH_BRIDGE"`.
  - `metrics`: Dictionary of topological metrics:
    - `total_nodes_analyzed`, `suspicious_nodes_count`, `pruned_nodes_count`, `total_edges_analyzed`, `suspicious_edges_count`, `pruned_edges_count`, `suspicious_volume_mxn`, `detected_cycles_count`, `passthrough_accounts_count`, `pruning_efficiency_pct`.
  - `patterns`: Dictionary containing:
    - `cycles`: List of detected elementary cycles.
    - `passthrough_accounts`: List of high-velocity mule accounts.

### 2.3 ORM Relational Schema (`backend/models/forensic.py`)
- **`InvestigationCase`**:
  - `id`: `uuid.UUID` (PK).
  - `filename`: `str` (max 255).
  - `status`: `str` (default `"PENDING"`, set to `"PROCESSING"` upon upload, `"COMPLETED"` upon verdict).
  - `created_at`, `updated_at`: DateTime with timezone (`DateTime(timezone=True)`).
  - `ingestion_metadata`: `JSONB` / `JSON_DOCUMENT`.
  - `metrics`: `JSONB` / `JSON_DOCUMENT`.
  - `subgraph`: `JSONB` / `JSON_DOCUMENT`.
  - `patterns`: `JSONB` / `JSON_DOCUMENT`.
  - `verdict`: `JSONB` / `JSON_DOCUMENT` (nullable).
  - `transactions`: One-to-many relationship with `TransactionRecord`, cascade delete.
- **`TransactionRecord`**:
  - `id`: `uuid.UUID` (PK).
  - `case_id`: `uuid.UUID` (FK to `investigation_cases.id`, indexed, `ondelete="CASCADE"`).
  - `origin`: `str` (indexed).
  - `destination`: `str` (indexed).
  - `amount`: `Decimal(18, 2)` (`Numeric(18, 2)`).
  - `timestamp`: DateTime with timezone (`DateTime(timezone=True)`).
  - `is_suspicious`: `bool` (indexed, default `False`).
  - `reasons`: List of strings (`JSONB` / `JSON_DOCUMENT`).

---

## 3. Database Persistence Mechanism for `POST /upload`

### 3.1 Mapping to `InvestigationCase`
Upon completion of Polars CSV parsing and NetworkX pruning:
```python
case_id = uuid.uuid4()
case_obj = InvestigationCase(
    id=case_id,
    filename=file.filename or "dataset.csv",
    status="PROCESSING",
    ingestion_metadata=ingestion_meta,
    metrics=filter_results["metrics"],
    subgraph=filter_results["subgraph"],
    patterns=filter_results["patterns"],
    verdict=None,
)
```

### 3.2 Mapping Polars Rows to `TransactionRecord` Instances
To correlate individual transactions with graph-level pruning results:
1. Extract fast lookup dictionaries from `filter_results["subgraph"]`:
   ```python
   suspicious_edge_map = {
       (e["source"], e["target"]): e.get("reasons", [])
       for e in filter_results.get("subgraph", {}).get("edges", [])
   }
   suspicious_node_map = {
       n["id"]: n.get("reasons", [])
       for n in filter_results.get("subgraph", {}).get("nodes", [])
   }
   ```
2. Convert timestamp float/step/string safely to `datetime`:
   ```python
   def parse_timestamp_to_datetime(val: Any) -> datetime:
       if isinstance(val, datetime):
           return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
       if isinstance(val, (int, float)):
           try:
               return datetime.fromtimestamp(float(val), tz=timezone.utc)
           except (OverflowError, OSError, ValueError):
               return datetime.now(timezone.utc)
       if isinstance(val, str):
           try:
               dt = datetime.fromisoformat(val)
               return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
           except ValueError:
               try:
                   return datetime.fromtimestamp(float(val), tz=timezone.utc)
               except (OverflowError, OSError, ValueError):
                   return datetime.now(timezone.utc)
       return datetime.now(timezone.utc)
   ```
3. Iterate over `df.select(["origin", "destination", "amount", "timestamp"]).to_dicts()`:
   - For each row, check `(orig, dest)` against `suspicious_edge_map`.
   - If present: `is_suspicious = True`, `reasons = list(suspicious_edge_map[(orig, dest)])`.
   - Else check if `orig` or `dest` is in `suspicious_node_map`: if so, mark `is_suspicious = True` with node-specific tags (`f"ORIGIN_{r}"`, `f"DESTINATION_{r}"`).
   - Otherwise: `is_suspicious = False`, `reasons = []`.
   - Construct `TransactionRecord`:
     ```python
     tx = TransactionRecord(
         id=uuid.uuid4(),
         case_id=case_id,
         origin=orig,
         destination=dest,
         amount=Decimal(str(round(float(row["amount"]), 2))),
         timestamp=ts_dt,
         is_suspicious=is_suspicious,
         reasons=reasons,
     )
     ```
4. Commit via async session:
   ```python
   session.add(case_obj)
   session.add_all(transaction_records)
   await session.commit()
   ```

---

## 4. Formulation of Retrieval Endpoints

### 4.1 `GET /api/v1/investigations` (Paginated Listing)
- **Parameters**:
  - `page: int = Query(1, ge=1)`
  - `page_size: int = Query(20, ge=1, le=100)`
  - `status: Optional[str] = Query(None)`
- **SQL Execution**:
  ```python
  count_stmt = select(func.count()).select_from(InvestigationCase)
  if status:
      count_stmt = count_stmt.where(InvestigationCase.status == status)
  total = (await db.execute(count_stmt)).scalar() or 0

  offset = (page - 1) * page_size
  query_stmt = (
      select(InvestigationCase)
      .order_by(InvestigationCase.created_at.desc())
      .offset(offset)
      .limit(page_size)
  )
  if status:
      query_stmt = query_stmt.where(InvestigationCase.status == status)
  cases = (await db.execute(query_stmt)).scalars().all()
  ```
- **Response Format**:
  ```json
  {
    "items": [
      {
        "case_id": "uuid-string",
        "filename": "batch_01.csv",
        "status": "COMPLETED",
        "created_at": "2026-09-12T08:00:00Z",
        "updated_at": "2026-09-12T08:00:05Z",
        "metrics": { ... },
        "has_verdict": true
      }
    ],
    "total": 45,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
  }
  ```

### 4.2 `GET /api/v1/investigations/{case_id}` (Case Detail Retrieval)
- **Parameters**: `case_id: str` (UUID string).
- **Validation**:
  ```python
  try:
      case_uuid = uuid.UUID(case_id)
  except ValueError:
      raise HTTPException(status_code=400, detail="Invalid case UUID format.")
  ```
- **SQL Execution**:
  ```python
  stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
  case = (await db.execute(stmt)).scalar_one_or_none()
  if not case:
      raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
  ```
- **Response Format**:
  ```json
  {
    "case_id": "uuid-string",
    "filename": "batch_01.csv",
    "status": "COMPLETED",
    "created_at": "2026-09-12T08:00:00Z",
    "updated_at": "2026-09-12T08:00:05Z",
    "ingestion": { ... },
    "metrics": { ... },
    "subgraph": { ... },
    "patterns": { ... },
    "verdict": { ... }
  }
  ```

### 4.3 `GET /api/v1/investigations/{case_id}/stream` (SSE Streaming + Terminal Verdict Persistence)
- **Critical Architectural Consideration**:
  FastAPI route dependencies (e.g. `db: AsyncSession = Depends(get_db)`) execute their cleanup block as soon as the route handler returns the `StreamingResponse` object, BEFORE the async generator completes streaming. Holding a session across seconds of `asyncio.sleep` also risks connection pool exhaustion.
- **Solution**:
  1. Retrieve case information at stream start (from DB or fallback).
  2. Inside `generate_n8n_or_simulated_stream`: stream thought events.
  3. When generating the final `verdict_payload`:
     - Update in-memory fallback dict `INVESTIGATION_CASES[case_id]`.
     - If database is configured (`settings.DATABASE_URL`), open a dedicated short-lived session via `get_session_factory()`:
       ```python
       factory = get_session_factory()
       async with factory() as session:
           stmt = select(InvestigationCase).where(InvestigationCase.id == uuid.UUID(case_id))
           case_obj = (await session.execute(stmt)).scalar_one_or_none()
           if case_obj:
               case_obj.verdict = verdict_payload
               case_obj.status = "COMPLETED"
               await session.commit()
       ```
     - Yield final SSE `verdict` event.

---

## 5. Backward-Compatibility & Offline In-Memory Fallback

### 5.1 The `get_optional_db` Dependency
To allow both production TigerData PostgreSQL execution and zero-config offline or test execution, introduce `get_optional_db()` in `backend/core/database.py`:
```python
async def get_optional_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    FastAPI dependency yielding an AsyncSession if DATABASE_URL is configured,
    or None if running in offline in-memory fallback mode.
    """
    if not settings.DATABASE_URL:
        yield None
        return

    try:
        factory = get_session_factory()
    except Exception:
        yield None
        return

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### 5.2 Dual-Layer Persistence Strategy
In `backend/api/routes/investigations.py`:
- Maintain `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}`.
- On upload:
  - Always store record in `INVESTIGATION_CASES[case_id]` (ensures instant local cache).
  - If `db is not None`: also insert `InvestigationCase` and `TransactionRecord` instances into PostgreSQL.
- On list / detail:
  - If `db is not None`: query PostgreSQL; if not found, fall back to `INVESTIGATION_CASES`.
  - If `db is None`: serve directly from `INVESTIGATION_CASES`.
- This ensures 100% test pass without regressions on standard test environments, while enabling full relational persistence when a database is connected.

---

## 6. Implementation Blueprint for Implementer Agent

| Target File | Key Changes |
|---|---|
| `backend/core/database.py` | Add `get_optional_db()` dependency generator. |
| `backend/api/routes/investigations.py` | Update `POST /upload` with `InvestigationCase` and `TransactionRecord` bulk creation. Add `GET /investigations` (paginated) and `GET /investigations/{case_id}`. Update `GET /{case_id}/stream` with terminal DB verdict update. Add `parse_timestamp_to_datetime` helper. |
| `backend/tests/test_investigations.py` | Create comprehensive test suite testing database persistence, transaction insertion, pagination, detail retrieval, and stream verdict updating with in-memory SQLite fixture. |
