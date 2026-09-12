# Adversarial White-Box Coverage & Hardening Analysis — Milestone 5

## 1. Executive Summary

- **Role**: Empirical Challenger 2 (Milestone 5)
- **Target**: Forensic Auditor Python Backend Platform
- **Scope**: Full codebase (`backend/app/**`, `backend/core/**`, `backend/models/**`, `backend/services/**`, `backend/api/**`, `backend/tests/**`)
- **Baseline Test Suite Result**: 121 passed in 44.67s
- **Overall Risk Assessment**: **HIGH (Critical Ingestion Defect Uncovered)**
- **Verdict**: **REJECT**

While the baseline automated test suite contains 121 passing tests, white-box adversarial stress testing uncovered a critical dormant defect in the CSV ingestion pipeline (`backend/services/ingestion.py:74`). When an AML transaction dataset is provided without an explicit timestamp column—a supported and documented feature designed to fall back to synthetic sequential steps—Polars raises an unhandled `polars.exceptions.SchemaError: non-integer 'dtype' passed to 'int_range': 'f64'`. This causes `POST /api/v1/investigations/upload` to crash with an **HTTP 500 Internal Server Error**, breaking R2 acceptance criteria for datasets lacking timestamps.

---

## 2. Adversarial Challenge & Stress-Testing Matrix

| # | Dimension / Component | Test Scenario / Attack Vector | Predicted / Expected Behavior | Actual Behavior | Result |
|---|-----------------------|--------------------------------|--------------------------------|-----------------|--------|
| 1 | Ingestion (`ingestion.py`) | CSV upload without timestamp column (`origin,destination,amount`) | Fallback to synthetic sequential step timestamps, HTTP 201 | HTTP 500 `SchemaError: non-integer dtype passed to int_range: 'f64'` | **FAIL (Finding 1)** |
| 2 | Ingestion / Filtering | CSV upload with empty/null cell in timestamp column (`A,B,100,`) | Graceful handling or 422 Unprocessable Entity | HTTP 500 `TypeError: float() argument must be a string or a real number, not 'NoneType'` | **FAIL (Finding 2)** |
| 3 | Dynamic Query Engine | `timestamp` filter using `in` operator with list of ISO strings | Coerce all ISO string items in list to `datetime` objects | Status 200 but returns 0 records due to unparsed strings in list | **FAIL (Finding 3)** |
| 4 | Database Normalization | Obfuscation of database credentials in logs | Passwords masked as `:****@` | Sanitized correctly without credential leak | **PASS** |
| 5 | Database Error Handling | Empty `DATABASE_URL` during `get_engine()` | Descriptive `RuntimeError` explaining configuration gap | Clear informative `RuntimeError` raised | **PASS** |
| 6 | Graph Filter Pruning | Self-loops (`A -> A`) and single transactions | Isolated without cycle crashes, pruned efficiency calculated | Correctly handles self-loops and single transactions | **PASS** |
| 7 | Graph Filter Pruning | Empty dataframe passed to filter pipeline | Pruning efficiency defaults to 0.0% without ZeroDivisionError | Correctly handled | **PASS** |
| 8 | Multi-Target Dynamic Queries | Dynamic query builder across all 10 registered targets | Clean 200 OK responses with matching schemas | All 10 targets verified working cleanly | **PASS** |
| 9 | SQL Injection Resistance | Non-whitelisted columns, sort fields, raw SQL injection probes | Rejection with HTTP 422 or 400 | Rejection enforced at schema and registry levels | **PASS** |
| 10 | Legal Precedents Vector Search | Query vector with all zeros (`[0.0] * 1536`) | Prevent zero-division error in vector norm calculation | Zero norm guard `or 1.0` functions as designed, HTTP 200 | **PASS** |
| 11 | TTS Streaming Proxy | Client disconnect mid-stream | Clean connection teardown without socket leak | `asyncio.CancelledError` caught and re-raised cleanly | **PASS** |
| 12 | TTS Synthetic Silence Fallback | Offline mode or upstream 500/401/429 | Bitwise valid 320-byte MPEG frame with `X-Audio-Source` header | Bitwise valid MPEG frame emitted | **PASS** |

---

## 3. Empirical Vulnerabilities & Bugs Found

### Finding 1: Fatal SchemaError in Polars Ingestion on Datasets Without Timestamps (Severity: HIGH / CRITICAL)
- **File**: `backend/services/ingestion.py:74`
- **Code**:
  ```python
  if has_timestamp:
      select_exprs.append(pl.col(timestamp_col).cast(pl.Float64).alias("timestamp"))
  else:
      select_exprs.append(pl.int_range(0, df.height, dtype=pl.Float64).alias("timestamp"))
  ```
- **Root Cause**: Polars expression `pl.int_range(start, end, dtype=...)` strictly requires an integer data type (`pl.Int64`, `pl.Int32`, etc.). Passing `dtype=pl.Float64` raises:
  `polars.exceptions.SchemaError: non-integer 'dtype' passed to 'int_range': 'f64'`.
- **Reproduction**:
  ```python
  import asyncio, httpx
  from backend.main import app

  async def reproduce():
      transport = httpx.ASGITransport(app=app)
      async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
          csv_data = b"origin,destination,amount\nACC_A,ACC_B,1000.0\nACC_B,ACC_C,1000.0"
          res = await client.post("/api/v1/investigations/upload", files={"file": ("dataset_notime.csv", csv_data, "text/csv")})
          print("Status:", res.status_code)
          print("Body:", res.text)

  asyncio.run(reproduce())
  ```
  **Output**:
  ```json
  Status: 500
  Body: {"detail":"Error processing transaction dataset: non-integer `dtype` passed to `int_range`: 'f64'"}
  ```
- **Blast Radius**: Any user or AI agent uploading a transaction CSV without an explicit timestamp column receives an HTTP 500 crash instead of an HTTP 201 response.
- **Recommended Fix**: Change line 74 to:
  ```python
  select_exprs.append(pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp"))
  ```

---

### Finding 2: Unhandled NoneType in Graph Building when CSV Has Missing Timestamp Cell (Severity: MEDIUM)
- **File**: `backend/services/ingestion.py:78` and `backend/services/deterministic_filter.py:21`
- **Code**:
  In `read_amlsim_csv`:
  ```python
  cleaned_df = (
      df.select(select_exprs)
      .filter(
          pl.col("origin").is_not_null()
          & pl.col("destination").is_not_null()
          & pl.col("amount").is_not_null()
          & (pl.col("amount") > 0)
      )
  )
  ```
  In `build_transaction_graph`:
  ```python
  timestamp = float(row["timestamp"])
  ```
- **Root Cause**: `timestamp` is not filtered for nulls in `cleaned_df`. If a CSV contains an empty cell in the timestamp column (e.g. `A,B,100,`), Polars produces a `null` value. When `build_transaction_graph` iterates over the rows, `float(None)` raises:
  `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
  This bubbles up as an HTTP 500 error in `upload_investigation_dataset`.
- **Recommended Fix**: In `backend/services/ingestion.py`, add `.fill_null(0.0)` or require non-null timestamps:
  ```python
  select_exprs.append(pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64).alias("timestamp"))
  ```

---

### Finding 3: Missing Datetime Coercion in Dynamic Query Engine for List Operators (Severity: LOW)
- **File**: `backend/services/tool_registry.py:397-401`
- **Code**:
  ```python
  if f.field == "timestamp" and isinstance(val, str):
      val_dt = parse_datetime_safe(val)
      if val_dt:
          val = val_dt
  ```
- **Root Cause**: When a client uses `in` or `not_in` operators on the `timestamp` field (e.g. `{"field": "timestamp", "operator": "in", "value": ["2026-01-01T12:00:00Z"]}`), `val` is a `list` of strings. Because `isinstance(val, str)` evaluates to `False`, the individual strings are never coerced to `datetime` objects. In SQLAlchemy, comparing a SQL `DateTime` column against raw Python strings in an `IN` clause fails to match, silently returning 0 records.
- **Recommended Fix**:
  ```python
  if f.field == "timestamp":
      if isinstance(val, str):
          val_dt = parse_datetime_safe(val)
          if val_dt:
              val = val_dt
      elif isinstance(val, (list, tuple, set)):
          val = [parse_datetime_safe(v) or v for v in val]
  ```

---

## 4. Acceptance Criteria Compliance Matrix

| Requirement | Acceptance Criterion | Status | Empirical Observation |
|---|---|---|---|
| R1 (DB Engine) | SQLAlchemy async engine initializes with SSL (`sslmode=require`) & pooling | **SATISFIED** | Validated via `normalize_database_url` tests; connection pooling parameters match configuration |
| R1 (DB Models) | Models defined with UUID, JSONB, Vector(1536) & HNSW index | **SATISFIED** | Validated via `models/forensic.py` and SQLite `@compiles` hooks |
| R1 (DB Session) | `get_db` yields managed transactional session | **SATISFIED** | Validated in integration tests; automatic commit and rollback verified |
| R1 (DB Errors) | Missing configuration produces clear, informative errors | **SATISFIED** | Empirical test verified `RuntimeError` on missing `DATABASE_URL` |
| R2 (Upload) | `POST /upload` persists case and individual transactions | **DEFECT** | Works for 4-column CSVs, but **crashes with HTTP 500** on 3-column CSVs without timestamps |
| R2 (Pagination) | `GET /investigations` returns paginated case history | **SATISFIED** | Verified with query parameters `page`, `page_size`, `status` |
| R2 (Detail) | `GET /investigations/{case_id}` returns full case record & subgraph | **SATISFIED** | Verified in SQLite and in-memory modes |
| R2 (SSE Stream) | `GET /investigations/{case_id}/stream` streams SSE thoughts & persists verdict | **SATISFIED** | 6 thought steps + terminal verdict persisted into DB; status updated to `COMPLETED` |
| R3 (Transactions) | `POST /tools/transactions` filters by case, accounts, amounts, suspicion | **SATISFIED** | Verified with boundary amounts and suspicion filters |
| R3 (Entities) | `POST /tools/entities` returns detailed inflows, outflows, risk scores | **SATISFIED** | Verified with entity-specific queries and net flow computations |
| R3 (Patterns) | `POST /tools/patterns` returns detected cycles and mule accounts | **SATISFIED** | Verified across all pattern types (`all`, `cycles`, `passthrough_mules`) |
| R3 (Precedents) | `POST /tools/legal-precedents` executes vector similarity search | **SATISFIED** | Verified against Mexican AML jurisprudence (CFF 69-B, UIF, NIF A-2) |
| R3 (Dynamic Query) | `POST /tools/query` safely executes structured composable filter queries | **SATISFIED** | Verified with whitelisting and parameterized ASTs across all 10 targets |
| R4 (TTS Proxy) | `POST /tts/synthesize` streams MP3 or silent MPEG fallback frame | **SATISFIED** | Verified proxy streaming and synthetic fallback mode (320-byte valid MPEG frame) |
| R5 (Health) | `GET /health` returns status healthy | **SATISFIED** | Verified HTTP 200 with `status="healthy"` |
| R5 (Tests) | All automated tests in `backend/tests/` pass cleanly | **SATISFIED (Dormant Gap)** | 121 tests pass, but gap in missing-timestamp coverage allowed Finding 1 to go undetected |

---

## 5. Conclusion & Final Verdict

**Verdict: REJECT**

The platform demonstrates high quality across the database layer, agent tools router, dynamic query engine, SSE streaming, and speech synthesis. However, **Finding 1 is a blocking defect** in `backend/services/ingestion.py:74`:
A fundamental feature of transaction ingestion (optional timestamp fallback) raises an unhandled `polars.exceptions.SchemaError` resulting in **HTTP 500 Internal Server Error**.

Milestone 5 must be rejected until:
1. `backend/services/ingestion.py:74` is corrected from `pl.int_range(0, df.height, dtype=pl.Float64)` to `pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64)`.
2. Timestamp null-safety is addressed in `read_amlsim_csv`.
3. An automated regression test verifying CSV upload without a timestamp column is added to `backend/tests/test_investigations.py`.
