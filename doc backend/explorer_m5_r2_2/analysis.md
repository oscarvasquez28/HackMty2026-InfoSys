# Analysis: Dynamic Query DateTime Coercion for List Operators (`in` / `not_in`)

**Date**: 2026-09-12  
**Author**: Explorer 2 (Milestone 5 Iteration 2)  
**Target Module**: `backend/services/tool_registry.py`  
**Referenced Defect**: Challenger 2 Report (`.agents/challenger_m5_2/handoff.md`, Finding 3)

---

## 1. Executive Summary

Challenger 2 identified a latent defect in `backend/services/tool_registry.py`:
When dynamic queries use the `in` or `not_in` operators against DateTime columns (e.g. `timestamp` in `TransactionRecord`, or `created_at`/`updated_at` in `InvestigationCase`), list/tuple elements remain raw ISO string representations rather than `datetime` objects.

Because SQLAlchemy does not implicitly cast array string literals when compiling `column.in_(val_list)` against a `DateTime(timezone=True)` column, the underlying database driver (whether SQLite in test or PostgreSQL/asyncpg/psycopg in production) performs string-to-timestamp comparison that fails to match records. As a consequence:
- `timestamp in ["2026-01-01T02:00:00"]` matches **0 records** (false negatives).
- `timestamp not_in ["2026-01-01T02:00:00"]` matches **all records** including the target (false positives).

Empirical reproduction verified that scalar comparisons (`eq`, `gt`, `lt`) worked because `isinstance(val, str)` was checked, but collection comparisons bypassed coercion completely because `isinstance(val, str)` evaluates to `False` for `list`/`tuple`/`set`.

---

## 2. Empirical Root Cause Analysis

### 2.1 Code Inspection

In `backend/services/tool_registry.py`:

#### Location A: Lines 394–406 (`handle_transactions_query`)
```python
        for f in request.filters:
            if f.field == "case_id":
                continue
            col = getattr(TransactionRecord, f.field)
            val = f.value
            # Type coercions
            if f.field == "timestamp" and isinstance(val, str):
                val_dt = parse_datetime_safe(val)
                if val_dt:
                    val = val_dt
            elif f.field == "amount" and isinstance(val, (int, float, str)):
                val = Decimal(str(val))
            elif f.field == "is_suspicious" and isinstance(val, str):
                val = val.lower() in ("true", "1")
            where_clauses.append(apply_sa_operator(col, f.operator, val))
```
- When `f.operator in (FilterOperator.IN, FilterOperator.NOT_IN)`, `f.value` is validated by Pydantic schema `QueryFilter` as `list`/`tuple`/`set`.
- For `f.field == "timestamp"`: `isinstance(val, str)` is `False`.
- The coercion block `val = val_dt` is completely skipped.
- `apply_sa_operator(col, f.operator, val)` receives `val` as `["2026-01-01T02:00:00"]`.
- `apply_sa_operator` executes `TransactionRecord.timestamp.in_(val_list)` where `val_list` contains strings.

#### Location B: Lines 506–514 (`handle_cases_query`)
```python
        for f in request.filters:
            col = getattr(InvestigationCase, f.field)
            val = f.value
            if f.field in ("created_at", "updated_at") and isinstance(val, str):
                val_dt = parse_datetime_safe(val)
                if val_dt:
                    val = val_dt
            where_clauses.append(apply_sa_operator(col, f.operator, val))
```
- Identical issue exists for `created_at` and `updated_at` in `InvestigationCase`.

#### Location C: Lines 184–197 (`evaluate_in_memory_predicate`)
```python
    elif op == "in":
        if not isinstance(target_val, (list, tuple, set)):
            return False
        # If val is a list, check intersection
        if isinstance(val, list):
            return any(x in target_val or str(x) in [str(t) for t in target_val] for x in val)
        return val in target_val or str(val) in [str(t) for t in target_val]
```
- In offline/in-memory mode, string comparison fails if representations differ (e.g. `2026-01-01T02:00:00Z` vs `2026-01-01T02:00:00+00:00`).

#### Location D: Lines 57–62 (`parse_datetime_safe`)
```python
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
```
- When a string does not contain an explicit timezone offset (e.g. `2026-01-01T02:00:00`), `fromisoformat()` produces a timezone-naive `datetime`.
- Comparing timezone-naive datetimes with timezone-aware datetimes (`datetime.now(timezone.utc)`) raises `TypeError: can't compare offset-naive and offset-aware datetimes` in Python 3.

---

### 2.2 Empirical Reproduction Results

A direct test against `POST /api/v1/tools/query` with an uploaded transaction dataset:

```python
# Query 1: Scalar equality on timestamp
{'target': 'transactions', 'case_id': case_id, 'filters': [{'field': 'timestamp', 'operator': 'eq', 'value': ts0}]}
# Output: EQ query count: 1

# Query 2: 'in' operator on timestamp with list containing [ts0]
{'target': 'transactions', 'case_id': case_id, 'filters': [{'field': 'timestamp', 'operator': 'in', 'value': [ts0]}]}
# Output: IN query count: 0  <-- BUG!

# Query 3: 'not_in' operator on timestamp with list containing [ts0]
{'target': 'transactions', 'case_id': case_id, 'filters': [{'field': 'timestamp', 'operator': 'not_in', 'value': [ts0]}]}
# Output: NOT_IN query count: 2  <-- BUG! Matches all records including ts0
```

---

## 3. Formulated Solution

The solution consists of four coordinated enhancements in `backend/services/tool_registry.py`:

### 3.1 UTC Normalization in `parse_datetime_safe`
Ensure all parsed string datetimes default to `timezone.utc` if timezone is omitted:
```python
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
```

### 3.2 List/Tuple/Set Coercion in `handle_transactions_query`
Coerce both scalar and collection values for `timestamp`, `amount`, and `is_suspicious`:
```python
            # Type coercions
            if f.field == "timestamp":
                if isinstance(val, (list, tuple, set)):
                    val = [parse_datetime_safe(x) or x for x in val]
                elif isinstance(val, (str, int, float)):
                    val_dt = parse_datetime_safe(val)
                    if val_dt:
                        val = val_dt
            elif f.field == "amount":
                if isinstance(val, (list, tuple, set)):
                    val = [Decimal(str(x)) for x in val]
                elif isinstance(val, (int, float, str)):
                    val = Decimal(str(val))
            elif f.field == "is_suspicious":
                if isinstance(val, (list, tuple, set)):
                    val = [x.lower() in ("true", "1") if isinstance(x, str) else bool(x) for x in val]
                elif isinstance(val, str):
                    val = val.lower() in ("true", "1")
```

### 3.3 List/Tuple/Set Coercion in `handle_cases_query`
Apply the same datetime coercion to `created_at` and `updated_at`:
```python
            if f.field in ("created_at", "updated_at"):
                if isinstance(val, (list, tuple, set)):
                    val = [parse_datetime_safe(x) or x for x in val]
                elif isinstance(val, (str, int, float)):
                    val_dt = parse_datetime_safe(val)
                    if val_dt:
                        val = val_dt
```

### 3.4 In-Memory Predicate DateTime Awareness in `evaluate_in_memory_predicate`
Add datetime normalization and comparison to in-memory fallback for DateTime fields (`timestamp`, `created_at`, `updated_at`):
```python
    if field_name in ("timestamp", "created_at", "updated_at"):
        dt_val = parse_datetime_safe(val)
        if dt_val is not None:
            if op == "eq":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val == dt_tgt if dt_tgt is not None else False
            elif op == "neq":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val != dt_tgt if dt_tgt is not None else True
            elif op == "gt":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val > dt_tgt if dt_tgt is not None else False
            elif op == "gte":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val >= dt_tgt if dt_tgt is not None else False
            elif op == "lt":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val < dt_tgt if dt_tgt is not None else False
            elif op == "lte":
                dt_tgt = parse_datetime_safe(target_val)
                return dt_val <= dt_tgt if dt_tgt is not None else False
            elif op == "in":
                if not isinstance(target_val, (list, tuple, set)):
                    return False
                target_dts = [parse_datetime_safe(t) for t in target_val]
                return any(dt_val == t_dt for t_dt in target_dts if t_dt is not None)
            elif op == "not_in":
                if not isinstance(target_val, (list, tuple, set)):
                    return True
                target_dts = [parse_datetime_safe(t) for t in target_val]
                return not any(dt_val == t_dt for t_dt in target_dts if t_dt is not None)
```

### 3.5 Defense-in-Depth in `apply_sa_operator`
Inspect column type metadata in `apply_sa_operator` so any future registered models with `DateTime` columns automatically receive proper datetime binding:
```python
    if hasattr(column, "type") and isinstance(column.type, DateTime):
        if op in ("in", "not_in") and isinstance(value, (list, tuple, set)):
            value = [parse_datetime_safe(x) or x for x in value]
        elif isinstance(value, (str, int, float)):
            dt_parsed = parse_datetime_safe(value)
            if dt_parsed is not None:
                value = dt_parsed
```

---

## 4. Verification

1. **Before fix**:
   - `IN query count: 0`
   - `NOT_IN query count: 2`

2. **With fix dynamically applied**:
   - `IN query count: 1`
   - `NOT_IN query count: 1`
   - All 15 tests in `backend/tests/test_agent_tools.py` pass cleanly.
   - All 8 tests in `backend/tests/test_challenger_m3_2.py` pass cleanly.

See `handoff.md` for the complete diff patch and verification plan.
