"""
Dynamic Tool Registry & Parameterized Query Engine for n8n AI Agents.
Enforces column whitelisting, mandatory case_id scoping, parameterized SQL generation,
and dual execution (PostgreSQL AsyncSession + in-memory INVESTIGATION_CASES fallback).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union
import uuid

from fastapi import HTTPException, status
from sqlalchemy import DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.investigations import INVESTIGATION_CASES
from backend.models.forensic import (
    InvestigationCase,
    LegalArticleVector,
    SEED_LEGAL_PRECEDENTS,
    TransactionRecord,
)
from backend.schemas.agent_tools import (
    DynamicQueryRequest,
    DynamicQueryResponse,
    FilterOperator,
    QueryFilter,
    SortOrder,
    TARGET_FIELD_WHITELISTS,
    TargetEntity,
)


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


def parse_datetime_safe(val: Any) -> Optional[datetime]:
    """Parses datetime from ISO string, epoch float/int, or datetime."""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(float(val), tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def apply_sa_operator(column: Any, operator_val: Union[FilterOperator, str], value: Any) -> Any:
    """
    Safely compiles a filter operator into a parameterized SQLAlchemy expression.
    Zero string concatenation or raw SQL injection vulnerability.
    """
    op = operator_val.value.lower() if isinstance(operator_val, FilterOperator) else str(operator_val).lower()

    # Column-level type coercion for DateTime columns (defense-in-depth)
    if hasattr(column, "type") and isinstance(column.type, DateTime):
        if op in ("in", "not_in") and isinstance(value, (list, tuple, set)):
            value = [parse_datetime_safe(x) or x for x in value]
        elif isinstance(value, (str, int, float)):
            dt_parsed = parse_datetime_safe(value)
            if dt_parsed is not None:
                value = dt_parsed

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
        val_list = list(value)
        if len(val_list) == 0:
            return column.in_([None]) & column.is_not(None)
        return column.in_(val_list)
    elif op == "not_in":
        if not isinstance(value, (list, tuple, set)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operator 'not_in' requires an array/list value, got {type(value).__name__}",
            )
        val_list = list(value)
        if len(val_list) == 0:
            return True
        return column.not_in(val_list)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported operator '{op}'. Allowed operators: eq, neq, gt, gte, lt, lte, like, ilike, in, not_in",
        )


def evaluate_in_memory_predicate(item: Dict[str, Any], f: QueryFilter) -> bool:
    """Evaluates a QueryFilter condition against an in-memory dictionary item."""
    field_name = f.field
    val = item.get(field_name)

    # Secondary field resolution (e.g. entity_id -> id or id -> entity_id)
    if val is None:
        if field_name == "entity_id":
            val = item.get("id")
        elif field_name == "id":
            val = item.get("entity_id") or item.get("account")
        elif field_name == "account":
            val = item.get("node_id") or item.get("account_id")

    op = f.operator.value.lower() if isinstance(f.operator, FilterOperator) else str(f.operator).lower()
    target_val = f.value

    # Datetime handling for DateTime fields
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

    if op == "eq":
        if isinstance(val, (int, float)) and isinstance(target_val, (int, float)):
            return float(val) == float(target_val)
        if isinstance(val, bool) or isinstance(target_val, bool):
            return bool(val) == bool(target_val)
        return str(val) == str(target_val)
    elif op == "neq":
        if isinstance(val, (int, float)) and isinstance(target_val, (int, float)):
            return float(val) != float(target_val)
        if isinstance(val, bool) or isinstance(target_val, bool):
            return bool(val) != bool(target_val)
        return str(val) != str(target_val)
    elif op == "gt":
        if val is None or target_val is None:
            return False
        try:
            return float(val) > float(target_val)
        except (ValueError, TypeError):
            return str(val) > str(target_val)
    elif op == "gte":
        if val is None or target_val is None:
            return False
        try:
            return float(val) >= float(target_val)
        except (ValueError, TypeError):
            return str(val) >= str(target_val)
    elif op == "lt":
        if val is None or target_val is None:
            return False
        try:
            return float(val) < float(target_val)
        except (ValueError, TypeError):
            return str(val) < str(target_val)
    elif op == "lte":
        if val is None or target_val is None:
            return False
        try:
            return float(val) <= float(target_val)
        except (ValueError, TypeError):
            return str(val) <= str(target_val)
    elif op == "like":
        val_str = str(val or "")
        clean_target = str(target_val or "").strip("%")
        return clean_target in val_str
    elif op == "ilike":
        val_str = str(val or "").lower()
        clean_target = str(target_val or "").strip("%").lower()
        return clean_target in val_str
    elif op == "in":
        if not isinstance(target_val, (list, tuple, set)):
            return False
        # If val is a list, check intersection
        if isinstance(val, list):
            return any(x in target_val or str(x) in [str(t) for t in target_val] for x in val)
        return val in target_val or str(val) in [str(t) for t in target_val]
    elif op == "not_in":
        if not isinstance(target_val, (list, tuple, set)):
            return True
        if isinstance(val, list):
            return not any(x in target_val or str(x) in [str(t) for t in target_val] for x in val)
        return val not in target_val and str(val) not in [str(t) for t in target_val]
    return False


class ToolRegistry:
    """
    Extensible query handler registry allowing registration of dynamic query
    targets with strict column whitelisting, parameterized SQL generation,
    and mandatory case_id scoping.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._metadata: Dict[str, TargetMetadata] = {}
        self._aliases: Dict[str, str] = {}

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
        aliases: Optional[List[str]] = None,
    ) -> Callable:
        """Registers a target query handler. Supports direct invocation or decorator usage."""
        def decorator(fn: Callable) -> Callable:
            cols = set(allowed_columns) if allowed_columns else set()
            sort_cols = set(allowed_sort_columns) if allowed_sort_columns else cols
            def_sort = default_sort_field or (next(iter(sort_cols)) if sort_cols else "id")
            meta = TargetMetadata(
                target=target,
                model=model,
                allowed_columns=cols,
                allowed_sort_columns=sort_cols,
                requires_case_id=requires_case_id,
                default_sort_field=def_sort,
                default_sort_order=default_sort_order,
                description=description,
            )
            self._handlers[target] = fn
            self._metadata[target] = meta

            if aliases:
                for alias in aliases:
                    self._aliases[alias] = target
                    self._handlers[alias] = fn
                    self._metadata[alias] = TargetMetadata(
                        target=alias,
                        model=model,
                        allowed_columns=cols,
                        allowed_sort_columns=sort_cols,
                        requires_case_id=requires_case_id,
                        default_sort_field=def_sort,
                        default_sort_order=default_sort_order,
                        description=f"Alias for {target}. {description}",
                    )
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    def get_metadata(self, target: str) -> Optional[TargetMetadata]:
        canonical = self._aliases.get(target, target)
        return self._metadata.get(canonical)

    def list_targets(self) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for name, meta in self._metadata.items():
            if meta.target not in seen:
                seen.add(meta.target)
                result.append({
                    "target": meta.target,
                    "description": meta.description,
                    "requires_case_id": meta.requires_case_id,
                    "allowed_columns": sorted(list(meta.allowed_columns)),
                    "allowed_sort_columns": sorted(list(meta.allowed_sort_columns)),
                    "default_sort": f"{meta.default_sort_field} {meta.default_sort_order}",
                })
        return result

    async def execute_query(
        self,
        request: DynamicQueryRequest,
        db: Optional[AsyncSession] = None,
    ) -> DynamicQueryResponse:
        """Dispatches dynamic query to registered target handler with strict validation."""
        target_name = request.target.value if isinstance(request.target, TargetEntity) else str(request.target)
        canonical_target = self._aliases.get(target_name, target_name)
        meta = self._metadata.get(target_name) or self._metadata.get(canonical_target)

        if not meta or canonical_target not in self._handlers:
            allowed = sorted(list(self._metadata.keys()))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported query target '{target_name}'. Allowed targets: {allowed}",
            )

        # 1. Mandatory case_id Scoping Enforcement
        if meta.requires_case_id:
            case_id = request.case_id
            if not case_id:
                for f in request.filters:
                    if f.field == "case_id" and f.operator in (FilterOperator.EQ, "eq"):
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
            try:
                uuid.UUID(str(case_id))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid UUID format for case_id: '{case_id}'",
                )

        # 2. Column Whitelist Validation
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

        # 3. Sort Column Validation
        sort_by = request.sort_by
        if sort_by is not None:
            if sort_by not in meta.allowed_sort_columns:
                allowed_sort = sorted(list(meta.allowed_sort_columns))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Sort column '{sort_by}' is not permitted for target '{target_name}'. "
                        f"Allowed sort columns: {allowed_sort}"
                    ),
                )

        handler = self._handlers[canonical_target]
        return await handler(request, meta, db)


# Singleton Registry Instance
tool_registry = ToolRegistry()


# =============================================================================
# Built-In Target Handlers
# =============================================================================

# -----------------------------------------------------------------------------
# 1. Transactions Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "transactions",
    model=TransactionRecord,
    allowed_columns=set(TARGET_FIELD_WHITELISTS["transactions"].keys()),
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
    raw_case_id = request.case_id
    if not raw_case_id:
        for f in request.filters:
            if f.field == "case_id":
                raw_case_id = f.value
                break
    case_uuid = uuid.UUID(str(raw_case_id))

    if db is not None:
        where_clauses = [TransactionRecord.case_id == case_uuid]
        for f in request.filters:
            if f.field == "case_id":
                continue
            col = getattr(TransactionRecord, f.field)
            val = f.value
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
            where_clauses.append(apply_sa_operator(col, f.operator, val))

        count_stmt = select(func.count(TransactionRecord.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(TransactionRecord).where(*where_clauses)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_col = getattr(TransactionRecord, sort_col_name)
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        stmt = stmt.order_by(sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc())
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
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case '{case_uuid}' not found.",
            )

        raw_records = case_data.get("transactions", [])
        if not raw_records and "subgraph" in case_data:
            edges = case_data["subgraph"].get("edges", [])
            raw_records = [
                {
                    "id": str(uuid.uuid4()),
                    "case_id": str(case_uuid),
                    "origin": e.get("source", ""),
                    "destination": e.get("target", ""),
                    "amount": float(e.get("amount", 0.0)),
                    "timestamp": (e.get("timestamps") or [datetime.now(timezone.utc).isoformat()])[0],
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
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        is_desc = sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col_name) if x.get(sort_col_name) is not None else 0, reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )


# -----------------------------------------------------------------------------
# 2. Cases Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "cases",
    model=InvestigationCase,
    allowed_columns=set(TARGET_FIELD_WHITELISTS["cases"].keys()),
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
    scoped_case_id = str(request.case_id) if request.case_id else None

    if db is not None:
        where_clauses = []
        if scoped_case_id:
            where_clauses.append(InvestigationCase.id == uuid.UUID(scoped_case_id))
        for f in request.filters:
            col = getattr(InvestigationCase, f.field)
            val = f.value
            if f.field in ("created_at", "updated_at"):
                if isinstance(val, (list, tuple, set)):
                    val = [parse_datetime_safe(x) or x for x in val]
                elif isinstance(val, (str, int, float)):
                    val_dt = parse_datetime_safe(val)
                    if val_dt:
                        val = val_dt
            where_clauses.append(apply_sa_operator(col, f.operator, val))

        count_stmt = select(func.count(InvestigationCase.id)).where(*where_clauses)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(InvestigationCase).where(*where_clauses)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_col = getattr(InvestigationCase, sort_col_name)
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        stmt = stmt.order_by(sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc())
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
        raw_cases = []
        for k, v in INVESTIGATION_CASES.items():
            cid = v.get("case_id") or v.get("id") or k
            raw_cases.append({
                "id": cid,
                "filename": v.get("filename", "dataset.csv"),
                "status": v.get("status", "PROCESSING"),
                "created_at": v.get("created_at"),
                "updated_at": v.get("updated_at") or v.get("created_at"),
                "metrics": v.get("metrics", {}),
                "has_verdict": v.get("verdict") is not None,
            })

        if scoped_case_id:
            raw_cases = [c for c in raw_cases if c["id"] == scoped_case_id]

        filtered = [
            c for c in raw_cases
            if all(evaluate_in_memory_predicate(c, f) for f in request.filters)
        ]
        total = len(filtered)
        sort_col_name = request.sort_by or meta.default_sort_field
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        is_desc = sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col_name) or "", reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=scoped_case_id,
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )


# -----------------------------------------------------------------------------
# 3. Entities & Nodes Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "entities",
    allowed_columns=set(TARGET_FIELD_WHITELISTS["entities"].keys()),
    allowed_sort_columns={"risk_score", "total_in", "total_out", "net_flow", "in_degree", "out_degree", "id", "entity_id"},
    requires_case_id=True,
    default_sort_field="risk_score",
    default_sort_order="desc",
    description="Profile financial entities/nodes, volumes, degrees, and risk scores.",
    aliases=["nodes"],
)
async def handle_entities_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    raw_case_id = request.case_id
    if not raw_case_id:
        for f in request.filters:
            if f.field == "case_id":
                raw_case_id = f.value
                break
    case_uuid = uuid.UUID(str(raw_case_id))

    nodes: List[Dict[str, Any]] = []
    if db is not None:
        stmt = select(InvestigationCase.subgraph).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        subgraph = res.scalar_one_or_none()
        if subgraph is None:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
            subgraph = {}
        nodes = list(subgraph.get("nodes", []))
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
        nodes = list(case_data.get("subgraph", {}).get("nodes", []))

    normalized: List[Dict[str, Any]] = []
    for n in nodes:
        node_id = str(n.get("id") or n.get("entity_id") or n.get("account"))
        t_in = float(n.get("total_inflow", n.get("total_in", 0.0)))
        t_out = float(n.get("total_outflow", n.get("total_out", 0.0)))
        r_score = float(n.get("risk_score", 0.0))
        reasons = n.get("reasons", [])
        normalized.append({
            "id": node_id,
            "entity_id": node_id,
            "total_in": t_in,
            "total_out": t_out,
            "net_flow": round(t_in - t_out, 2),
            "in_degree": int(n.get("in_degree", 0)),
            "out_degree": int(n.get("out_degree", 0)),
            "risk_score": r_score,
            "is_suspicious": bool(reasons or r_score >= 0.5),
            "reasons": reasons,
        })

    filtered = [
        item for item in normalized
        if all(evaluate_in_memory_predicate(item, f) for f in request.filters if f.field != "case_id")
    ]
    total = len(filtered)
    sort_col = request.sort_by or meta.default_sort_field
    sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
    is_desc = sort_order.lower() == "desc"
    filtered.sort(key=lambda x: x.get(sort_col) if x.get(sort_col) is not None else 0, reverse=is_desc)
    records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )


# -----------------------------------------------------------------------------
# 4. Patterns, Cycles & Passthrough Accounts Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "patterns",
    allowed_columns=set(TARGET_FIELD_WHITELISTS["patterns"].keys()),
    allowed_sort_columns={"estimated_volume", "length", "ratio"},
    requires_case_id=True,
    default_sort_field="estimated_volume",
    default_sort_order="desc",
    description="Retrieve detected topological patterns (elementary cycles and pass-through mule accounts).",
    aliases=["cycles", "passthrough_accounts"],
)
async def handle_patterns_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    raw_case_id = request.case_id
    if not raw_case_id:
        for f in request.filters:
            if f.field == "case_id":
                raw_case_id = f.value
                break
    case_uuid = uuid.UUID(str(raw_case_id))

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
    target_name = request.target.value if isinstance(request.target, TargetEntity) else str(request.target)

    # 1. Cycles
    if target_name in ("patterns", "cycles"):
        for c in patterns_dict.get("cycles", []):
            path = c.get("path", [])
            items.append({
                "pattern_type": "CYCLE",
                "path": path,
                "length": c.get("length", len(path)),
                "estimated_volume": float(c.get("estimated_volume", 0.0)),
                "ratio": None,
                "account": None,
                "node_id": None,
                "time_delta_hours": None,
            })

    # 2. Passthrough accounts
    if target_name in ("patterns", "passthrough_accounts"):
        for pt in patterns_dict.get("passthrough_accounts", []):
            acc = pt.get("account_id") or pt.get("account") or pt.get("node_id")
            t_in = float(pt.get("inflow", pt.get("total_in", 0.0)))
            t_out = float(pt.get("outflow", pt.get("total_out", 0.0)))
            items.append({
                "pattern_type": "PASSTHROUGH",
                "path": None,
                "length": None,
                "estimated_volume": t_in,
                "ratio": float(pt.get("ratio", 0.0)),
                "account": acc,
                "node_id": acc,
                "time_delta_hours": float(pt.get("window_hours", pt.get("time_delta_hours", 48.0))),
                "total_in": t_in,
                "total_out": t_out,
            })

    filtered = [
        item for item in items
        if all(evaluate_in_memory_predicate(item, f) for f in request.filters if f.field != "case_id")
    ]
    total = len(filtered)
    sort_col = request.sort_by or meta.default_sort_field
    sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
    is_desc = sort_order.lower() == "desc"
    filtered.sort(key=lambda x: x.get(sort_col) if x.get(sort_col) is not None else 0, reverse=is_desc)
    records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )


# -----------------------------------------------------------------------------
# 5. Edges Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "edges",
    allowed_columns=set(TARGET_FIELD_WHITELISTS["edges"].keys()),
    allowed_sort_columns={"amount", "count", "source", "target"},
    requires_case_id=True,
    default_sort_field="amount",
    default_sort_order="desc",
    description="Query graph edges and transferred amounts within an investigation case.",
)
async def handle_edges_query(
    request: DynamicQueryRequest,
    meta: TargetMetadata,
    db: Optional[AsyncSession] = None,
) -> DynamicQueryResponse:
    start_t = time.perf_counter()
    raw_case_id = request.case_id
    if not raw_case_id:
        for f in request.filters:
            if f.field == "case_id":
                raw_case_id = f.value
                break
    case_uuid = uuid.UUID(str(raw_case_id))

    edges: List[Dict[str, Any]] = []
    if db is not None:
        stmt = select(InvestigationCase.subgraph).where(InvestigationCase.id == case_uuid)
        res = await db.execute(stmt)
        subgraph = res.scalar_one_or_none()
        if subgraph is None:
            exists = (await db.execute(select(InvestigationCase.id).where(InvestigationCase.id == case_uuid))).scalar_one_or_none()
            if not exists:
                raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
            subgraph = {}
        edges = list(subgraph.get("edges", []))
    else:
        case_data = INVESTIGATION_CASES.get(str(case_uuid))
        if not case_data:
            raise HTTPException(status_code=404, detail=f"Investigation case '{case_uuid}' not found.")
        edges = list(case_data.get("subgraph", {}).get("edges", []))

    normalized: List[Dict[str, Any]] = []
    for e in edges:
        normalized.append({
            "source": str(e.get("source", "")),
            "target": str(e.get("target", "")),
            "amount": float(e.get("amount", 0.0)),
            "count": int(e.get("count", 1)),
        })

    filtered = [
        item for item in normalized
        if all(evaluate_in_memory_predicate(item, f) for f in request.filters if f.field != "case_id")
    ]
    total = len(filtered)
    sort_col = request.sort_by or meta.default_sort_field
    sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
    is_desc = sort_order.lower() == "desc"
    filtered.sort(key=lambda x: x.get(sort_col) if x.get(sort_col) is not None else 0, reverse=is_desc)
    records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=str(case_uuid),
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )


# -----------------------------------------------------------------------------
# 6. Legal Precedents & Legal Vectors Handler
# -----------------------------------------------------------------------------
@tool_registry.register(
    "legal_precedents",
    model=LegalArticleVector,
    allowed_columns=set(TARGET_FIELD_WHITELISTS["legal_precedents"].keys()),
    allowed_sort_columns={"article_code", "law_name", "id"},
    requires_case_id=False,
    default_sort_field="article_code",
    default_sort_order="asc",
    description="Query Mexican AML, CFF 69-B, and UIF regulatory legal knowledge base.",
    aliases=["legal_vectors"],
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
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        stmt = stmt.order_by(sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc())
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
        raw_items = [
            {
                "id": str(uuid.uuid4()),
                "article_code": item["article_code"],
                "law_name": item["law_name"],
                "content": item["content"],
            }
            for item in SEED_LEGAL_PRECEDENTS
        ]
        filtered = [
            item for item in raw_items
            if all(evaluate_in_memory_predicate(item, f) for f in request.filters)
        ]
        total = len(filtered)
        sort_col = request.sort_by or meta.default_sort_field
        sort_order = request.sort_order.value if isinstance(request.sort_order, SortOrder) else str(request.sort_order)
        is_desc = sort_order.lower() == "desc"
        filtered.sort(key=lambda x: x.get(sort_col) or "", reverse=is_desc)
        records = filtered[request.offset : request.offset + request.limit]

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    return DynamicQueryResponse(
        target=meta.target,
        case_id=None,
        total=total,
        count=len(records),
        limit=request.limit,
        offset=request.offset,
        applied_filters=request.filters,
        records=records,
        execution_time_ms=duration_ms,
    )
