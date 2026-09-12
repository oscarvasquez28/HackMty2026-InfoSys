"""
Pydantic v2 schemas for Agent Tools API endpoints, dynamic query interfaces,
and n8n forensic auditor tool contracts.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# =============================================================================
# Enums
# =============================================================================

class TargetEntity(str, Enum):
    """Supported entity targets for dynamic query builder."""
    TRANSACTIONS = "transactions"
    CASES = "cases"
    ENTITIES = "entities"
    NODES = "nodes"
    EDGES = "edges"
    PATTERNS = "patterns"
    CYCLES = "cycles"
    PASSTHROUGH_ACCOUNTS = "passthrough_accounts"
    LEGAL_PRECEDENTS = "legal_precedents"
    LEGAL_VECTORS = "legal_vectors"


class FilterOperator(str, Enum):
    """Relational and pattern filter operators for composable queries."""
    EQ = "eq"          # ==
    NEQ = "neq"        # !=
    GT = "gt"          # >
    GTE = "gte"        # >=
    LT = "lt"          # <
    LTE = "lte"        # <=
    LIKE = "like"      # SQL LIKE / wildcard match
    ILIKE = "ilike"    # Case-insensitive LIKE
    IN = "in"          # Value in list
    NOT_IN = "not_in"  # Value not in list


class SortOrder(str, Enum):
    """Sort direction."""
    ASC = "asc"
    DESC = "desc"


class PatternType(str, Enum):
    """Topological pattern categories."""
    ALL = "all"
    CYCLES = "cycles"
    PASSTHROUGH_MULES = "passthrough_mules"


# =============================================================================
# Whitelist Constants for Dynamic Query Security
# =============================================================================

TARGET_FIELD_WHITELISTS: Dict[str, Dict[str, type]] = {
    TargetEntity.TRANSACTIONS.value: {
        "id": str,
        "case_id": str,
        "origin": str,
        "destination": str,
        "amount": float,
        "timestamp": datetime,
        "is_suspicious": bool,
        "reasons": list,
    },
    TargetEntity.CASES.value: {
        "id": str,
        "filename": str,
        "status": str,
        "created_at": datetime,
        "updated_at": datetime,
    },
    TargetEntity.ENTITIES.value: {
        "id": str,
        "entity_id": str,
        "total_in": float,
        "total_out": float,
        "net_flow": float,
        "in_degree": int,
        "out_degree": int,
        "risk_score": float,
        "is_suspicious": bool,
        "reasons": list,
    },
    TargetEntity.NODES.value: {
        "id": str,
        "entity_id": str,
        "total_in": float,
        "total_out": float,
        "net_flow": float,
        "in_degree": int,
        "out_degree": int,
        "risk_score": float,
        "is_suspicious": bool,
        "reasons": list,
    },
    TargetEntity.EDGES.value: {
        "source": str,
        "target": str,
        "amount": float,
        "count": int,
    },
    TargetEntity.PATTERNS.value: {
        "pattern_type": str,
        "length": int,
        "estimated_volume": float,
        "ratio": float,
        "account": str,
        "node_id": str,
        "time_delta_hours": float,
        "path": list,
    },
    TargetEntity.CYCLES.value: {
        "path": list,
        "length": int,
        "estimated_volume": float,
    },
    TargetEntity.PASSTHROUGH_ACCOUNTS.value: {
        "account": str,
        "total_in": float,
        "total_out": float,
        "ratio": float,
        "time_delta_hours": float,
        "window_hours": float,
        "inflow": float,
        "outflow": float,
    },
    TargetEntity.LEGAL_PRECEDENTS.value: {
        "id": str,
        "article_code": str,
        "law_name": str,
        "content": str,
    },
    TargetEntity.LEGAL_VECTORS.value: {
        "id": str,
        "article_code": str,
        "law_name": str,
        "content": str,
    },
}

CASE_SCOPED_TARGETS = {
    TargetEntity.TRANSACTIONS.value,
    TargetEntity.ENTITIES.value,
    TargetEntity.NODES.value,
    TargetEntity.EDGES.value,
    TargetEntity.PATTERNS.value,
    TargetEntity.CYCLES.value,
    TargetEntity.PASSTHROUGH_ACCOUNTS.value,
}


# =============================================================================
# 1. Transaction Query Models
# =============================================================================

class TransactionItem(BaseModel):
    """Individual transaction record returned in query response."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: Union[uuid.UUID, str] = Field(..., description="Unique transaction UUID")
    case_id: Union[uuid.UUID, str] = Field(..., description="Associated investigation case UUID")
    origin: str = Field(..., description="Originating account ID")
    destination: str = Field(..., description="Destination account ID")
    amount: float = Field(..., description="Transaction transfer amount in MXN")
    timestamp: Union[datetime, str] = Field(..., description="Transaction UTC timestamp or step")
    is_suspicious: bool = Field(default=False, description="Whether flagged as suspicious")
    reasons: List[str] = Field(default_factory=list, description="Suspicion justification flags")

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount_float(cls, v: Any) -> float:
        if isinstance(v, (Decimal, int, float, str)):
            return float(v)
        return float(v)


class TransactionQueryRequest(BaseModel):
    """Request payload for filtering transactions within a case."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID to query within")
    origin: Optional[str] = Field(None, description="Filter by origin account ID (exact or prefix)")
    destination: Optional[str] = Field(None, description="Filter by destination account ID (exact or prefix)")
    min_amount: Optional[float] = Field(None, ge=0.0, description="Minimum transfer amount in MXN")
    max_amount: Optional[float] = Field(None, ge=0.0, description="Maximum transfer amount in MXN")
    start_time: Optional[datetime] = Field(None, description="Lower bound timestamp (inclusive, UTC)")
    end_time: Optional[datetime] = Field(None, description="Upper bound timestamp (inclusive, UTC)")
    is_suspicious: Optional[bool] = Field(None, description="Filter by suspicion flag (True/False/None for all)")
    limit: int = Field(default=50, ge=1, le=1000, description="Pagination page size limit (1-1000)")
    offset: int = Field(default=0, ge=0, description="Pagination offset (>= 0)")

    @model_validator(mode="after")
    def validate_bounds(self) -> "TransactionQueryRequest":
        if self.min_amount is not None and self.max_amount is not None:
            if self.max_amount < self.min_amount:
                raise ValueError(
                    f"max_amount ({self.max_amount}) cannot be less than min_amount ({self.min_amount})"
                )
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError(
                    f"end_time ({self.end_time.isoformat()}) must be greater than or equal to start_time ({self.start_time.isoformat()})"
                )
        return self


class TransactionQueryResponse(BaseModel):
    """Response payload returning paginated transaction records."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID")
    total: int = Field(..., ge=0, description="Total matching transaction records")
    limit: int = Field(..., ge=1, description="Echoed pagination limit")
    offset: int = Field(..., ge=0, description="Echoed pagination offset")
    total_volume_mxn: float = Field(default=0.0, ge=0.0, description="Aggregated volume of matching records in MXN")
    items: List[TransactionItem] = Field(default_factory=list, description="List of matching transaction records")


# =============================================================================
# 2. Entity Profile Models
# =============================================================================

class EntityProfileItem(BaseModel):
    """Detailed topological and forensic profile for a single entity/account."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    entity_id: str = Field(
        ...,
        validation_alias=AliasChoices("entity_id", "id", "account"),
        description="Bank account or entity identifier",
    )
    in_degree: int = Field(default=0, ge=0, description="Count of distinct incoming counterparties")
    out_degree: int = Field(default=0, ge=0, description="Count of distinct outgoing counterparties")
    total_inflow: float = Field(
        default=0.0,
        validation_alias=AliasChoices("total_inflow", "total_in"),
        description="Total funds received in MXN",
    )
    total_outflow: float = Field(
        default=0.0,
        validation_alias=AliasChoices("total_outflow", "total_out"),
        description="Total funds dispersed in MXN",
    )
    net_flow: float = Field(default=0.0, description="Net flow in MXN (total_inflow - total_outflow)")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated forensic risk score [0.0 - 1.0]")
    reasons: List[str] = Field(default_factory=list, description="Assigned topological risk justification flags")
    is_suspicious: bool = Field(default=False, description="True if node is part of suspicious subgraph")
    counterparties_in: Optional[List[str]] = Field(default=None, description="Optional list of source account IDs")
    counterparties_out: Optional[List[str]] = Field(default=None, description="Optional list of target account IDs")

    @model_validator(mode="before")
    @classmethod
    def compute_net_flow_and_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            t_in = float(data.get("total_inflow", data.get("total_in", 0.0)))
            t_out = float(data.get("total_outflow", data.get("total_out", 0.0)))
            if "net_flow" not in data:
                data["net_flow"] = round(t_in - t_out, 2)
            reasons = data.get("reasons", [])
            if "is_suspicious" not in data:
                data["is_suspicious"] = bool(reasons or float(data.get("risk_score", 0.0)) >= 0.5)
        return data


class EntityProfileRequest(BaseModel):
    """Request payload for entity profiling tool."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID to profile entities in")
    entity_id: Optional[str] = Field(None, description="Optional specific account ID; if omitted, profiles all entities")
    min_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Filter for entities with risk_score >= threshold")
    is_suspicious: Optional[bool] = Field(None, description="Filter for suspicious entities only")
    limit: int = Field(default=50, ge=1, le=500, description="Pagination page size limit (1-500)")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class EntityProfileResponse(BaseModel):
    """Response payload for entity profiling tool."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID")
    total_entities: int = Field(..., ge=0, description="Total matching entities profiled")
    entities: List[EntityProfileItem] = Field(default_factory=list, description="Profiled entities")


# =============================================================================
# 3. Pattern Extraction Models
# =============================================================================

class CyclePatternItem(BaseModel):
    """Detected circular transaction flow (e.g. smurfing or layering loop)."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    path: List[str] = Field(..., description="Ordered list of account IDs forming the closed cycle")
    length: int = Field(..., ge=2, description="Number of hops in cycle")
    estimated_volume: float = Field(default=0.0, ge=0.0, description="Estimated funds circulating through cycle in MXN")


class PassthroughMuleItem(BaseModel):
    """Detected high-velocity pass-through mule account."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    account: str = Field(
        ...,
        validation_alias=AliasChoices("account", "account_id", "node_id"),
        description="Mule account identifier",
    )
    total_in: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("total_in", "inflow"),
        description="Total incoming volume in MXN",
    )
    total_out: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("total_out", "outflow"),
        description="Total outgoing volume in MXN",
    )
    ratio: float = Field(..., ge=0.0, le=1.0, description="Flow turnover ratio (min/max >= 0.90)")
    time_delta_hours: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("time_delta_hours", "window_hours"),
        description="Elapsed hours between first inflow and last outflow",
    )


class PatternQueryRequest(BaseModel):
    """Request payload for extracting detected patterns in a case."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID to query patterns from")
    pattern_type: PatternType = Field(default=PatternType.ALL, description="Filter pattern types: 'all', 'cycles', 'passthrough_mules'")
    min_cycle_length: Optional[int] = Field(None, ge=2, le=10, description="Minimum cycle path length filter")
    max_cycle_length: Optional[int] = Field(None, ge=2, le=10, description="Maximum cycle path length filter")
    min_volume: Optional[float] = Field(None, ge=0.0, description="Minimum circulating volume in MXN")
    min_passthrough_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum pass-through ratio filter")

    @model_validator(mode="after")
    def validate_cycle_bounds(self) -> "PatternQueryRequest":
        if self.min_cycle_length is not None and self.max_cycle_length is not None:
            if self.max_cycle_length < self.min_cycle_length:
                raise ValueError(
                    f"max_cycle_length ({self.max_cycle_length}) cannot be less than min_cycle_length ({self.min_cycle_length})"
                )
        return self


class PatternQueryResponse(BaseModel):
    """Response payload for detected patterns tool."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    case_id: Union[uuid.UUID, str] = Field(..., description="Investigation case UUID")
    pattern_type: str = Field(..., description="Pattern type queried")
    total_cycles_count: int = Field(default=0, ge=0, description="Count of cycles returned")
    total_mules_count: int = Field(default=0, ge=0, description="Count of pass-through mule accounts returned")
    cycles: List[CyclePatternItem] = Field(default_factory=list, description="List of circular layering patterns")
    passthrough_mules: List[PassthroughMuleItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("passthrough_mules", "passthrough_accounts"),
        description="List of detected mule accounts",
    )


# =============================================================================
# 4. Legal Precedent Vector Search Models
# =============================================================================

class LegalPrecedentItem(BaseModel):
    """Individual legal precedent match returned by vector search."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    article_code: str = Field(..., description="Standard statutory article code (e.g. CFF-ART-69B, UIF-ROI-24H)")
    law_name: str = Field(..., description="Statute or regulatory framework name")
    content: str = Field(..., description="Full legal text, jurisprudence thesis, or regulatory criteria")
    similarity_score: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity score [-1.0 to 1.0]")
    distance: Optional[float] = Field(None, ge=0.0, description="pgvector cosine distance (distance = 1 - similarity)")


class LegalPrecedentQueryRequest(BaseModel):
    """Request payload for searching Mexican AML statutes and tax jurisprudence."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    query_text: str = Field(..., min_length=1, description="Natural language search text for legal matching")
    query_vector: Optional[List[float]] = Field(
        None,
        description="Optional pre-computed 1536-dimensional embedding vector; generated automatically if omitted",
    )
    top_k: int = Field(default=3, ge=1, le=20, description="Maximum number of relevant articles to return")
    similarity_threshold: Optional[float] = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity cutoff threshold",
    )
    law_name_filter: Optional[str] = Field(
        None,
        description="Optional filter for specific law names (e.g. 'Código Fiscal', 'UIF', 'NIF')",
    )

    @field_validator("query_vector")
    @classmethod
    def validate_vector_dimension(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None:
            if len(v) != 1536:
                raise ValueError(f"query_vector must have exactly 1536 dimensions, received {len(v)}")
        return v


class LegalPrecedentQueryResponse(BaseModel):
    """Response payload for legal precedent vector search tool."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    query_text: str = Field(..., description="Echoed input query text")
    top_k: int = Field(..., ge=1, description="Requested top_k limit")
    total_matches: int = Field(..., ge=0, description="Count of articles matching threshold")
    results: List[LegalPrecedentItem] = Field(default_factory=list, description="Ranked matching legal precedents")


# =============================================================================
# 5. Dynamic Composable Query Models
# =============================================================================

class QueryFilter(BaseModel):
    """Individual filter clause in composable dynamic query."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    field: str = Field(..., description="Target field/column name to filter on")
    operator: FilterOperator = Field(..., description="Comparison operator (eq, neq, gt, gte, lt, lte, like, ilike, in, not_in)")
    value: Any = Field(..., description="Filter comparison value (scalar or list for 'in'/'not_in')")

    @model_validator(mode="after")
    def validate_operator_value_consistency(self) -> "QueryFilter":
        if self.operator in (FilterOperator.IN, FilterOperator.NOT_IN):
            if not isinstance(self.value, (list, tuple, set)):
                raise ValueError(
                    f"Operator '{self.operator.value}' requires an array/list value, got {type(self.value).__name__}"
                )
        return self


class DynamicQueryRequest(BaseModel):
    """Request payload for arbitrary dynamic queries against case data."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    target: Union[TargetEntity, str] = Field(..., description="Data entity collection to query")
    case_id: Optional[Union[uuid.UUID, str]] = Field(
        None,
        description="Investigation case UUID (mandatory for case-scoped targets: transactions, nodes, edges, cycles, passthrough_accounts)",
    )
    filters: List[QueryFilter] = Field(default_factory=list, description="List of filter conditions to apply (ANDed)")
    sort_by: Optional[str] = Field(None, description="Field name to sort results by")
    sort_order: SortOrder = Field(default=SortOrder.ASC, description="Sort direction ('asc' or 'desc')")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum number of records to return")
    offset: int = Field(default=0, ge=0, description="Number of records to skip")

    @model_validator(mode="after")
    def validate_case_id_and_fields(self) -> "DynamicQueryRequest":
        target_str = self.target.value if isinstance(self.target, TargetEntity) else str(self.target)

        # Case-scoped targets require case_id either at root or in filters
        if target_str in CASE_SCOPED_TARGETS and not self.case_id:
            has_case_id_filter = any(
                f.field == "case_id" and f.operator in (FilterOperator.EQ, "eq")
                for f in self.filters
            )
            if not has_case_id_filter:
                raise ValueError(f"case_id is required when querying target '{target_str}'")

        # Whitelist field validation if known target in TARGET_FIELD_WHITELISTS
        if target_str in TARGET_FIELD_WHITELISTS:
            whitelist = TARGET_FIELD_WHITELISTS[target_str]
            for f in self.filters:
                if f.field not in whitelist:
                    allowed = sorted(list(whitelist.keys()))
                    raise ValueError(
                        f"Field '{f.field}' is not permissible for target '{target_str}'. Allowed fields: {allowed}"
                    )

            if self.sort_by is not None:
                if self.sort_by not in whitelist:
                    allowed = sorted(list(whitelist.keys()))
                    raise ValueError(
                        f"sort_by field '{self.sort_by}' is not permissible for target '{target_str}'. Allowed fields: {allowed}"
                    )

        return self


class DynamicQueryResponse(BaseModel):
    """Response payload returning dynamically queried records."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    target: str = Field(..., description="Queried entity target")
    case_id: Optional[Union[uuid.UUID, str]] = Field(None, description="Investigation case UUID if scoped")
    total: int = Field(..., ge=0, description="Total matching records count")
    count: Optional[int] = Field(None, ge=0, description="Count of returned records in this slice")
    limit: int = Field(..., ge=1, description="Echoed limit")
    offset: int = Field(..., ge=0, description="Echoed offset")
    applied_filters: List[QueryFilter] = Field(default_factory=list, description="Filters applied to this query")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="Result records")
    execution_time_ms: Optional[float] = Field(None, ge=0.0, description="Query execution duration in milliseconds")

    @model_validator(mode="before")
    @classmethod
    def set_count_if_omitted(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "count" not in data or data["count"] is None:
                records = data.get("records", [])
                data["count"] = len(records)
        return data
