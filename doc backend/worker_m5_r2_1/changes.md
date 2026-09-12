# Changes Log — Worker M5 R2 (Milestone 5 Iteration 2)

**Agent Working Directory**: `.agents/worker_m5_r2_1`  
**Date**: 2026-09-12  
**Role**: Implementer / QA  

## Summary of Code Modifications

### 1. `backend/services/ingestion.py`
- **Location**: `read_amlsim_csv()` (lines 71–79)
- **Defect Addressed**: Polars 1.x `SchemaError: non-integer 'dtype' passed to 'int_range': 'f64'` on 3-column CSV uploads without a timestamp column; and missing null coalescing on existing timestamp columns leading to `TypeError`.
- **Modifications**:
  - For CSVs with an identified timestamp column: chained `.fill_null(0.0)` prior to `.cast(pl.Float64)`.
  - For CSVs without an identified timestamp column: replaced `pl.int_range(0, df.height, dtype=pl.Float64)` with `pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp")`.

### 2. `backend/services/deterministic_filter.py`
- **Location**: `build_transaction_graph()` (lines 18–25)
- **Defect Addressed**: Unhandled `NoneType` in `float(row["timestamp"])` causing `TypeError` and HTTP 500 when processing datasets with empty/null timestamp cells.
- **Modifications**:
  - Implemented safe extraction and conversion:
    ```python
    raw_ts = row.get("timestamp")
    try:
        timestamp = float(raw_ts) if raw_ts is not None else 0.0
    except (ValueError, TypeError):
        timestamp = 0.0
    ```

### 3. `backend/services/tool_registry.py`
- **Location**:
  - Added `DateTime` import from `sqlalchemy`.
  - `parse_datetime_safe()`: normalized naive datetime objects to UTC using `dt.replace(tzinfo=timezone.utc)`.
  - `apply_sa_operator()`: added defense-in-depth column-level coercion for `DateTime` columns when operator is `in` or `not_in`, converting strings in collections to datetime objects.
  - `evaluate_in_memory_predicate()`: added datetime-aware comparisons for `timestamp`, `created_at`, and `updated_at` fields across all operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`).
  - `handle_transactions_query()`: added collection coercion `[parse_datetime_safe(x) or x for x in val]` for `timestamp` when `val` is a `list`, `tuple`, or `set`, as well as list coercions for `amount` and `is_suspicious`.
  - `handle_cases_query()`: added collection coercion `[parse_datetime_safe(x) or x for x in val]` for `created_at` and `updated_at` when `val` is a `list`, `tuple`, or `set`.

### 4. `backend/tests/test_investigations.py`
- **Added Tests**:
  - `test_csv_upload_without_timestamp_column`: Uploads a 3-column CSV (`origin,destination,amount`) and asserts HTTP 201, `status == "PROCESSING"`, topological graph metrics computation, and database persistence of 7 TransactionRecords with sequential non-null datetime timestamps.
  - `test_csv_upload_with_null_timestamp_cells`: Uploads a CSV with empty timestamp cells and asserts HTTP 201, `status == "PROCESSING"`, and database persistence of all 6 TransactionRecords with non-null datetimes (defaulted to 0.0).

### 5. `backend/tests/test_agent_tools.py`
- **Added Tests**:
  - `test_query_datetime_in_operator`: Submits `POST /api/v1/tools/query` with `in` and `not_in` operators containing ISO datetime strings `[ts_a, ts_b]`, asserting HTTP 200, `total >= 2`, record counts, and strict timestamp matching.

### 6. `backend/tests/test_pipeline.py`
- **Added Tests**:
  - `test_read_amlsim_csv_synthetic_fallback`: Unit test validating Polars DataFrame normalization and synthetic step generation `[0.0, 1.0]` when timestamp column is absent.
  - `test_read_amlsim_csv_null_timestamp_cells`: Unit test validating `fill_null(0.0)` for partial/empty timestamp cells resulting in `[0.0, 5.0]`.

---

## Test Verification Summary
- Pre-fix baseline: 121 tests passed.
- Targeted tests: 5 regression tests passed.
- Full test suite: 126 tests passed in 42.56s (`pytest backend/tests/ -v`).
- 0 failures, 0 regressions.

