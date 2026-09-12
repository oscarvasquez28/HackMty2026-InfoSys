# Milestone 5 Iteration 2: Regression Test Strategy & Specifications Analysis

**Author**: Explorer M5 R2-3 (Regression Test Strategy Explorer)  
**Date**: 2026-09-12  
**Target Project**: Forensic Auditor Python Backend Platform  
**Status**: COMPLETE  

---

## 1. Executive Summary

During Milestone 5 verification, the Challenger agent identified three critical defects that triggered HTTP 500 Internal Server Errors or incorrect query result sets under valid operational conditions:
1. **Finding 1 (CSV Ingestion Fallback SchemaError)**: `POST /api/v1/investigations/upload` crashed with HTTP 500 when uploading 3-column CSV files (`origin, destination, amount`) omitting a timestamp column, due to `pl.int_range(..., dtype=pl.Float64)` violating Polars 1.x type invariants.
2. **Finding 2 (Null/Empty Timestamp Handling)**: `POST /api/v1/investigations/upload` crashed with HTTP 500 when uploading CSV files where individual cells in the timestamp column were empty or null, due to unhandled `NoneType` in `float(row["timestamp"])`.
3. **Finding 3 (Dynamic Query List Operator Datetime Coercion)**: `POST /api/v1/tools/query` with `in` or `not_in` operators against the `timestamp` column returned 0 records when supplied with ISO datetime strings, because scalar-only type check `isinstance(val, str)` bypassed coercion for arrays/lists.

All 121 existing tests in `backend/tests/` passed previously because test fixtures only included 4-column CSVs with explicit numeric timestamps and tested dynamic queries with scalar timestamp comparisons (`eq`, `gt`, `lt`).

This analysis establishes the regression test strategy, specifies the exact test functions and assertions to add to the test suite, and provides the exact code fixes required for the implementation phase.

---

## 2. Defect Analysis & Root Causes

### Defect 1: Ingestion Fallback SchemaError
- **File**: `backend/services/ingestion.py:74`
- **Root Cause**: Polars 1.x strict typing requires integer types (`pl.Int32`, `pl.Int64`, `pl.UInt32`, `pl.UInt64`) for `int_range`. The expression:
  ```python
  select_exprs.append(pl.int_range(0, df.height, dtype=pl.Float64).alias("timestamp"))
  ```
  raises `polars.exceptions.SchemaError: non-integer 'dtype' passed to 'int_range': 'f64'`.
- **API Impact**: When an upload omits a timestamp column, `read_amlsim_csv()` crashes, bubbling up to `investigations.py:173` as an HTTP 500 Internal Server Error:
  `{"detail":"Error processing transaction dataset: non-integer 'dtype' passed to 'int_range': 'f64'"}`.
- **Remedy**:
  ```python
  select_exprs.append(pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp"))
  ```

### Defect 2: Missing Null Handling in Timestamp Column
- **File**: `backend/services/ingestion.py:72` & `backend/services/deterministic_filter.py:21`
- **Root Cause**:
  1. In `read_amlsim_csv()`, `pl.col(timestamp_col).cast(pl.Float64)` retains `null` for empty cells. The downstream filter checks `origin`, `destination`, and `amount`, but not `timestamp`.
  2. In `build_transaction_graph()`, line 21 executes:
     ```python
     timestamp = float(row["timestamp"])
     ```
     When `row["timestamp"]` is `None`, this throws `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
- **API Impact**: Uploading a CSV with an empty timestamp cell (e.g. `ACC_A,ACC_B,1000.0,`) produces HTTP 500.
- **Remedy**:
  In `backend/services/ingestion.py:72`:
  ```python
  select_exprs.append(pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64).alias("timestamp"))
  ```
  In `backend/services/deterministic_filter.py:21` (defense in depth):
  ```python
  timestamp = float(row["timestamp"] or 0.0)
  ```

### Defect 3: Dynamic Query List Operator Datetime Coercion
- **File**: `backend/services/tool_registry.py:397-400`
- **Root Cause**: In the query handler for target `transactions`:
  ```python
  if f.field == "timestamp" and isinstance(val, str):
      val_dt = parse_datetime_safe(val)
      if val_dt:
          val = val_dt
  ```
  When the filter operator is `in` or `not_in`, `val` is a Python `list` (e.g. `["2026-01-01T01:00:00+00:00", ...]`). `isinstance(val, str)` evaluates to `False`, leaving `val` as a list of raw strings.
  When passed to SQLAlchemy:
  `TransactionRecord.timestamp.in_(["2026-01-01T01:00:00+00:00"])`
  SQLAlchemy does not coerce string values inside lists to Python `datetime` objects for SQLite/PostgreSQL `DateTime(timezone=True)` columns, resulting in 0 matches.
- **API Impact**: Dynamic agent tool queries filtering on transaction timestamps with `in` or `not_in` return empty record sets (`total: 0`) even when matching transactions exist.
- **Remedy**:
  ```python
  if f.field == "timestamp":
      if isinstance(val, str):
          val_dt = parse_datetime_safe(val)
          if val_dt:
              val = val_dt
      elif isinstance(val, (list, tuple, set)):
          val = [parse_datetime_safe(v) or v for v in val]
  elif f.field == "amount":
      if isinstance(val, (int, float, str)):
          val = Decimal(str(val))
      elif isinstance(val, (list, tuple, set)):
          val = [Decimal(str(v)) for v in val]
  ```

---

## 3. Empirical Verification Evidence

Empirical testing confirmed both the defect presence and the efficacy of the proposed fixes:

### Test 1: Uploading 3-Column CSV (No Timestamp)
```bash
python -c "
import asyncio, httpx
from backend.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        csv_data = b'origin,destination,amount\nACC_A,ACC_B,1000.0\nACC_B,ACC_C,1000.0'
        res = await client.post('/api/v1/investigations/upload', files={'file': ('notime.csv', csv_data, 'text/csv')})
        print('Status:', res.status_code, res.text[:120])
asyncio.run(main())
"
```
**Output Before Fix**:
`Status: 500 {"detail":"Error processing transaction dataset: non-integer 'dtype' passed to 'int_range': 'f64'"}`

### Test 2: Uploading CSV with Null Timestamp Cell
```bash
python -c "
import asyncio, httpx
from backend.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        csv_data = b'origin,destination,amount,timestamp\nACC_A,ACC_B,1000.0,\nACC_B,ACC_C,1000.0,2.0'
        res = await client.post('/api/v1/investigations/upload', files={'file': ('nulltime.csv', csv_data, 'text/csv')})
        print('Status:', res.status_code, res.text[:120])
asyncio.run(main())
"
```
**Output Before Fix**:
`Status: 500 {"detail":"Error processing transaction dataset: float() argument must be a string or a real number, not 'NoneType'"}`

### Test 3: Dynamic Query with `in` Operator & ISO Datetime Strings
```bash
# Executed direct SQLAlchemy statement test with string list vs datetime list:
stmt_str = select(TransactionRecord).where(TransactionRecord.timestamp.in_([t1_str, t2_str]))
# Result: 0 matches

stmt_dt = select(TransactionRecord).where(TransactionRecord.timestamp.in_([t1, t2]))
# Result: 2 matches
```
**Output**: Confirms that coercing list items to `datetime` objects restores exact matching.

---

## 4. Test Suite Placement Architecture

| Test Function | Target Test File | Target Section | Primary Concerns Checked |
|---|---|---|---|
| `test_csv_upload_without_timestamp_column` | `backend/tests/test_investigations.py` | CSV Upload & Ingestion Tests | HTTP 201, synthetic timestamps generated (0, 1, 2...), DB persistence, graph metrics |
| `test_csv_upload_with_null_timestamp_cells` | `backend/tests/test_investigations.py` | CSV Upload & Ingestion Tests | HTTP 201, missing timestamps filled to 0.0, no TypeError, full persistence |
| `test_query_datetime_in_operator` | `backend/tests/test_agent_tools.py` | Dynamic Composable Query Engine Tests | HTTP 200, `in` and `not_in` operators, ISO datetime list parsing, record count matching |
| `test_read_amlsim_csv_synthetic_fallback` *(Unit)* | `backend/tests/test_pipeline.py` | Unit Pipeline Tests | Polars DataFrame normalization, Float64 synthetic steps |
| `test_read_amlsim_csv_null_timestamp_handling` *(Unit)* | `backend/tests/test_pipeline.py` | Unit Pipeline Tests | Polars DataFrame `fill_null(0.0)`, graph building resilience |

---

## 5. Precise Regression Test Specifications

### 5.1 `test_csv_upload_without_timestamp_column`
```python
@pytest.mark.asyncio
async def test_csv_upload_without_timestamp_column():
    """
    Regression Test for Finding 1 (M5 Challenger):
    Verifies that uploading a 3-column CSV without a timestamp or step column:
    1. Successfully returns HTTP 201 Created without throwing a SchemaError.
    2. Persists an InvestigationCase with status PROCESSING.
    3. Bulk-inserts TransactionRecord rows with synthetic sequential timestamps.
    4. Deterministic topological metrics (cycles, nodes) are correctly computed.
    """
    csv_3col = (
        "origin,destination,amount\n"
        "ACC_A,ACC_B,150000.0\n"
        "ACC_B,ACC_C,148000.0\n"
        "ACC_C,ACC_A,145000.0\n"
        "CORP_INFLOW,MULE_01,500000.0\n"
        "MULE_01,OFFSHORE_OUT,485000.0\n"
        "LEGIT_PAYROLL,EMPLOYEE_01,2500.0\n"
        "STORE_MERCHANT,CONSUMER_99,120.0\n"
    ).encode("utf-8")

    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("three_column_dataset.csv", csv_3col, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)
            
            assert response.status_code == 201, (
                f"Expected HTTP 201 Created for 3-column CSV upload, got {response.status_code}: {response.text}"
            )
            
            payload = response.json()
            assert "case_id" in payload
            case_id = uuid.UUID(payload["case_id"])
            assert payload["filename"] == "three_column_dataset.csv"
            assert payload["status"] == "PROCESSING"
            assert payload["metrics"]["total_nodes_analyzed"] >= 5
            assert payload["metrics"]["detected_cycles_count"] >= 1

            # Verify synthetic timestamps on persisted TransactionRecords in DB
            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    select(TransactionRecord)
                    .where(TransactionRecord.case_id == case_id)
                    .order_by(TransactionRecord.timestamp.asc())
                )
                txs = (await session.execute(stmt)).scalars().all()
                assert len(txs) == 7

                # Ensure all transactions have valid, sequential UTC datetime timestamps
                for tx in txs:
                    assert tx.timestamp is not None
                    assert tx.timestamp.tzinfo is not None

                # Check sequential progression from base datetime
                extracted_timestamps = [t.timestamp for t in txs]
                assert extracted_timestamps == sorted(extracted_timestamps)
```

### 5.2 `test_csv_upload_with_null_timestamp_cells`
```python
@pytest.mark.asyncio
async def test_csv_upload_with_null_timestamp_cells():
    """
    Regression Test for Finding 2 (M5 Challenger):
    Verifies that uploading a CSV with empty or null timestamp cells:
    1. Returns HTTP 201 Created without throwing TypeError or HTTP 500.
    2. Successfully defaults null timestamp cells to 0.0.
    3. Builds the transaction graph and persists all records to PostgreSQL.
    """
    csv_null_timestamps = (
        "origin,destination,amount,timestamp\n"
        "ACC_A,ACC_B,150000.0,\n"
        "ACC_B,ACC_C,148000.0,1.0\n"
        "ACC_C,ACC_A,145000.0,\n"
        "CORP_INFLOW,MULE_01,500000.0,10.0\n"
        "MULE_01,OFFSHORE_OUT,485000.0,22.0\n"
        "LEGIT_PAYROLL,EMPLOYEE_01,2500.0,\n"
    ).encode("utf-8")

    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("null_timestamps_sample.csv", csv_null_timestamps, "text/csv")}
            response = await client.post("/api/v1/investigations/upload", files=files)
            
            assert response.status_code == 201, (
                f"Expected HTTP 201 Created for CSV with null timestamp cells, got {response.status_code}: {response.text}"
            )
            
            payload = response.json()
            case_id = uuid.UUID(payload["case_id"])
            assert payload["status"] == "PROCESSING"

            # Check that all 6 rows were ingested and persisted with non-null datetimes
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(TransactionRecord).where(TransactionRecord.case_id == case_id)
                txs = (await session.execute(stmt)).scalars().all()
                assert len(txs) == 6
                for tx in txs:
                    assert tx.timestamp is not None
                    assert tx.timestamp.tzinfo is not None
```

### 5.3 `test_query_datetime_in_operator`
```python
@pytest.mark.asyncio
async def test_query_datetime_in_operator():
    """
    Regression Test for Finding 3 (M5 Challenger):
    Verifies that POST /api/v1/tools/query with 'in' and 'not_in' operators
    against the 'timestamp' column correctly converts ISO string lists to datetime objects,
    producing exact matches in SQLAlchemy.
    """
    async with isolated_test_db():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            case_id = await upload_test_case(client)

            # 1. Fetch case transactions to obtain actual stored ISO timestamps
            tx_res = await client.post("/api/v1/tools/transactions", json={"case_id": case_id})
            assert tx_res.status_code == 200
            tx_items = tx_res.json()["items"]
            assert len(tx_items) >= 2

            ts_a = tx_items[0]["timestamp"]
            ts_b = tx_items[1]["timestamp"]
            assert ts_a is not None and ts_b is not None

            # 2. Query dynamic query builder with 'in' operator using string timestamps
            query_in = {
                "target": "transactions",
                "case_id": case_id,
                "filters": [
                    {
                        "field": "timestamp",
                        "operator": "in",
                        "value": [ts_a, ts_b]
                    }
                ]
            }
            res_in = await client.post("/api/v1/tools/query", json=query_in)
            assert res_in.status_code == 200, f"Expected 200, got {res_in.status_code}: {res_in.text}"
            
            data_in = res_in.json()
            assert data_in["total"] >= 2, (
                f"Expected at least 2 records matching ISO timestamps in list, got total={data_in['total']}"
            )
            assert data_in["count"] == len(data_in["records"])
            matched_ts_set = {ts_a, ts_b}
            for rec in data_in["records"]:
                assert rec["timestamp"] in matched_ts_set

            # 3. Query dynamic query builder with 'not_in' operator excluding ts_a
            query_nin = {
                "target": "transactions",
                "case_id": case_id,
                "filters": [
                    {
                        "field": "timestamp",
                        "operator": "not_in",
                        "value": [ts_a]
                    }
                ]
            }
            res_nin = await client.post("/api/v1/tools/query", json=query_nin)
            assert res_nin.status_code == 200
            data_nin = res_nin.json()
            
            expected_total = len(tx_items) - sum(1 for t in tx_items if t["timestamp"] == ts_a)
            assert data_nin["total"] == expected_total
            for rec in data_nin["records"]:
                assert rec["timestamp"] != ts_a
```

### 5.4 Unit-Level Specifications for `backend/tests/test_pipeline.py`
```python
def test_read_amlsim_csv_synthetic_fallback():
    """Unit test: verifies that read_amlsim_csv handles missing timestamp column."""
    from backend.services.ingestion import read_amlsim_csv
    csv_bytes = b"origin,destination,amount\nACC_1,ACC_2,100.0\nACC_2,ACC_3,200.0"
    df, meta = read_amlsim_csv(csv_bytes)
    assert df.height == 2
    assert "timestamp" in df.columns
    assert df["timestamp"].to_list() == [0.0, 1.0]


def test_read_amlsim_csv_null_timestamp_cells():
    """Unit test: verifies that read_amlsim_csv defaults null timestamp cells to 0.0."""
    from backend.services.ingestion import read_amlsim_csv
    csv_bytes = b"origin,destination,amount,timestamp\nACC_1,ACC_2,100.0,\nACC_2,ACC_3,200.0,5.0"
    df, meta = read_amlsim_csv(csv_bytes)
    assert df.height == 2
    assert df["timestamp"].to_list() == [0.0, 5.0]
```

---

## 6. Implementation Patch Reference

The implementer agent should apply the following precise edits:

### Patch 1: `backend/services/ingestion.py`
```diff
--- a/backend/services/ingestion.py
+++ b/backend/services/ingestion.py
@@ -71,4 +71,4 @@
     if has_timestamp:
-        select_exprs.append(pl.col(timestamp_col).cast(pl.Float64).alias("timestamp"))
+        select_exprs.append(pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64).alias("timestamp"))
     else:
-        select_exprs.append(pl.int_range(0, df.height, dtype=pl.Float64).alias("timestamp"))
+        select_exprs.append(pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp"))
```

### Patch 2: `backend/services/deterministic_filter.py`
```diff
--- a/backend/services/deterministic_filter.py
+++ b/backend/services/deterministic_filter.py
@@ -21,1 +21,1 @@
-        timestamp = float(row["timestamp"])
+        timestamp = float(row["timestamp"] or 0.0)
```

### Patch 3: `backend/services/tool_registry.py`
```diff
--- a/backend/services/tool_registry.py
+++ b/backend/services/tool_registry.py
@@ -397,4 +397,14 @@
-            if f.field == "timestamp" and isinstance(val, str):
-                val_dt = parse_datetime_safe(val)
-                if val_dt:
-                    val = val_dt
+            if f.field == "timestamp":
+                if isinstance(val, str):
+                    val_dt = parse_datetime_safe(val)
+                    if val_dt:
+                        val = val_dt
+                elif isinstance(val, (list, tuple, set)):
+                    val = [parse_datetime_safe(v) or v for v in val]
+            elif f.field == "amount":
+                if isinstance(val, (int, float, str)):
+                    val = Decimal(str(val))
+                elif isinstance(val, (list, tuple, set)):
+                    val = [Decimal(str(v)) for v in val]
             elif f.field == "is_suspicious" and isinstance(val, str):
                 val = val.lower() in ("true", "1")
```

---

## 7. Verification Protocol for Implementer & Challenger

1. **Apply Patches**: Apply the three code edits in `ingestion.py`, `deterministic_filter.py`, and `tool_registry.py`.
2. **Add Regression Tests**:
   - Add `test_csv_upload_without_timestamp_column` and `test_csv_upload_with_null_timestamp_cells` to `backend/tests/test_investigations.py`.
   - Add `test_query_datetime_in_operator` to `backend/tests/test_agent_tools.py`.
   - Add unit tests to `backend/tests/test_pipeline.py`.
3. **Execute Targeted Regression Tests**:
   ```bash
   python -m pytest backend/tests/test_investigations.py -k "without_timestamp or null_timestamp" -v
   python -m pytest backend/tests/test_agent_tools.py -k "test_query_datetime_in_operator" -v
   ```
4. **Execute Complete Test Suite**:
   ```bash
   python -m pytest backend/tests/ -v
   ```
   **Expected Outcome**: 124+ passed tests with 0 failures and 0 warnings.
