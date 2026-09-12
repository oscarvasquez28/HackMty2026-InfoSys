# Technical Analysis: Milestone 3 Dedicated Tool Endpoints & Scalable Query Interface

**Agent**: `explorer_m3_1`  
**Milestone**: M3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents)  
**Date**: 2026-09-12  
**Target Module**: `backend/api/routes/agent_tools.py`, `backend/schemas/agent_tools.py`  

---

## Executive Summary

Milestone 3 implements the dedicated tool endpoints and dynamic query registry required by Requirement R3 of `ORIGINAL_REQUEST.md` and Milestone 3 of `PROJECT.md`. These endpoints allow external AI agents (e.g. n8n workflow nodes, LLM agent tool callers, forensic auditors) to inspect transaction graphs, query specific financial entities, inspect detected money laundering patterns (cycles and mule pass-throughs), and query Mexican AML jurisprudence precedents (CFF 69-B, NIF A-2, UIF ROI/ROR, LIC 115, CPF 400 Bis) via vector similarity search.

This analysis provides:
1. The formal Pydantic v2 schemas and REST contracts for all 4 dedicated endpoints plus the dynamic query builder.
2. The exact async SQLAlchemy 2.0 queries, column whitelisting, and pgvector cosine distance expressions.
3. The dual fallback architecture when `DATABASE_URL` is unconfigured or in offline demo mode (reading from `INVESTIGATION_CASES` and `SEED_LEGAL_PRECEDENTS`).
4. SQLite test compatibility mechanisms to prevent OperationalErrors when running in test environments with `sqlite+aiosqlite:///:memory:`.
5. The `ToolRegistry` pattern and dynamic composable query execution design.

---

## 1. System Architecture & Route Hierarchy

### 1.1 Endpoint Route Table

All endpoints reside in `backend/api/routes/agent_tools.py` with `router = APIRouter(prefix="/tools", tags=["agent-tools"])` and are registered in `backend/main.py` under `app.include_router(agent_tools_router, prefix=settings.API_V1_STR)`.

| Endpoint | Method | Purpose | Data Source (DB) | Fallback Source (Offline) |
|---|---|---|---|---|
| `/api/v1/tools/transactions` | `POST` | Filter transactions by case, origin/dest, amount, timestamp, suspicion flag | `transactions` table (`TransactionRecord`) | `INVESTIGATION_CASES[case_id]["transactions"]` / `subgraph["edges"]` |
| `/api/v1/tools/entities` | `POST` | Profile accounts (flow volumes, net flow, counterparty degrees, risk score, reasons) | `investigation_cases.subgraph["nodes"]` & `transactions` | `INVESTIGATION_CASES[case_id]["subgraph"]["nodes"]` |
| `/api/v1/tools/patterns` | `POST` | Retrieve circular flow cycles and rapid pass-through mule metrics | `investigation_cases.patterns` & `metrics` | `INVESTIGATION_CASES[case_id]["patterns"]` |
| `/api/v1/tools/legal-precedents` | `POST` | Vector similarity search (HNSW cosine) & keyword fallback against Mexican AML statutes | `legal_knowledge_vectors` (`LegalArticleVector`) | `backend.models.forensic.SEED_LEGAL_PRECEDENTS` |
| `/api/v1/tools/query` | `POST` | Composable dynamic query builder with column whitelisting and parameterized SQL | Registered target handlers via `ToolRegistry` | Target in-memory handlers |

---

## 2. Pydantic v2 Data Contracts (`backend/schemas/agent_tools.py`)

```python
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Union
import uuid
from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# 1. Transactions Tool Schemas
# -----------------------------------------------------------------------------
class TransactionFilterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_id: uuid.UUID = Field(..., description="UUID of the investigation case to scope transactions to")
    account: Optional[str] = Field(None, description="Account identifier appearing as origin OR destination")
    origin: Optional[str] = Field(None, description="Exact origin account ID")
    destination: Optional[str] = Field(None, description="Exact destination account ID")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum amount in MXN")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum amount in MXN")
    start_time: Optional[datetime] = Field(None, description="Earliest timestamp filter (UTC)")
    end_time: Optional[datetime] = Field(None, description="Latest timestamp filter (UTC)")
    is_suspicious: Optional[bool] = Field(None, description="Filter for suspicious transactions only")
    limit: int = Field(default=50, ge=1, le=500, description="Page limit (1-500)")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    sort_by: Literal["timestamp", "amount", "origin", "destination"] = Field(default="timestamp", description="Field to sort by")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Sort order")

class TransactionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    origin: str
    destination: str
    amount: float
    timestamp: datetime
    is_suspicious: bool
    reasons: List[str]

class TransactionFilterResponse(BaseModel):
    case_id: str
    total: int
    limit: int
    offset: int
    transactions: List[TransactionItem]


# -----------------------------------------------------------------------------
# 2. Entities Profiling Tool Schemas
# -----------------------------------------------------------------------------
class EntityProfileRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_id: uuid.UUID = Field(..., description="UUID of the investigation case")
    account_id: Optional[str] = Field(None, description="Specific account ID to profile")
    risk_tier: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]] = Field(None, description="Filter by risk tier")
    min_volume: Optional[float] = Field(None, ge=0.0, description="Minimum total transaction volume")
    limit: int = Field(default=50, ge=1, le=500, description="Limit for multi-entity profiles")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

class EntityProfileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    total_inflow: float
    total_outflow: float
    net_flow: float
    total_volume: float
    in_degree: int
    out_degree: int
    total_degree: int
    risk_score: float
    risk_tier: str
    risk_reasons: List[str]
    is_suspicious: bool

class EntityProfileResponse(BaseModel):
    case_id: str
    total: int
    limit: int
    offset: int
    entities: List[EntityProfileItem]


# -----------------------------------------------------------------------------
# 3. Patterns Tool Schemas
# -----------------------------------------------------------------------------
class PatternQueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_id: uuid.UUID = Field(..., description="UUID of the investigation case")
    pattern_type: Literal["all", "cycles", "passthrough"] = Field(default="all", description="Pattern filter")
    min_cycle_length: Optional[int] = Field(None, ge=2, description="Minimum cycle hops")
    max_cycle_length: Optional[int] = Field(None, ge=2, description="Maximum cycle hops")
    min_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum pass-through retention ratio")
    account: Optional[str] = Field(None, description="Filter patterns involving this account ID")

class CyclePatternItem(BaseModel):
    path: List[str]
    length: int
    estimated_volume: float

class PassthroughAccountItem(BaseModel):
    account: str
    total_in: float
    total_out: float
    ratio: float
    time_delta_hours: float

class PatternQueryResponse(BaseModel):
    case_id: str
    total_cycles: int
    total_passthrough_accounts: int
    cycles: List[CyclePatternItem]
    passthrough_accounts: List[PassthroughAccountItem]
    summary_metrics: Dict[str, Any]


# -----------------------------------------------------------------------------
# 4. Legal Precedents Tool Schemas
# -----------------------------------------------------------------------------
class LegalPrecedentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query_text: Optional[str] = Field(None, description="Natural language query or statute keywords")
    query_vector: Optional[List[float]] = Field(None, description="Pre-computed 1536-D embedding vector")
    top_k: int = Field(default=3, ge=1, le=20, description="Number of top precedents to return")
    article_code: Optional[str] = Field(None, description="Filter by exact article code (e.g. 'CFF-ART-69B')")
    law_name: Optional[str] = Field(None, description="Filter by law name or statute")

class LegalPrecedentItem(BaseModel):
    id: str
    article_code: str
    law_name: str
    content: str
    similarity_score: float
    distance: Optional[float] = None

class LegalPrecedentQueryResponse(BaseModel):
    query: Optional[str]
    total_results: int
    top_k: int
    precedents: List[LegalPrecedentItem]


# -----------------------------------------------------------------------------
# 5. Dynamic Query Builder Schemas
# -----------------------------------------------------------------------------
class FilterCriterion(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike", "in"]
    value: Any

class DynamicQueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target: Literal["transactions", "entities", "patterns", "cases", "legal_precedents"] = Field(..., description="Query entity target")
    case_id: Optional[uuid.UUID] = Field(None, description="Case UUID (mandatory for case-scoped targets)")
    filters: List[FilterCriterion] = Field(default_factory=list, description="List of filter criteria")
    sort_by: Optional[str] = Field(None, description="Column to sort by")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Sort order")
    limit: int = Field(default=50, ge=1, le=500, description="Items limit")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

class DynamicQueryResponse(BaseModel):
    target: str
    total: int
    limit: int
    offset: int
    items: List[Dict[str, Any]]
```

---

## 3. Detailed Endpoint Implementation Formulations

### 3.1 `POST /api/v1/tools/transactions`

#### Database Query Logic
1. **Case Verification**:
   ```python
   stmt_case = select(InvestigationCase.id).where(InvestigationCase.id == req.case_id)
   if (await db.execute(stmt_case)).scalar_one_or_none() is None:
       raise HTTPException(status_code=404, detail=f"Investigation case '{req.case_id}' not found.")
   ```
2. **Dynamic Filter Compilation**:
   ```python
   filters = [TransactionRecord.case_id == req.case_id]
   
   if req.account:
       filters.append(
           or_(
               TransactionRecord.origin == req.account,
               TransactionRecord.destination == req.account,
           )
       )
   if req.origin:
       filters.append(TransactionRecord.origin == req.origin)
   if req.destination:
       filters.append(TransactionRecord.destination == req.destination)
   if req.min_amount is not None:
       filters.append(TransactionRecord.amount >= req.min_amount)
   if req.max_amount is not None:
       filters.append(TransactionRecord.amount <= req.max_amount)
   if req.start_time is not None:
       filters.append(TransactionRecord.timestamp >= req.start_time)
   if req.end_time is not None:
       filters.append(TransactionRecord.timestamp <= req.end_time)
   if req.is_suspicious is not None:
       filters.append(TransactionRecord.is_suspicious == req.is_suspicious)
   ```
3. **Count & Pagination**:
   ```python
   count_stmt = select(func.count()).select_from(TransactionRecord).where(*filters)
   total = (await db.execute(count_stmt)).scalar() or 0
   
   sort_col = getattr(TransactionRecord, req.sort_by, TransactionRecord.timestamp)
   order_clause = sort_col.asc() if req.sort_order == "asc" else sort_col.desc()
   
   query_stmt = (
       select(TransactionRecord)
       .where(*filters)
       .order_by(order_clause)
       .offset(req.offset)
       .limit(req.limit)
   )
   records = (await db.execute(query_stmt)).scalars().all()
   ```

#### Offline Dual Fallback Logic
1. If `case_key not in INVESTIGATION_CASES`: raise HTTP 404.
2. If `case_dict.get("transactions")` is present, read transaction dictionaries directly.
3. If not present, extract from `case_dict.get("subgraph", {}).get("edges", [])` synthesizing transaction records:
   - `id`: synthetic UUID string
   - `origin`: `edge["source"]`
   - `destination`: `edge["target"]`
   - `amount`: `float(edge["amount"])`
   - `timestamp`: parsed using `parse_timestamp_to_datetime(edge.get("timestamps", [1.0])[0])`
   - `is_suspicious`: True
   - `reasons`: `edge.get("reasons", [])`
4. Apply filtering in Python:
   - `account`: `tx["origin"] == req.account or tx["destination"] == req.account`
   - `origin`: `tx["origin"] == req.origin`
   - `destination`: `tx["destination"] == req.destination`
   - `min_amount`: `tx["amount"] >= float(req.min_amount)`
   - `max_amount`: `tx["amount"] <= float(req.max_amount)`
   - `start_time`: `tx["timestamp"] >= req.start_time`
   - `end_time`: `tx["timestamp"] <= req.end_time`
   - `is_suspicious`: `bool(tx["is_suspicious"]) == req.is_suspicious`
5. Sort, slice `[req.offset : req.offset + req.limit]`, and return response.

---

### 3.2 `POST /api/v1/tools/entities`

#### Database Query Logic
1. **Case Verification & Subgraph Extraction**:
   ```python
   stmt = select(InvestigationCase).where(InvestigationCase.id == req.case_id)
   case_obj = (await db.execute(stmt)).scalar_one_or_none()
   if case_obj is None:
       raise HTTPException(status_code=404, detail=f"Investigation case '{req.case_id}' not found.")
   ```
2. **Topological Metrics Integration**:
   `subgraph_nodes = (case_obj.subgraph or {}).get("nodes", [])`
   Map nodes by `id`: `{n["id"]: n for n in subgraph_nodes}`.
3. **Single Entity Profiling**:
   If `req.account_id` is supplied:
   - If present in `nodes_map`:
     Extract `total_in`, `total_out`, `in_degree`, `out_degree`, `reasons`, `risk_score`.
     Compute:
     `net_flow = round(total_in - total_out, 2)`
     `total_volume = round(total_in + total_out, 2)`
     `total_degree = in_degree + out_degree`
     `risk_tier = classify_risk_tier(risk_score, reasons)`
   - If NOT in `nodes_map` (benign account that was pruned):
     Query `TransactionRecord` directly to calculate baseline transactional activity:
     ```python
     inflow_stmt = select(
         func.coalesce(func.sum(TransactionRecord.amount), 0),
         func.count(TransactionRecord.id)
     ).where(TransactionRecord.case_id == req.case_id, TransactionRecord.destination == req.account_id)
     
     outflow_stmt = select(
         func.coalesce(func.sum(TransactionRecord.amount), 0),
         func.count(TransactionRecord.id)
     ).where(TransactionRecord.case_id == req.case_id, TransactionRecord.origin == req.account_id)
     
     in_vol, in_cnt = (await db.execute(inflow_stmt)).one()
     out_vol, out_cnt = (await db.execute(outflow_stmt)).one()
     ```
     If `in_cnt == 0 and out_cnt == 0`: account does not exist in case; return empty list with total=0.
     Otherwise: return entity profile with `risk_score = 0.0`, `risk_tier = "LOW"`, `risk_reasons = []`, `is_suspicious = False`.
4. **Multi-Entity Profiling**:
   If `req.account_id` is None:
   Filter `subgraph_nodes` by `req.min_volume` and `req.risk_tier`.
   Sort by `risk_score desc, total_volume desc`.
   Apply `offset` and `limit`.

#### Offline Dual Fallback Logic
1. Look up `case_key = str(req.case_id)` in `INVESTIGATION_CASES`.
2. Extract `subgraph = case_dict.get("subgraph") or case_dict.get("filter_results", {}).get("subgraph", {})`.
3. Process `subgraph.get("nodes", [])` with identical business logic.

---

### 3.3 `POST /api/v1/tools/patterns`

#### Database Query Logic
1. **Case Verification**:
   Retrieve `case_obj` by `req.case_id`. If None, raise 404.
2. **Patterns & Metrics Extraction**:
   ```python
   patterns = case_obj.patterns or {}
   raw_cycles = patterns.get("cycles", [])
   raw_pt = patterns.get("passthrough_accounts", [])
   metrics = case_obj.metrics or {}
   ```
3. **Filtering**:
   - `cycles`:
     If `req.pattern_type in ("all", "cycles")`:
     - Filter `c["length"] >= req.min_cycle_length` (if specified)
     - Filter `c["length"] <= req.max_cycle_length` (if specified)
     - Filter `req.account in c.get("path", [])` (if specified)
     Else: `filtered_cycles = []`
   - `passthrough_accounts`:
     If `req.pattern_type in ("all", "passthrough")`:
     - Filter `pt.get("ratio", 0.0) >= req.min_ratio` (if specified)
     - Filter `pt.get("account") == req.account` (if specified)
     Else: `filtered_pt = []`
4. **Summary Metrics**:
   Return `metrics` containing `total_nodes_analyzed`, `suspicious_volume_mxn`, `detected_cycles_count`, `passthrough_accounts_count`, `pruning_efficiency_pct`.

#### Offline Dual Fallback Logic
1. Retrieve `case_dict` from `INVESTIGATION_CASES[case_key]`.
2. Extract `patterns = case_dict.get("patterns") or case_dict.get("filter_results", {}).get("patterns", {})`.
3. Apply the same filtering rules and return `PatternQueryResponse`.

---

### 3.4 `POST /api/v1/tools/legal-precedents`

#### Vector Embedding Strategy & Similarity Formula
1. **Embedding Acquisition**:
   - If `req.query_vector` is provided: validate length is 1536 (or Gemini dimension).
   - If `req.query_vector` is None and `req.query_text` is provided:
     Generate unit-normalized embedding using `generate_deterministic_embedding(req.query_text, dim=1536)`.
2. **PostgreSQL Native pgvector Cosine Distance Query**:
   ```python
   if db.bind and db.bind.dialect.name == "postgresql" and target_vector:
       distance_expr = LegalArticleVector.embedding.cosine_distance(target_vector)
       stmt = (
           select(
               LegalArticleVector,
               distance_expr.label("distance")
           )
           .order_by(distance_expr.asc())
           .limit(req.top_k)
       )
       if req.article_code:
           stmt = stmt.where(LegalArticleVector.article_code == req.article_code)
       if req.law_name:
           stmt = stmt.where(LegalArticleVector.law_name.ilike(f"%{req.law_name}%"))
       
       results = (await db.execute(stmt)).all()
       precedents = []
       for art, dist in results:
           distance_val = float(dist) if dist is not None else 0.0
           sim_score = max(0.0, min(1.0, round(1.0 - distance_val, 4)))
           precedents.append(
               LegalPrecedentItem(
                   id=str(art.id),
                   article_code=art.article_code,
                   law_name=art.law_name,
                   content=art.content,
                   similarity_score=sim_score,
                   distance=round(distance_val, 4),
               )
           )
   ```
3. **SQLite Test Environment Cosine Distance Compatibility**:
   When running under `sqlite+aiosqlite:///:memory:` (which stores vectors as TEXT and lacks pgvector `<=>` operator):
   ```python
   stmt = select(LegalArticleVector)
   if req.article_code:
       stmt = stmt.where(LegalArticleVector.article_code == req.article_code)
   if req.law_name:
       stmt = stmt.where(LegalArticleVector.law_name.ilike(f"%{req.law_name}%"))
   articles = (await db.execute(stmt)).scalars().all()
   
   scored_items = []
   for art in articles:
       emb = art.embedding
       if emb is None:
           emb = generate_deterministic_embedding(art.content)
       # Compute Euclidean unit-normalized dot product
       dot_prod = sum(a * b for a, b in zip(target_vector, emb))
       sim = max(0.0, min(1.0, float(dot_prod)))
       dist = 1.0 - sim
       scored_items.append((art, sim, dist))
   
   scored_items.sort(key=lambda x: x[1], reverse=True)
   top_items = scored_items[:req.top_k]
   ```
4. **Keyword Fallback (when neither vector nor text generates an embedding)**:
   ```python
   stmt = select(LegalArticleVector)
   if req.article_code:
       stmt = stmt.where(LegalArticleVector.article_code == req.article_code)
   if req.law_name:
       stmt = stmt.where(LegalArticleVector.law_name.ilike(f"%{req.law_name}%"))
   if req.query_text:
       tokens = [t.strip() for t in req.query_text.split() if len(t.strip()) > 2]
       conditions = [
           or_(
               LegalArticleVector.content.ilike(f"%{t}%"),
               LegalArticleVector.law_name.ilike(f"%{t}%"),
               LegalArticleVector.article_code.ilike(f"%{t}%"),
           )
           for t in tokens
       ]
       if conditions:
           stmt = stmt.where(or_(*conditions))
   stmt = stmt.limit(req.top_k)
   ```

#### Offline Dual Fallback Logic
1. Read from `backend.models.forensic.SEED_LEGAL_PRECEDENTS`.
2. Apply `article_code` and `law_name` filters.
3. If `target_vector` is computed:
   Calculate unit-norm dot product against each precedent's embedding (`generate_deterministic_embedding(p["content"])`).
   Sort descending by `similarity_score`.
4. Return top `top_k` items.

---

### 3.5 Dynamic Tool Registry & Query Builder (`POST /api/v1/tools/query`)

#### Security Requirements:
1. **Column Whitelisting**: Strict dictionary of permissible columns per target. Rejects any unlisted column with HTTP 400.
2. **Case Scoping**: Enforces `case_id` for case-specific targets (`transactions`, `entities`, `patterns`).
3. **Parameterized SQL Generation**: Compiles conditions via SQLAlchemy column expressions (`col == val`, `col.like(...)`), preventing raw SQL injection.

```python
WHITELISTS = {
    "transactions": {
        "id": TransactionRecord.id,
        "case_id": TransactionRecord.case_id,
        "origin": TransactionRecord.origin,
        "destination": TransactionRecord.destination,
        "amount": TransactionRecord.amount,
        "timestamp": TransactionRecord.timestamp,
        "is_suspicious": TransactionRecord.is_suspicious,
    },
    "cases": {
        "id": InvestigationCase.id,
        "filename": InvestigationCase.filename,
        "status": InvestigationCase.status,
        "created_at": InvestigationCase.created_at,
        "updated_at": InvestigationCase.updated_at,
    },
    "legal_precedents": {
        "id": LegalArticleVector.id,
        "article_code": LegalArticleVector.article_code,
        "law_name": LegalArticleVector.law_name,
        "content": LegalArticleVector.content,
    },
}
```

#### ToolRegistry Class Architecture:
```python
class ToolRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, target: str, handler: Callable):
        self._handlers[target] = handler

    async def execute_query(self, req: DynamicQueryRequest, db: Optional[AsyncSession]) -> DynamicQueryResponse:
        handler = self._handlers.get(req.target)
        if not handler:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target '{req.target}'. Available targets: {list(self._handlers.keys())}"
            )
        return await handler(req, db)

registry = ToolRegistry()
```

---

## 4. Test Strategy & Plan (`backend/tests/test_agent_tools.py`)

A comprehensive test suite covering:
1. **Transactions Tool**:
   - Filter by case_id only (returns all case transactions).
   - Filter by account (origin or destination matching).
   - Filter by min_amount and max_amount.
   - Filter by is_suspicious=True / False.
   - Pagination (limit & offset).
   - 404 on non-existent case_id.
   - In-memory offline fallback execution.
2. **Entities Tool**:
   - Single entity profiling (returns exact inflow, outflow, net flow, degrees, risk score).
   - Querying pruned/benign account not in suspicious subgraph (returns 0 risk score, LOW tier).
   - Multi-entity listing with risk_tier filter and min_volume filter.
   - In-memory offline fallback execution.
3. **Patterns Tool**:
   - Retrieve all patterns (cycles + passthrough mules).
   - Filter pattern_type='cycles' with min_cycle_length/max_cycle_length.
   - Filter pattern_type='passthrough' with min_ratio.
   - Filter patterns by specific account.
   - In-memory offline fallback execution.
4. **Legal Precedents Tool**:
   - Natural language semantic search (query_text="operaciones simuladas factureras EFOS EDOS").
   - Explicit query_vector matching.
   - Direct article_code query ("CFF-ART-69B").
   - Cosine similarity ranking and distance sanity checks.
   - In-memory offline fallback execution using SEED_LEGAL_PRECEDENTS.
5. **Dynamic Query Builder & Registry**:
   - Transactions target with `amount gt 100000` and `is_suspicious eq true`.
   - Security rejection: attempt to filter by unauthorized column triggers HTTP 400.
   - Missing mandatory `case_id` triggers HTTP 400.
6. **Zero-Regression Full Suite**:
   - Verify that all 35 existing tests in `test_investigations.py`, `test_database.py`, `test_challenge_m2_streaming.py`, and `test_pipeline.py` remain 100% passing.
