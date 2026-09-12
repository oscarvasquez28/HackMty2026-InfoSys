# Milestone 3 Specification Mining: Agent Tools API Contracts & Schemas

## 1. Executive Summary & Context

Milestone 3 of the Forensic Auditor Python Backend introduces the **Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents** (Requirement R3 in `ORIGINAL_REQUEST.md`).

The forensic platform processes large-scale banking transaction datasets (e.g. IBM AMLSim format), applies deterministic topological graph pruning (NetworkX), and persists case data and individual transaction records in remote TigerData PostgreSQL (or local SQLite in test environments).

To empower autonomous forensic AI agents (operating via external n8n workflows or local reasoning agents) to investigate suspicious activity, drill down into evidence, evaluate legal liability, and compose ad-hoc queries without altering backend database schemas or exposing the system to SQL injection, Milestone 3 defines:
1. **Four Dedicated Tool Endpoints**:
   - `POST /api/v1/tools/transactions`: Parameterized transaction filtering.
   - `POST /api/v1/tools/entities`: Node topological profiling (in/outflow, degree, net flow, risk scores).
   - `POST /api/v1/tools/patterns`: Cyclic layering and rapid pass-through mule network extraction.
   - `POST /api/v1/tools/legal-precedents`: Semantic vector similarity search against Mexican AML / CFF 69-B jurisprudence.
2. **Dynamic Composable Query Builder & Registry**:
   - `POST /api/v1/tools/query`: Composable query interface accepting structured filter criteria (`field`, `operator`, `value`), sorting, and pagination with strict column whitelisting and parameterized AST generation.
   - `ToolRegistry`: Extensible registry pattern mapping query targets to verified execution handlers.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Agent Tools - Transactions | `TransactionQueryRequest` & `POST /api/v1/tools/transactions` | Query and filter transaction rows scoped by `case_id` with origin/destination filtering, amount bounds, time windows, and suspicion flags. | `case_id` (UUID/str), `origin` (Optional[str]), `destination` (Optional[str]), `min_amount` (Optional[float]), `max_amount` (Optional[float]), `start_time` (Optional[datetime]), `end_time` (Optional[datetime]), `is_suspicious` (Optional[bool]), `limit` (int, 1-1000, def 50), `offset` (int, >=0, def 0) | `TransactionQueryResponse`: `case_id`, `total`, `limit`, `offset`, `total_volume_mxn`, `items` (list of `TransactionItem`) | 400 Bad Request if `min_amount > max_amount` or `start_time > end_time`; 404 Not Found if `case_id` does not exist; 422 for invalid types | ORIGINAL_REQUEST §R3, PROJECT.md #12 |
| 2 | Agent Tools - Entities | `EntityProfileRequest` & `POST /api/v1/tools/entities` | Profiles financial entities/nodes within a case, returning in/out degree, total inflow, total outflow, net flow, assigned risk score, risk reasons, and connected counterparties. | `case_id` (UUID/str), `entity_id` (Optional[str]), `min_risk_score` (Optional[float], 0.0-1.0), `is_suspicious` (Optional[bool]), `limit` (int, 1-500, def 50), `offset` (int, >=0, def 0) | `EntityProfileResponse`: `case_id`, `total_entities`, `entities` (list of `EntityProfileItem`) | 404 Not Found if `case_id` or explicit `entity_id` not found; 422 if `min_risk_score` not in [0.0, 1.0] | ORIGINAL_REQUEST §R3, PROJECT.md #13 |
| 3 | Agent Tools - Patterns | `PatternQueryRequest` & `POST /api/v1/tools/patterns` | Extracts detected topological patterns (elementary directed cycles and rapid pass-through mule accounts) stored in the case subgraph. | `case_id` (UUID/str), `pattern_type` ("all", "cycles", "passthrough_mules"), `min_cycle_length` (Optional[int], 2-10), `max_cycle_length` (Optional[int], 2-10), `min_volume` (Optional[float], >=0.0), `min_passthrough_ratio` (Optional[float], 0.0-1.0) | `PatternQueryResponse`: `case_id`, `pattern_type`, `total_cycles_count`, `total_mules_count`, `cycles` (list of `CyclePatternItem`), `passthrough_mules` (list of `PassthroughMuleItem`) | 400 Bad Request if `min_cycle_length > max_cycle_length`; 404 Not Found if `case_id` not found; 422 for invalid pattern type | ORIGINAL_REQUEST §R3, PROJECT.md #14 |
| 4 | Agent Tools - Legal Precedents | `LegalPrecedentQueryRequest` & `POST /api/v1/tools/legal-precedents` | Semantic vector search against Mexican AML statutes (CFF 69-B, NIF A-2, UIF ROI/ROR, CPF 400 Bis) using pgvector cosine distance (`<=>`) with keyword fallback. | `query_text` (str, len>=1), `query_vector` (Optional[List[float]], dim 1536), `top_k` (int, 1-20, def 3), `similarity_threshold` (Optional[float], -1.0 to 1.0, def 0.0), `law_name_filter` (Optional[str]) | `LegalPrecedentQueryResponse`: `query_text`, `top_k`, `total_matches`, `results` (list of `LegalPrecedentItem` with `article_code`, `law_name`, `content`, `similarity_score`, `distance`) | 400 Bad Request if `query_vector` dimension != 1536; 422 if empty query; returns empty results list if no match above threshold | ORIGINAL_REQUEST §R3, PROJECT.md #15 |
| 5 | Dynamic Query - Composable Endpoint | `DynamicQueryRequest` & `POST /api/v1/tools/query` | Arbitrary composable query engine across financial case datasets, accepting target entity, structured filter criteria, sorting, and pagination. | `case_id` (Optional[UUID/str], mandatory for case-scoped targets), `target` ("transactions", "nodes", "edges", "cycles", "passthrough_accounts", "legal_vectors"), `filters` (List[`QueryFilter`]), `sort_by` (Optional[str]), `sort_order` ("asc"\|"desc", def "asc"), `limit` (int, 1-1000, def 50), `offset` (int, >=0, def 0) | `DynamicQueryResponse`: `case_id`, `target`, `total`, `limit`, `offset`, `records` (List[Dict[str, Any]]), `applied_filters` (List[`QueryFilter`]), `execution_time_ms` (float) | 400 Bad Request if field is not whitelisted, if operator is unsupported, or if `case_id` is missing for case-scoped target; 404 Not Found if `case_id` absent from DB | ORIGINAL_REQUEST §R3, PROJECT.md #16 |
| 6 | Dynamic Query - Tool Registry | `ToolRegistry` handler pattern | Extensible handler registry mapping query targets to validated database query builders and in-memory evaluators with column whitelisting. | Internal registration via `ToolRegistry.register(target, handler)` and `execute_query(target, criteria, db)` | Dictionary containing total count, projected records, and filter execution metadata | Raises `ValueError` or `HTTPException(400)` on unwhitelisted field or target registration collision | ORIGINAL_REQUEST §R3, PROJECT.md §Interface Contracts |
| 7 | Dynamic Query - Filter Operators | Structured `QueryFilter` operators | Safe relational filter operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in`. | `field` (str), `operator` (`FilterOperator`), `value` (Union[str, int, float, bool, List[Any]]) | SQL binary expression / Python boolean filter predicate | 422 if operator invalid; 400 if value type incompatible with operator (e.g. `in` with non-list) | ORIGINAL_REQUEST §R3, PROJECT.md §Dynamic Composable Query Builder |
| 8 | Dynamic Query - Column Whitelisting | Security sanitization layer | Strict whitelist of accessible attributes per target to prevent SQL injection and unauthorized data leakage. | Candidate field name string | Validated field identifier mapped to ORM column or JSON attribute | 400 Bad Request ("Field 'xxx' is not permissible for target 'yyy'. Allowed fields: [...]") | PROJECT.md §Dynamic Composable Query Builder |
| 9 | Dual Engine Execution (DB & In-Memory) | Database & in-memory fallback | Allows agent tool queries to execute against both TigerData PostgreSQL (`AsyncSession`) and in-memory `INVESTIGATION_CASES` dictionary (offline / test mode). | `case_id`, criteria, `Optional[AsyncSession]` | Unified Pydantic response models | Seamless transparent execution regardless of database connectivity state | backend/api/routes/investigations.py |

---

## Edge Cases

| # | Feature | Input | Observed Behavior / Expected Specification |
|---|---------|-------|--------------------------------------------|
| 1 | `TransactionQueryRequest` | `min_amount = 50000.0`, `max_amount = 10000.0` | Pydantic `@model_validator` triggers validation error: `max_amount (10000.0) cannot be less than min_amount (50000.0)`. Emits HTTP 422/400. |
| 2 | `TransactionQueryRequest` | `start_time = 2026-09-12T12:00:00Z`, `end_time = 2026-09-10T12:00:00Z` | Pydantic `@model_validator` triggers validation error: `end_time must be greater than or equal to start_time`. |
| 3 | `TransactionQueryRequest` | `limit = 0` or `limit = 5000` | Field constraint `ge=1, le=1000` rejects value with HTTP 422 Unprocessable Entity. |
| 4 | `TransactionQueryRequest` | `case_id` not found in DB or memory | Route queries database; if `InvestigationCase` does not exist, raises HTTP 404 Not Found with message: `Investigation case '{case_id}' not found.` |
| 5 | `EntityProfileRequest` | Single `entity_id = "UNKNOWN_NODE"` | If `entity_id` is provided but does not exist in the case graph/transactions, returns HTTP 404 Not Found: `Entity '{entity_id}' not found in case '{case_id}'.` |
| 6 | `EntityProfileRequest` | `entity_id = None` (bulk profiling) | Evaluates all nodes in case. If `min_risk_score = 0.7`, returns only nodes having `risk_score >= 0.7`, sorted by `risk_score DESC`. |
| 7 | `EntityProfileItem` | Zero inflow and zero outflow (`total_in = 0.0, total_out = 0.0`) | `net_flow = 0.0`, `in_degree = 0, out_degree = 0`. Handled without division-by-zero errors. |
| 8 | `PatternQueryRequest` | `pattern_type = "cycles"`, `min_cycle_length = 5, max_cycle_length = 3` | Pydantic validator triggers: `max_cycle_length (3) cannot be less than min_cycle_length (5)`. |
| 9 | `PatternQueryRequest` | Case has 0 cycles and 0 mules | Returns HTTP 200 with empty arrays `cycles: []`, `passthrough_mules: []`, and counts `total_cycles_count: 0`, `total_mules_count: 0`. |
| 10 | `LegalPrecedentQueryRequest` | `query_vector` with length 512 (instead of 1536) | Pydantic `@field_validator('query_vector')` raises `ValueError: query_vector dimension must be exactly 1536, got 512`. |
| 11 | `LegalPrecedentQueryRequest` | `similarity_threshold = 0.99` (no match exceeds threshold) | Returns HTTP 200 with `total_matches = 0` and `results = []` without crashing. |
| 12 | `DynamicQueryRequest` | `target = "transactions"`, filter on unwhitelisted field `field = "password_hash"` or `field = "id; DROP TABLE transactions--"` | Whitelist validation fails immediately: `Field 'password_hash' is not permitted for target 'transactions'. Allowed: ['origin', 'destination', 'amount', 'timestamp', 'is_suspicious', 'reasons', 'id']`. Preempts SQL injection. |
| 13 | `DynamicQueryRequest` | `operator = "in"`, `value = "string_value"` (non-list) | Pydantic validator enforces that operator `"in"` or `"not_in"` must have an iterable list value. Raises validation error. |
| 14 | `DynamicQueryRequest` | `case_id = None` on case-scoped target (`"transactions"`, `"nodes"`, `"edges"`) | Model validator enforces: `case_id is required for target '{target}'`. Returns HTTP 400 Bad Request. |
| 15 | `DynamicQueryRequest` | Database offline / running in SQLite memory mode | Uses fallback evaluator: queries in-memory `INVESTIGATION_CASES` dictionary and runs Python-based filter matching, returning identical schema response. |

---

## 2. Pydantic v2 Schema Specification for `backend/schemas/agent_tools.py`

Below is the complete, self-contained schema specification designed for `backend/schemas/agent_tools.py`:

```python
"""
Pydantic v2 schemas for Agent Tools API endpoints, dynamic query interfaces,
and n8n forensic auditor tool contracts.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import math
from typing import Any, Dict, List, Literal, Optional, Union
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
    NODES = "nodes"
    EDGES = "edges"
    CYCLES = "cycles"
    PASSTHROUGH_ACCOUNTS = "passthrough_accounts"
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
    },
    TargetEntity.NODES.value: {
        "id": str,
        "entity_id": str,
        "total_in": float,
        "total_out": float,
        "in_degree": int,
        "out_degree": int,
        "risk_score": float,
        "is_suspicious": bool,
    },
    TargetEntity.EDGES.value: {
        "source": str,
        "target": str,
        "amount": float,
        "count": int,
    },
    TargetEntity.CYCLES.value: {
        "length": int,
        "estimated_volume": float,
    },
    TargetEntity.PASSTHROUGH_ACCOUNTS.value: {
        "account": str,
        "total_in": float,
        "total_out": float,
        "ratio": float,
        "time_delta_hours": float,
    },
    TargetEntity.LEGAL_VECTORS.value: {
        "id": str,
        "article_code": str,
        "law_name": str,
        "content": str,
    },
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
        if isinstance(v, Decimal):
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
            t_in = float(data.get("total_inflow", data.get("total_in", 0.0)))
            t_out = float(data.get("total_outflow", data.get("total_out", 0.0)))
            if "net_flow" not in data:
                data["net_flow"] = round(t_in - t_out, 2)
            reasons = data.get("reasons", [])
            if "is_suspicious" not in data:
                data["is_suspicious"] = bool(reasons or data.get("risk_score", 0.0) >= 0.5)
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

    account: str = Field(..., description="Mule account identifier")
    total_in: float = Field(..., ge=0.0, description="Total incoming volume in MXN")
    total_out: float = Field(..., ge=0.0, description="Total outgoing volume in MXN")
    ratio: float = Field(..., ge=0.0, le=1.0, description="Flow turnover ratio (min/max >= 0.90)")
    time_delta_hours: float = Field(..., ge=0.0, description="Elapsed hours between first inflow and last outflow")


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

    target: TargetEntity = Field(..., description="Data entity collection to query")
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
        # Case-scoped targets require case_id
        case_scoped = {
            TargetEntity.TRANSACTIONS,
            TargetEntity.NODES,
            TargetEntity.EDGES,
            TargetEntity.CYCLES,
            TargetEntity.PASSTHROUGH_ACCOUNTS,
        }
        if self.target in case_scoped and not self.case_id:
            raise ValueError(f"case_id is required when querying target '{self.target.value}'")

        # Whitelist field validation
        whitelist = TARGET_FIELD_WHITELISTS.get(self.target.value, {})
        for f in self.filters:
            if f.field not in whitelist:
                allowed = sorted(list(whitelist.keys()))
                raise ValueError(
                    f"Field '{f.field}' is not permissible for target '{self.target.value}'. Allowed fields: {allowed}"
                )

        if self.sort_by is not None:
            if self.sort_by not in whitelist:
                allowed = sorted(list(whitelist.keys()))
                raise ValueError(
                    f"sort_by field '{self.sort_by}' is not permissible for target '{self.target.value}'. Allowed fields: {allowed}"
                )

        return self


class DynamicQueryResponse(BaseModel):
    """Response payload returning dynamically queried records."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    target: str = Field(..., description="Queried entity target")
    case_id: Optional[Union[uuid.UUID, str]] = Field(None, description="Investigation case UUID if scoped")
    total: int = Field(..., ge=0, description="Total matching records count")
    limit: int = Field(..., ge=1, description="Echoed limit")
    offset: int = Field(..., ge=0, description="Echoed offset")
    applied_filters: List[QueryFilter] = Field(default_factory=list, description="Filters applied to this query")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="Result records")
    execution_time_ms: Optional[float] = Field(None, ge=0.0, description="Query execution duration in milliseconds")
```

---

## 3. Dynamic Tool Registry Architecture & Query Builder

The dynamic tool registry in `backend/api/routes/agent_tools.py` will implement a registry design pattern:

```python
class ToolRegistry:
    """
    Extensible query handler registry allowing registration of new agent tool queries
    without modifying database schema.
    Enforces column whitelisting, parameterized SQL generation, and mandatory case_id scoping.
    """
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, target: str, handler: Callable) -> None:
        """Registers a query handler for a target entity."""
        self._handlers[target] = handler

    async def execute_query(
        self,
        request: DynamicQueryRequest,
        db: Optional[AsyncSession] = None,
    ) -> DynamicQueryResponse:
        """Dispatches dynamic query to registered target handler with validation."""
        handler = self._handlers.get(request.target.value)
        if not handler:
            raise HTTPException(
                status_code=400,
                detail=f"No query handler registered for target '{request.target.value}'"
            )
        return await handler(request, db)
```

### Parameterized SQL Query Construction
For relational queries against `TransactionRecord`:
1. Base query: `stmt = select(TransactionRecord).where(TransactionRecord.case_id == case_uuid)`
2. For each filter in `request.filters`:
   - Obtain mapped column via `column = getattr(TransactionRecord, f.field)`
   - Map operator safely using SQLAlchemy binary expressions:
     - `FilterOperator.EQ`: `column == f.value`
     - `FilterOperator.NEQ`: `column != f.value`
     - `FilterOperator.GT`: `column > f.value`
     - `FilterOperator.GTE`: `column >= f.value`
     - `FilterOperator.LT`: `column < f.value`
     - `FilterOperator.LTE`: `column <= f.value`
     - `FilterOperator.LIKE`: `column.like(f"%{f.value}%")`
     - `FilterOperator.ILIKE`: `column.ilike(f"%{f.value}%")`
     - `FilterOperator.IN`: `column.in_(f.value)`
     - `FilterOperator.NOT_IN`: `column.not_in(f.value)`
   - Append to `.where()`
3. Sorting: `order_col = getattr(TransactionRecord, request.sort_by)` with `.asc()` or `.desc()`.
4. Pagination: `.offset(request.offset).limit(request.limit)`
5. Total count: `select(func.count()).select_from(...)`

### In-Memory / Subgraph Target Handling
For targets residing in `InvestigationCase.subgraph` or `InvestigationCase.patterns` (e.g. `nodes`, `cycles`, `passthrough_accounts`):
1. Extract the array from `case.subgraph["nodes"]` or `case.patterns["cycles"]`.
2. Apply Python predicates matching the filter operators.
3. Apply sorting and slicing (`[offset : offset + limit]`).
4. Return `DynamicQueryResponse`.

---

## 4. API Endpoints & Route Specifications

The agent tools router will be declared in `backend/api/routes/agent_tools.py` and included in `backend/main.py`:

```python
router = APIRouter(prefix="/tools", tags=["agent_tools"])
```

1. **`POST /api/v1/tools/transactions`**
   - Summary: Query transactions with case scoping and parameter filters.
   - Body: `TransactionQueryRequest`
   - Response: `200 OK` -> `TransactionQueryResponse`
   - Errors: `404 Not Found` (case missing), `400 Bad Request` (invalid bounds), `422 Unprocessable Entity`.

2. **`POST /api/v1/tools/entities`**
   - Summary: Profile financial entities (degrees, in/outflow, risk score).
   - Body: `EntityProfileRequest`
   - Response: `200 OK` -> `EntityProfileResponse`
   - Errors: `404 Not Found` (case or entity missing), `422 Unprocessable Entity`.

3. **`POST /api/v1/tools/patterns`**
   - Summary: Retrieve circular flow cycles and pass-through mule account metrics.
   - Body: `PatternQueryRequest`
   - Response: `200 OK` -> `PatternQueryResponse`
   - Errors: `404 Not Found` (case missing), `400 Bad Request` (invalid bounds), `422 Unprocessable Entity`.

4. **`POST /api/v1/tools/legal-precedents`**
   - Summary: Cosine vector similarity search against Mexican AML jurisprudence.
   - Body: `LegalPrecedentQueryRequest`
   - Response: `200 OK` -> `LegalPrecedentQueryResponse`
   - Errors: `400 Bad Request` (vector dimension mismatch), `422 Unprocessable Entity`.

5. **`POST /api/v1/tools/query`**
   - Summary: Dynamic composable query endpoint using `ToolRegistry`.
   - Body: `DynamicQueryRequest`
   - Response: `200 OK` -> `DynamicQueryResponse`
   - Errors: `400 Bad Request` (unwhitelisted field, missing case_id), `404 Not Found`, `422 Unprocessable Entity`.
