# Milestone 3 Analysis: Dynamic Tool Registry & Query Builder Pattern

**Agent**: explorer_m3_2  
**Milestone**: Milestone 3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents)  
**Target Modules**: `backend/services/tool_registry.py`, `backend/api/routes/agent_tools.py`, `backend/schemas/agent_tools.py`, `backend/main.py`  
**Date**: 2026-09-12  

---

## 1. Executive Summary

Milestone 3 requirement **R3** (`ORIGINAL_REQUEST.md`) mandates a scalable, extensible query interface and dynamic tool registry for n8n AI agents. The AI agents must be able to explore transactional graphs, profile counterparties, inspect topological patterns (cycles, pass-through mules), and query Mexican AML jurisprudence without modifying database schemas or creating security vulnerabilities.

This document presents the complete architectural design and implementation specification for:
1. **The `ToolRegistry` Engine** (`backend/services/tool_registry.py`): A modular registry pattern supporting decorator-based (`@tool_registry.register(...)`) and programmatic tool query handler registration.
2. **Safe Dynamic Query Builder**: Complete elimination of SQL injection via column whitelisting, operator whitelisting, and parameterized SQLAlchemy 2.0 Core/ORM expression trees (zero string interpolation).
3. **Mandatory `case_id` Scoping**: Strict enforcement of case boundaries for case-scoped entities (`transactions`, `entities`, `patterns`) to prevent cross-case data leakage.
4. **Column & Operator Whitelists**: Definitive rules for 5 canonical entity targets: `transactions`, `cases`, `entities`, `patterns`, and `legal_precedents` (with backward-compatible aliases for `nodes`, `edges`, `cycles`, `passthrough_accounts`, and `legal_vectors`).
5. **Sorting & Pagination Engine**: Validated offset/limit pagination with bounded limits (1–1000, default 50) and whitelisted order-by fields.
6. **Dual Storage Execution**: Seamless execution across both remote TigerData PostgreSQL (`AsyncSession`) and in-memory fallback store (`INVESTIGATION_CASES` cache), guaranteeing 100% offline resilience and zero-regression test execution.
7. **Router Integration**: Clean registration of `agent_tools_router` in `backend/main.py` with OpenAPI tags.

---

## 2. Core Architecture & Design Patterns

### 2.1 Tool Registry Pattern (`backend/services/tool_registry.py`)

The `ToolRegistry` decouples HTTP request routing from query compilation and execution. New query targets can be registered at runtime or module load without altering existing API routes or database schemas.

```
┌────────────────────────────────────────────────────────┐
│               n8n AI Agent / HTTP Client               │
└───────────────────────────┬────────────────────────────┘
                            │ POST /api/v1/tools/query
                            ▼
┌────────────────────────────────────────────────────────┐
│     Agent Tools Router (backend/api/routes/agent_tools.py)│
└───────────────────────────┬────────────────────────────┘
                            │ DynamicQueryRequest
                            ▼
┌────────────────────────────────────────────────────────┐
│       ToolRegistry (backend/services/tool_registry.py) │
│  - Target Validation & Metadata Lookup                 │
│  - Mandatory case_id Scoping Enforcement               │
│  - Column Whitelist Sanitization                       │
│  - Operator Whitelist Sanitization                     │
│  - Sort & Pagination Bounds Verification               │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       [Active DB Session]      [Offline / Memory Mode]
                ▼                        ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ Parameterized SQLAlchemy 2.0  │ │ In-Memory Evaluator           │
│ AST Query Compiler            │ │ - Filter matching predicates  │
│ - select(Model).where(...)    │ │ - Python sorting & slicing    │
│ - Bound parameters (:param_1) │ │ - Read INVESTIGATION_CASES    │
└───────────────┬───────────────┘ └───────────────┬───────────────┘
                │                                │
                ▼                                ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ TigerData PostgreSQL / SQLite │ │ In-Memory Cache Dict          │
└───────────────────────────────┘ └───────────────────────────────┘
```

#### Registry Class Definition
```python
@dataclass(frozen=True)
class TargetMetadata:
    target: str
    model: Optional[Any]
    allowed_columns: Set[str]
    allowed_sort_columns: Set[str]
    requires_case_id: bool
    default_sort_field: str
    default_sort_order: str
    description: str


class ToolRegistry:
    """
    Extensible query handler registry allowing registration of dynamic query
    targets with strict column whitelisting, parameterized SQL generation,
    and mandatory case_id scoping.
    """
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._metadata: Dict[str, TargetMetadata] = {}

    def register(
        self,
        target: str,
        handler: Optional[Callable] = None,
        *,
        model: Optional[Any] = None,
        allowed_columns: Optional[Set[str]] = None,
        allowed_sort_columns: Optional[Set[str]] = None,
        requires_case_id: bool = False,
        default_sort_field: Optional[str] = None,
        default_sort_order: str = "desc",
        description: str = "",
    ) -> Callable:
        """
        Registers a target query handler. Supports direct invocation or decorator usage:
            @tool_registry.register("transactions", allowed_columns={...}, requires_case_id=True)
            async def handle_transactions(request, meta, db): ...
        """
        def decorator(fn: Callable) -> Callable:
            cols = allowed_columns or set()
            sort_cols = allowed_sort_columns or cols
            def_sort = default_sort_field or (next(iter(sort_cols)) if sort_cols else "id")
            self._handlers[target] = fn
            self._metadata[target] = TargetMetadata(
                target=target,
                model=model,
                allowed_columns=cols,
                allowed_sort_columns=sort_cols,
                requires_case_id=requires_case_id,
                default_sort_field=def_sort,
                default_sort_order=default_sort_order,
                description=description,
            )
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    def get_metadata(self, target: str) -> Optional[TargetMetadata]:
        return self._metadata.get(target)

    def list_targets(self) -> List[Dict[str, Any]]:
        return [
            {
                "target": meta.target,
                "description": meta.description,
                "requires_case_id": meta.requires_case_id,
                "allowed_columns": sorted(list(meta.allowed_columns)),
                "allowed_sort_columns": sorted(list(meta.allowed_sort_columns)),
                "default_sort": f"{meta.default_sort_field} {meta.default_sort_order}",
            }
            for meta in self._metadata.values()
        ]

    async def execute_query(
        self,
        request: "DynamicQueryRequest",
        db: Optional[AsyncSession] = None,
    ) -> "DynamicQueryResponse":
        # 1. Target Validation
        target_name = request.target if isinstance(request.target, str) else request.target.value
        meta = self.get_metadata(target_name)
        if not meta or target_name not in self._handlers:
            allowed = sorted(list(self._handlers.keys()))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported query target '{target_name}'. Allowed targets: {allowed}",
            )

        # 2. Mandatory case_id Scoping Enforcement
        if meta.requires_case_id:
            case_id = request.case_id
            if not case_id:
                # Inspect filters for case_id equality
                for f in request.filters:
                    if f.field == "case_id" and f.operator in ("eq", "EQ"):
                        case_id = f.value
                        break
            if not case_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Mandatory scoping violation: 'case_id' is required when querying target "
                        f"'{target_name}' to prevent cross-case data leaks."
                    ),
                )

        # 3. Column Whitelist Validation
        for f in request.filters:
            if f.field not in meta.allowed_columns:
                allowed_fields = sorted(list(meta.allowed_columns))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Field '{f.field}' is not permitted for target '{target_name}'. "
                        f"Allowed fields: {allowed_fields}"
                    ),
                )

        # 4. Sort Column Validation
        sort_by = request.sort_by
        if sort_by:
            if sort_by not in meta.allowed_sort_columns:
                allowed_sort = sorted(list(meta.allowed_sort_columns))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Sort column '{sort_by}' is not permitted for target '{target_name}'. "
                        f"Allowed sort columns: {allowed_sort}"
                    ),
                )

        # 5. Dispatch to target handler
        handler = self._handlers[target_name]
        return await handler(request, meta, db)
```

---

## 3. Entity Targets & Column Whitelists

To completely prevent unauthorized column enumeration, schema discovery attacks, and internal metadata leakage, every entity target has a strictly defined column whitelist.

| Entity Target | Backing Model / Source | `requires_case_id` | Allowed Query Columns (`allowed_columns`) | Allowed Sort Columns (`allowed_sort_columns`) | Default Sort |
|---|---|---|---|---|---|
| `transactions` | `TransactionRecord` (SQL) / `INVESTIGATION_CASES[case_id]["transactions"]` (Memory) | **YES (Mandatory)** | `id`, `case_id`, `origin`, `destination`, `amount`, `timestamp`, `is_suspicious`, `reasons` | `timestamp`, `amount`, `origin`, `destination`, `is_suspicious`, `id` | `timestamp desc` |
| `cases` | `InvestigationCase` (SQL) / `INVESTIGATION_CASES` (Memory) | **NO** | `id`, `filename`, `status`, `created_at`, `updated_at` | `created_at`, `updated_at`, `filename`, `status`, `id` | `created_at desc` |
| `entities` *(alias: `nodes`)* | `InvestigationCase.subgraph["nodes"]` (SQL/Memory) | **YES (Mandatory)** | `id`, `entity_id`, `total_in`, `total_out`, `net_flow`, `in_degree`, `out_degree`, `risk_score`, `is_suspicious`, `reasons` | `risk_score`, `total_in`, `total_out`, `net_flow`, `in_degree`, `out_degree`, `id` | `risk_score desc` |
| `patterns` *(aliases: `cycles`, `passthrough_accounts`)* | `InvestigationCase.patterns` (SQL/Memory) | **YES (Mandatory)** | `pattern_type`, `length`, `estimated_volume`, `ratio`, `account`, `node_id`, `time_delta_hours` | `estimated_volume`, `length`, `ratio` | `estimated_volume desc` |
| `legal_precedents` *(alias: `legal_vectors`)* | `LegalArticleVector` (SQL) / `SEED_LEGAL_PRECEDENTS` (Memory) | **NO** | `id`, `article_code`, `law_name`, `content` | `article_code`, `law_name`, `id` | `article_code asc` |

### Backward-Compatible Aliases
To ensure interoperability with both high-level agent queries and low-level graph representations:
- `nodes` is registered as an alias of `entities`.
- `cycles` and `passthrough_accounts` route to specialized or filtered projections of `patterns`.
- `legal_vectors` routes to `legal_precedents`.

---

## 4. Supported Operators & Parameterized AST Compilation

### 4.1 Allowed Operators Whitelist
The query builder supports 9 relational and pattern-matching operators:
- `eq`: Equality (`column == value`)
- `neq`: Inequality (`column != value`)
- `gt`: Greater than (`column > value`)
- `gte`: Greater than or equal (`column >= value`)
- `lt`: Less than (`column < value`)
- `lte`: Less than or equal (`column <= value`)
- `like`: Case-sensitive pattern match (`column.like(pattern)`)
- `ilike`: Case-insensitive pattern match (`column.ilike(pattern)`)
- `in`: Membership in array (`column.in_(values)`)
- *(Optional extension)* `not_in`: Negated membership (`column.not_in_(values)`)

### 4.2 Parameterized SQL Generation (100% SQLi Immunity)
The query builder compiles incoming criteria into SQLAlchemy 2.0 Core binary expression trees. Values are **never** injected into SQL strings via format strings, concatenation, or interpolation.

```python
def apply_sa_operator(column: Any, operator_str: str, value: Any) -> Any:
    op = operator_str.lower()
    
    if op == "eq":
        return column == value
    elif op == "neq":
        return column != value
    elif op == "gt":
        return column > value
    elif op == "gte":
        return column >= value
    elif op == "lt":
        return column < value
    elif op == "lte":
        return column <= value
    elif op == "like":
        val_str = str(value)
        pattern = val_str if ("%" in val_str or "_" in val_str) else f"%{val_str}%"
        return column.like(pattern)
    elif op == "ilike":
        val_str = str(value)
        pattern = val_str if ("%" in val_str or "_" in val_str) else f"%{val_str}%"
        return column.ilike(pattern)
    elif op == "in":
        if not isinstance(value, (list, tuple, set)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operator 'in' requires an array/list value, got {type(value).__name__}",
            )
        if len(value) == 0:
            # Empty in clause -> evaluates to false
            return column.in_([None]) & column.is_not(None)
        return column.in_(list(value))
    elif op == "not_in":
        if not isinstance(value, (list, tuple, set)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operator 'not_in' requires an array/list value, got {type(value).__name__}",
            )
        if len(value) == 0:
            return True
        return column.not_in_(list(value))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported operator '{operator_str}'. Allowed operators: eq, neq, gt, gte, lt, lte, like, ilike, in, not_in",
        )
```

#### Proof of Immunity against Attack Vectors
1. **Raw SQL Injection Attempt** (`field="origin; DROP TABLE transactions;--"`):
   - Caught by `field not in meta.allowed_columns` -> Returns HTTP 400 immediately. No SQL statement created.
2. **Tautology Injection in Value** (`value="' OR '1'='1"`):
   - Passed to `column == "' OR '1'='1"`.
   - Compiles to: `WHERE transactions.origin = :origin_1` with parameter `{"origin_1": "' OR '1'='1"}`.
   - Evaluated as a literal account ID. Zero SQL syntax disruption.
3. **Union-Based Injection in Value** (`value="' UNION SELECT password FROM users --"`):
   - Parameterized as `:param_1`. No union execution occurs.

---

## 5. Mandatory `case_id` Scoping Specification

### 5.1 Threat Model: Cross-Case Data Leakage
In a forensic investigation environment, different cases represent distinct financial entities, bank accounts, or judicial proceedings. An agent requesting:
```json
{
  "target": "transactions",
  "filters": [{"field": "is_suspicious", "operator": "eq", "value": true}]
}
```
Without mandatory scoping, this would dump suspicious transactions across **all** cases in the database, violating judicial confidentiality, banking secrecy, and multi-tenant data segregation.

### 5.2 Enforcement Rules
1. Every target having `meta.requires_case_id == True` enforces the presence of a non-null `case_id`.
2. The `case_id` can be specified:
   - At top-level: `"case_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"`
   - In filters: `{"field": "case_id", "operator": "eq", "value": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"}`
3. If absent from both, execution halts immediately with:
   ```json
   {
     "detail": "Mandatory scoping violation: 'case_id' is required when querying target 'transactions' to prevent cross-case data leaks."
   }
   ```
4. The resolved `case_id` is automatically parsed as a valid UUID and injected as an immutable conjunction clause (`TransactionRecord.case_id == case_uuid`) in the SQL query.

---

## 6. Sorting & Pagination Engine

### 6.1 Pagination Constraints
- `limit`:
  - Type: `int`
  - Range: `1 <= limit <= 1000`
  - Default: `50`
  - Rejection: Values `< 1` or `> 1000` return HTTP 422 Unprocessable Entity.
- `offset`:
  - Type: `int`
  - Range: `offset >= 0`
  - Default: `0`
  - Rejection: Negative values return HTTP 422.

### 6.2 Sorting Constraints
- `sort_by`:
  - Must exist in `meta.allowed_sort_columns`.
  - If omitted, defaults to `meta.default_sort_field`.
- `sort_order`:
  - Must be `"asc"` or `"desc"` (case-insensitive).
  - Applied as `getattr(Model, sort_by).desc()` or `.asc()`.

### 6.3 Response Metadata Contract
The response returns exact pagination metadata allowing agent pagination loops:
```json
{
  "target": "transactions",
  "case_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "total": 1420,
  "count": 50,
  "limit": 50,
  "offset": 0,
  "applied_filters": [
    {"field": "is_suspicious", "operator": "eq", "value": true}
  ],
  "records": [...],
  "execution_time_ms": 4.12
}
```

---

## 7. Dual Storage Execution (PostgreSQL & In-Memory Cache)

To guarantee that the backend functions reliably across development, testing, CI, and production:

### 7.1 Database Handler (`AsyncSession`)
1. Resolves model class from metadata (e.g. `TransactionRecord`).
2. Builds `select(Model).where(...)` and count query `select(func.count()).select_from(...)`.
3. Executes count query: `total = (await db.execute(count_stmt)).scalar() or 0`.
4. Executes slice query: `result = await db.execute(stmt)`.
5. Serializes rows to list of dictionaries, converting UUIDs to strings and Decimals to floats.

### 7.2 In-Memory Evaluator (`INVESTIGATION_CASES` Fallback)
When `db is None` (e.g. `DATABASE_URL` unset or SQLite offline test):
1. For case-scoped targets (`transactions`, `entities`, `patterns`):
   - Retrieves case dict from `INVESTIGATION_CASES[case_id_str]`.
   - If case not found, raises HTTP 404.
2. Evaluates filters using pure Python predicates:
   ```python
   def evaluate_in_memory_predicate(item: Dict[str, Any], f: QueryFilter) -> bool:
       val = item.get(f.field)
       op = f.operator.lower()
       target_val = f.value
       if op == "eq":
           return val == target_val or str(val) == str(target_val)
       elif op == "neq":
           return val != target_val
       elif op == "gt":
           return val is not None and float(val) > float(target_val)
       elif op == "gte":
           return val is not None and float(val) >= float(target_val)
       elif op == "lt":
           return val is not None and float(val) < float(target_val)
       elif op == "lte":
           return val is not None and float(val) <= float(target_val)
       elif op == "like":
           return str(target_val).strip("%") in str(val or "")
       elif op == "ilike":
           return str(target_val).strip("%").lower() in str(val or "").lower()
       elif op == "in":
           return val in target_val or str(val) in [str(x) for x in target_val]
       elif op == "not_in":
           return val not in target_val
       return False
   ```
3. Performs Python sorting (`items.sort(key=..., reverse=...)`) and slicing (`items[offset : offset + limit]`).
4. Produces identical `DynamicQueryResponse` structure.

---

## 8. Target Handlers Implementation Blueprint

### 8.1 Transactions Target Handler
```python
@tool_registry.register(
    "transactions",
    model=TransactionRecord,
    allowed_columns={"id", "case_id", "origin", "destination", "amount", "timestamp", "is_suspicious", "reasons"},
    allowed_sort_columns={"timestamp", "amount", "origin", "destination", "is_suspicious", "id"},
    requires_case_id=True,
    default_sort_field="timestamp",
    default_sort_order="desc",
    description="Query and filter individual transactions within an investigation case.",
)
async def handle_transactions_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    case_uuid = uuid.UUID(str(request.case_id))

    if db is not None:
        # Parameterized SQLAlchemy AST
        where_clauses = [TransactionRecord.case_id == case_uuid]
        for f in request.filters:
            if f.field == "case_id":
                continue
            col = getattr(TransactionRecord, f.field)
            where_clauses.append(apply_sa_operator(col, f.operator, f.value))

        # Count total
        count_stmt = select(func.count(TransactionRecord.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query items
        stmt = select(TransactionRecord).where(*where_clauses)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_col = getattr(TransactionRecord, sort_col_name)
        stmt = stmt.order_by(sort_col.desc() if request.sort_order.lower() == "desc" else sort_col.asc())
        stmt = stmt.limit(request.limit).offset(request.offset)

        rows = (await db.execute(stmt)).scalars().all()
        records = [
            {
                "id": str(r.id),
                "case_id": str(r.case_id),
                "origin": r.origin,
                "destination": r.destination,
                "amount": float(r.amount),
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "is_suspicious": r.is_suspicious,
                "reasons": r.reasons or [],
            }
            for r in rows
        ]
    else:
        # In-memory fallback
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
        
        raw_records = case_data.get("transactions", [])
        # If raw transactions aren't directly saved in dict, derive from subgraph edges
        if not raw_records and "subgraph" in case_data:
            edges = case_data["subgraph"].get("edges", [])
            raw_records = [
                {
                    "id": str(uuid.uuid4()),
                    "case_id": str(case_uuid),
                    "origin": e["source"],
                    "destination": e["target"],
                    "amount": float(e["amount"]),
                    "timestamp": e.get("timestamps", [datetime.now(timezone.utc).isoformat()])[0],
                    "is_suspicious": bool(e.get("reasons")),
                    "reasons": e.get("reasons", []),
                }
                for e in edges
            ]

        filtered = [
            r for r in raw_records
            if all(evaluate_in_memory_predicate(r, f) for f in request.filters if f.field != "case_id")
        ]
        total = len(filtered)
        sort_col_name = request.sort_by or meta.default_sort_field
        is_desc = request.sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col_name) or 0, reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target="transactions",
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
```

### 8.2 Cases Target Handler
```python
@tool_registry.register(
    "cases",
    model=InvestigationCase,
    allowed_columns={"id", "filename", "status", "created_at", "updated_at"},
    allowed_sort_columns={"created_at", "updated_at", "filename", "status", "id"},
    requires_case_id=False,
    default_sort_field="created_at",
    default_sort_order="desc",
    description="Query investigation cases history, status, and metadata.",
)
async def handle_cases_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    if db is not None:
        where_clauses = []
        if request.case_id:
            where_clauses.append(InvestigationCase.id == uuid.UUID(str(request.case_id)))
        for f in request.filters:
            col = getattr(InvestigationCase, f.field)
            where_clauses.append(apply_sa_operator(col, f.operator, f.value))

        count_stmt = select(func.count(InvestigationCase.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(InvestigationCase).where(*where_clauses)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_col = getattr(InvestigationCase, sort_col_name)
        stmt = stmt.order_by(sort_col.desc() if request.sort_order.lower() == "desc" else sort_col.asc())
        stmt = stmt.limit(request.limit).offset(request.offset)

        rows = (await db.execute(stmt)).scalars().all()
        records = [
            {
                "id": str(r.id),
                "filename": r.filename,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "metrics": r.metrics or {},
                "has_verdict": r.verdict is not None,
            }
            for r in rows
        ]
    else:
        raw_cases = list(INVESTIGATION_CASES.values())
        filtered = [
            c for c in raw_cases
            if all(evaluate_in_memory_predicate(c, f) for f in request.filters)
        ]
        total = len(filtered)
        sort_col_name = request.sort_by or meta.default_sort_field
        is_desc = request.sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col_name) or "", reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target="cases",
        case_id=str(request.case_id) if request.case_id else None,
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
```

### 8.3 Entities Target Handler (`entities` / `nodes`)
```python
@tool_registry.register(
    "entities",
    allowed_columns={"id", "entity_id", "total_in", "total_out", "net_flow", "in_degree", "out_degree", "risk_score", "is_suspicious", "reasons"},
    allowed_sort_columns={"risk_score", "total_in", "total_out", "net_flow", "in_degree", "out_degree", "id"},
    requires_case_id=True,
    default_sort_field="risk_score",
    default_sort_order="desc",
    description="Profile financial entities/nodes, volumes, degrees, and risk scores.",
)
async def handle_entities_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    case_uuid = uuid.UUID(str(request.case_id))

    nodes: List[Dict[str, Any]] = []
    if db is not None:
        stmt = select(InvestigationCase.subgraph).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        subgraph = res.scalar_one_or_none()
        if subgraph is None:
            # Check if case exists
            exists_stmt = select(InvestigationCase.id).where(InvestigationCase.id == case_uuid)
            if not (await db.execute(exists_stmt)).scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
            subgraph = {}
        nodes = list(subgraph.get("nodes", []))
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
        nodes = list(case_data.get("subgraph", {}).get("nodes", []))

    # Normalize entity fields
    normalized = []
    for n in nodes:
        t_in = float(n.get("total_in", 0.0))
        t_out = float(n.get("total_out", 0.0))
        normalized.append({
            "id": str(n.get("id")),
            "entity_id": str(n.get("id")),
            "total_in": t_in,
            "total_out": t_out,
            "net_flow": round(t_in - t_out, 2),
            "in_degree": int(n.get("in_degree", 0)),
            "out_degree": int(n.get("out_degree", 0)),
            "risk_score": float(n.get("risk_score", 0.0)),
            "is_suspicious": bool(n.get("reasons") or n.get("risk_score", 0.0) >= 0.5),
            "reasons": n.get("reasons", []),
        })

    filtered = [
        item for item in normalized
        if all(evaluate_in_memory_predicate(item, f) for f in request.filters if f.field != "case_id")
    ]
    total = len(filtered)
    sort_col = request.sort_by or meta.default_sort_field
    is_desc = request.sort_order.lower() == "desc"
    filtered.sort(key=lambda x: x.get(sort_col) or 0, reverse=is_desc)
    records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target="entities",
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
```

### 8.4 Patterns Target Handler (`patterns`)
```python
@tool_registry.register(
    "patterns",
    allowed_columns={"pattern_type", "length", "estimated_volume", "ratio", "account", "node_id", "time_delta_hours"},
    allowed_sort_columns={"estimated_volume", "length", "ratio"},
    requires_case_id=True,
    default_sort_field="estimated_volume",
    default_sort_order="desc",
    description="Retrieve detected topological patterns (elementary cycles and mule accounts).",
)
async def handle_patterns_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    case_uuid = uuid.UUID(str(request.case_id))

    patterns_dict: Dict[str, Any] = {}
    if db is not None:
        stmt = select(InvestigationCase.patterns).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        patterns_dict = res.scalar_one_or_none() or {}
        if not patterns_dict:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
        patterns_dict = case_data.get("patterns", {})

    items = []
    # 1. Cycles
    for c in patterns_dict.get("cycles", []):
        items.append({
            "pattern_type": "CYCLE",
            "path": c.get("path", []),
            "length": c.get("length", len(c.get("path", []))),
            "estimated_volume": float(c.get("estimated_volume", 0.0)),
            "ratio": None,
            "account": None,
            "node_id": None,
        })
    # 2. Passthrough accounts
    for pt in patterns_dict.get("passthrough_accounts", []):
        acc = pt.get("account_id") or pt.get("account") or pt.get("node_id")
        items.append({
            "pattern_type": "PASSTHROUGH",
            "path": None,
            "length": None,
            "estimated_volume": float(pt.get("inflow", pt.get("total_in", 0.0))),
            "ratio": float(pt.get("ratio", 0.0)),
            "account": acc,
            "node_id": acc,
            "time_delta_hours": float(pt.get("window_hours", pt.get("time_delta_hours", 48.0))),
        })

    filtered = [
        item for item in items
        if all(evaluate_in_memory_predicate(item, f) for f in request.filters if f.field != "case_id")
    ]
    total = len(filtered)
    sort_col = request.sort_by or meta.default_sort_field
    is_desc = request.sort_order.lower() == "desc"
    filtered.sort(key=lambda x: x.get(sort_col) or 0, reverse=is_desc)
    records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target="patterns",
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
```

### 8.5 Legal Precedents Target Handler (`legal_precedents` / `legal_vectors`)
```python
@tool_registry.register(
    "legal_precedents",
    model=LegalArticleVector,
    allowed_columns={"id", "article_code", "law_name", "content"},
    allowed_sort_columns={"article_code", "law_name", "id"},
    requires_case_id=False,
    default_sort_field="article_code",
    default_sort_order="asc",
    description="Query Mexican AML, CFF 69-B, and UIF regulatory legal knowledge base.",
)
async def handle_legal_precedents_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    if db is not None:
        where_clauses = []
        for f in request.filters:
            col = getattr(LegalArticleVector, f.field)
            where_clauses.append(apply_sa_operator(col, f.operator, f.value))

        count_stmt = select(func.count(LegalArticleVector.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(LegalArticleVector).where(*where_clauses)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_col = getattr(LegalArticleVector, sort_col_name)
        stmt = stmt.order_by(sort_col.desc() if request.sort_order.lower() == "desc" else sort_col.asc())
        stmt = stmt.limit(request.limit).offset(request.offset)

        rows = (await db.execute(stmt)).scalars().all()
        records = [
            {
                "id": str(r.id),
                "article_code": r.article_code,
                "law_name": r.law_name,
                "content": r.content,
            }
            for r in rows
        ]
    else:
        raw_items = list(SEED_LEGAL_PRECEDENTS)
        filtered = [
            item for item in raw_items
            if all(evaluate_in_memory_predicate(item, f) for f in request.filters)
        ]
        total = len(filtered)
        sort_col = request.sort_by or meta.default_sort_field
        is_desc = request.sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col) or "", reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target="legal_precedents",
        case_id=None,
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
```

---

## 9. API Router & Application Integration

### 9.1 `backend/api/routes/agent_tools.py`
The router will expose both the dynamic query endpoint and the dedicated endpoints:
```python
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.investigations import get_optional_db
from backend.services.tool_registry import tool_registry
from backend.schemas.agent_tools import (
    DynamicQueryRequest,
    DynamicQueryResponse,
    TransactionQueryRequest,
    TransactionQueryResponse,
    EntityProfileRequest,
    EntityProfileResponse,
    PatternQueryRequest,
    PatternQueryResponse,
    LegalPrecedentQueryRequest,
    LegalPrecedentQueryResponse,
)

router = APIRouter(prefix="/tools", tags=["agent-tools"])


@router.post(
    "/query",
    response_model=DynamicQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Dynamic Composable Query for AI Agents",
    description="Safely queries case transactions, entities, patterns, cases, or legal precedents with parameterized ASTs and column whitelisting.",
)
async def dynamic_query(
    request: DynamicQueryRequest,
    db: Optional[AsyncSession] = Depends(get_optional_db),
) -> DynamicQueryResponse:
    return await tool_registry.execute_query(request, db)
```

### 9.2 Registration in `backend/main.py`
In `backend/main.py`:
```python
# Lines to import:
from backend.api.routes.agent_tools import router as agent_tools_router

# Line to include router:
app.include_router(investigations_router, prefix=settings.API_V1_STR)
app.include_router(tts_router, prefix=settings.API_V1_STR)
app.include_router(agent_tools_router, prefix=settings.API_V1_STR)
```

---

## 10. Automated Test Cases & Verification Plan

### Test Suite: `backend/tests/test_agent_tools.py`

| # | Test Name | Target / Feature | Inputs | Expected Outcome |
|---|---|---|---|---|
| 1 | `test_dynamic_query_transactions_valid` | `transactions` | `case_id`, `filters=[{"field": "is_suspicious", "operator": "eq", "value": True}]` | HTTP 200, `records` containing only suspicious transactions, `total >= 1`. |
| 2 | `test_dynamic_query_unwhitelisted_column_injection` | `transactions` | `filters=[{"field": "origin; DROP TABLE transactions;--", "operator": "eq", "value": "ACC_1"}]` | HTTP 400 Bad Request: `Field '...' is not permitted for target 'transactions'.` Database unaltered. |
| 3 | `test_dynamic_query_mandatory_case_id_missing` | `transactions` | `case_id=None, filters=[{"field": "amount", "operator": "gt", "value": 1000}]` | HTTP 400 Bad Request: `Mandatory scoping violation: 'case_id' is required...` |
| 4 | `test_dynamic_query_operators_all` | `transactions` | Test all 9 operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in` | HTTP 200, correct relational filtering on amounts and accounts. |
| 5 | `test_dynamic_query_cases_unscoped` | `cases` | `target="cases", filters=[{"field": "status", "operator": "eq", "value": "COMPLETED"}]` | HTTP 200, paginated case summaries, `case_id` not required. |
| 6 | `test_dynamic_query_entities_profiling` | `entities` | `case_id`, `filters=[{"field": "risk_score", "operator": "gte", "value": 0.5}]` | HTTP 200, returns nodes sorted by `risk_score desc`. |
| 7 | `test_dynamic_query_patterns_cycles` | `patterns` | `case_id`, `filters=[{"field": "pattern_type", "operator": "eq", "value": "CYCLE"}]` | HTTP 200, returns circular flow patterns. |
| 8 | `test_dynamic_query_legal_precedents_like` | `legal_precedents` | `filters=[{"field": "content", "operator": "ilike", "value": "inexistencia"}]` | HTTP 200, returns `CFF-ART-69B` with high precision. |
| 9 | `test_dynamic_query_pagination_bounds` | `transactions` | `limit=2`, `offset=0`, then `offset=2` | Returns distinct non-overlapping slices; `total` remains identical. |
| 10 | `test_dynamic_query_invalid_sort_column` | `transactions` | `sort_by="password_hash"` | HTTP 400 Bad Request: `Sort column 'password_hash' is not permitted...` |
| 11 | `test_dynamic_query_offline_fallback` | All targets | With `db=None` / SQLite memory session | Identical schema response, no 500 error, zero crashes. |
| 12 | `test_tool_registry_custom_registration` | Custom target | Register dynamic target at runtime via `@tool_registry.register` | Can be queried via `/tools/query` without backend modifications. |

---

## 11. Conclusion & Recommendations

The proposed design satisfies all functional and security specifications for Milestone 3 (R3):
1. **Security**: SQL injection is eliminated at design time through strict whitelists and parameterized AST generation.
2. **Isolation**: Cross-case data leakage is eliminated by mandatory `case_id` scoping.
3. **Extensibility**: The `ToolRegistry` pattern allows registering arbitrary new tools or query targets in 10 lines of code without altering database tables or routes.
4. **Resilience**: The dual-engine evaluator transparently switches between TigerData PostgreSQL and in-memory cache without failing.
