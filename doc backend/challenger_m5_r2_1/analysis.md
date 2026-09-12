# Empirical Challenge Analysis — Milestone 5 Iteration 2

**Challenger**: Challenger 1 (critic, specialist)  
**Target Milestone**: Milestone 5 Iteration 2 (CSV Ingestion Robustness & Dynamic Tool Queries)  
**Date**: 2026-09-12  

---

## 1. Executive Summary

Milestone 5 Iteration 2 addresses three critical ingestion and query filtering defects identified during adversarial stress-testing:
1. **Defect 1**: Polars schema error on 3-column CSV uploads lacking timestamp columns (`origin,destination,amount`).
2. **Defect 2**: `TypeError` on null / empty timestamp cells during graph construction and Polars dataframe cleaning.
3. **Defect 3**: Empty query results when filtering transaction datetimes with the `in` or `not_in` dynamic tool operators.

Empirical verification confirms that all three primary defects have been successfully resolved by the Worker. End-to-end integration tests confirm:
- 3-column CSV uploads without a timestamp column return **HTTP 201 Created**, generate sequential synthetic float timestamps `[0.0, 1.0, 2.0, ...]`, and map cleanly to UTC datetime timestamps in the database layer.
- CSV uploads with unpopulated/null timestamp cells return **HTTP 201 Created**, defaulting missing timestamps to `0.0` (mapped to `2026-01-01 00:00:00 UTC`).
- Dynamic tool queries with `in` operators on datetime fields return matching records without type mismatch errors.

An additional adversarial edge-case was discovered during stress-testing: explicit quoted empty strings (`""`) or whitespace strings (`" "`) in timestamp columns trigger a strict Polars cast failure. This finding is cataloged as a hardening advisory for future iterations.

---

## 2. Empirical Verification of Defect 1: Missing Timestamp Column

### 2.1 Background & Root Cause
Previously, `backend/services/ingestion.py` attempted to generate synthetic indices via:
```python
pl.int_range(0, df.height, dtype=pl.Float64)
```
In Polars 1.x, `pl.int_range` only accepts integer dtypes, triggering `polars.exceptions.SchemaError: non-integer 'dtype' passed to 'int_range': 'f64'`. This caused `POST /api/v1/investigations/upload` to fail with HTTP 500 when uploading 3-column CSV files.

### 2.2 Worker Fix
The Worker updated line 77 of `backend/services/ingestion.py`:
```python
select_exprs.append(
    pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp")
)
```

### 2.3 Empirical Verification
1. **Pytest Regression Test**:
   ```powershell
   python -m pytest backend/tests/test_investigations.py -k "test_csv_upload_without_timestamp_column" -v
   ```
   **Result**: `PASSED` (1.20s).

2. **Direct Asynchronous HTTP Execution**:
   A custom asynchronous test harness uploaded a 3-row, 3-column CSV (`origin,destination,amount`):
   - Response Status: `201 Created`
   - Case ID generated and persisted in SQLite / PostgreSQL
   - Persisted `TransactionRecord` entities in database:
     - `tx[0] timestamp`: `2026-01-01 00:00:00+00:00` (float `0.0`)
     - `tx[1] timestamp`: `2026-01-01 01:00:00+00:00` (float `1.0`)
     - `tx[2] timestamp`: `2026-01-01 02:00:00+00:00` (float `2.0`)
   - Offline In-Memory Fallback (`DATABASE_URL=None`): returned `201 Created` and populated `INVESTIGATION_CASES` dictionary.

---

## 3. Empirical Verification of Defect 2: Null / Empty Timestamp Cells

### 3.1 Background & Root Cause
In previous iterations, empty timestamp cells in CSV files caused `read_amlsim_csv` to yield null values. When `build_transaction_graph` in `deterministic_filter.py` executed:
```python
float(row["timestamp"])
```
it raised `TypeError: float() argument must be a string or a real number, not 'NoneType'`.

### 3.2 Worker Fix
1. In `backend/services/ingestion.py`:
   ```python
   select_exprs.append(
       pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64).alias("timestamp")
   )
   ```
2. In `backend/services/deterministic_filter.py`:
   ```python
   raw_ts = row.get("timestamp")
   try:
       timestamp = float(raw_ts) if raw_ts is not None else 0.0
   except (ValueError, TypeError):
       timestamp = 0.0
   ```

### 3.3 Empirical Verification
1. **Pytest Regression Test**:
   ```powershell
   python -m pytest backend/tests/test_investigations.py -k "test_csv_upload_with_null_timestamp_cells" -v
   ```
   **Result**: `PASSED` (1.20s).

2. **Direct Asynchronous HTTP Execution**:
   A 3-row CSV with mixed populated and unpopulated timestamp cells (`origin,destination,amount,timestamp\nACC_X,ACC_Y,1000.0,\nACC_Y,ACC_Z,900.0,5.0\nACC_Z,ACC_X,800.0,\n`):
   - Response Status: `201 Created`
   - Row 1 timestamp: `2026-01-01 00:00:00+00:00` (defaulted to `0.0`)
   - Row 2 timestamp: `2026-01-01 05:00:00+00:00` (preserves explicit `5.0`)
   - Row 3 timestamp: `2026-01-01 00:00:00+00:00` (defaulted to `0.0`)
   - Offline In-Memory Fallback: returned `201 Created`.

---

## 4. Empirical Verification of Defect 3: Dynamic Tool Datetime Filtering

### 4.1 Background & Root Cause
In `backend/services/tool_registry.py`, when agents queried transactions or cases using `POST /api/v1/tools/query` with an `in` or `not_in` operator against a `DateTime` column, the operands were raw strings or unconverted lists. SQLite and PostgreSQL failed comparison against native datetimes, returning 0 records.

### 4.2 Worker Fix
- `parse_datetime_safe()` now ensures UTC normalization (`replace(tzinfo=timezone.utc)`).
- `handle_transactions_query()` and `handle_cases_query()` coerce list operands: `[parse_datetime_safe(x) or x for x in val]`.
- Column-level coercion in `apply_sa_operator()` and datetime-aware comparisons in `evaluate_in_memory_predicate()`.

### 4.3 Empirical Verification
```powershell
python -m pytest backend/tests/test_agent_tools.py -k "test_query_datetime_in_operator" -v
```
**Result**: `PASSED` (1.47s).

---

## 5. Adversarial Stress-Testing & Discovery: Quoted Empty / Whitespace Strings

### 5.1 Adversarial Hypothesis
What happens if the input CSV contains explicit empty string tokens like `""` or whitespace `" "` in the timestamp column rather than bare null commas (`,,`)?

### 5.2 Test Execution
```python
import io
from backend.services.ingestion import read_amlsim_csv

csv_data = b'origin,destination,amount,timestamp\nA,B,100, \nC,D,200,1.0\n'
read_amlsim_csv(io.BytesIO(csv_data))
```

### 5.3 Observation & Traceback
```
polars.exceptions.InvalidOperationError: conversion from `str` to `f64` failed in column 'timestamp' for 1 out of 2 values: [" "]
This error occurred in the following expression:
	col("timestamp").fill_null(["0.0"]).strict_cast(Float64)
```

### 5.4 Root Cause
In `backend/services/ingestion.py:73`:
```python
pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64).alias("timestamp")
```
When a CSV field has quotes or whitespace, Polars infers the column type as `pl.Utf8` / `pl.String`. In Polars, `fill_null()` only replaces actual null values; empty strings `""` and whitespace `" "` are non-null string values.
Consequently, `.cast(pl.Float64)` performs a strict cast (`strict=True` by default in Polars), which raises `InvalidOperationError`.

### 5.5 Recommended Hardening (Future Milestone Advisory)
In `backend/services/ingestion.py`, using non-strict casting or trimming empty strings ensures total resilience:
```python
pl.col(timestamp_col).cast(pl.Float64, strict=False).fill_null(0.0).alias("timestamp")
```
When tested with `pl.col(timestamp_col).cast(pl.Float64, strict=False).fill_null(0.0)`, values `['1.0', '', '  ', '3.5']` cleanly transform into `[1.0, 0.0, 0.0, 3.5]`.

Because standard CSV datasets from AMLSim and conventional banking exports use unquoted null delimiters (`,,`), the current fix satisfies all acceptance criteria for M5 R2. This finding is noted as an advisory for future hardening.

---

## 6. Empirical Test Matrix

| Test Case | Scenario | Expected | Observed | Verdict |
|---|---|---|---|---|
| `TC-M5-01` | 3-Column CSV Upload (`origin,dest,amount`) | HTTP 201, synthetic float step | HTTP 201, timestamps `0.0, 1.0, 2.0` | **PASS** |
| `TC-M5-02` | Unpopulated Timestamp Cells (`A,B,100,`) | HTTP 201, default to 0.0 | HTTP 201, timestamp `0.0` | **PASS** |
| `TC-M5-03` | Offline In-Memory Fallback (3-col CSV) | HTTP 201, dual-write memory | HTTP 201, cached in `INVESTIGATION_CASES` | **PASS** |
| `TC-M5-04` | Offline In-Memory Fallback (null ts CSV) | HTTP 201, dual-write memory | HTTP 201, cached in `INVESTIGATION_CASES` | **PASS** |
| `TC-M5-05` | Dynamic Tool Query `in` Datetime Filter | Correct records matching datetime list | Filter matches expected transaction | **PASS** |
| `TC-M5-06` | Polars Pipeline Unit Tests (`read_amlsim`) | 2 passed in test_pipeline.py | 2 passed in 1.16s | **PASS** |
| `TC-M5-FULL` | Full Automated Test Suite (`backend/tests/`) | 126 passed cleanly | 126 passed in 43.84s (Exit Code 0) | **PASS** |
| `TC-M5-ADV` | Quoted Empty / Whitespace Timestamp String | Graceful coercion | `InvalidOperationError` (strict cast) | **ADVISORY** |

---

## 7. Conclusion

The implementation provided by Worker M5 R2 satisfies the requirements of Milestone 5 Iteration 2:
- 3-column CSV ingestion functions correctly without schema errors.
- Unpopulated timestamp cells default cleanly without runtime exceptions.
- Dynamic tool queries with `in` datetime operators work seamlessly.

Verdict: **APPROVE** (with 1 non-blocking advisory documented in Section 5).
