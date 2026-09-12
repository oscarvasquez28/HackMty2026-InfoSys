# Specification Analysis: Milestone 2 — Investigation Persistence & Pagination Contracts

**Project**: Forensic Auditor Python Backend  
**Milestone**: M2 (Investigation Persistence & Pagination Contracts)  
**Author**: Spec Miner (`spec_miner_m2_1`)  
**Date**: 2026-09-12  

---

## Executive Summary

Milestone 2 bridges in-memory dataset analysis (Polars + NetworkX) with persistent TigerData PostgreSQL storage, enabling:
1. **Persistent Upload**: `POST /api/v1/investigations/upload` persisting both the `InvestigationCase` entity and all individual `TransactionRecord` rows with suspicion classification and timestamps.
2. **Paginated Historical Listing**: `GET /api/v1/investigations` supporting page-based pagination (`page`, `page_size`), case status filtering (`status`), total count, and summary metrics.
3. **Full Case Retrieval**: `GET /api/v1/investigations/{case_id}` returning complete topological metadata, metrics, isolated subgraph, patterns, and verdict.
4. **SSE Stream Case Hydration & Verdict Persistence**: `GET /api/v1/investigations/{case_id}/stream` querying case details from PostgreSQL, streaming SSE thoughts/verdicts, and saving the final verdict and `COMPLETED` status back into PostgreSQL.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Ingestion & Persistence | Multipart CSV Dataset Upload | Accepts AMLSim-formatted CSV, validates structure, runs Polars cleansing and NetworkX graph pruning | `file: UploadFile` (multipart/form-data) | `InvestigationUploadResponse` (HTTP 201) | HTTP 400 if filename not `.csv`; HTTP 422 if empty or missing required columns; HTTP 500 on unexpected exception | `ORIGINAL_REQUEST.md` R2, `doc/architecture/README.md` §4.1 |
| 2 | Ingestion & Persistence | InvestigationCase Relational Insertion | Creates and inserts an `investigation_cases` row with UUID PK, filename, status `PENDING`, metrics, subgraph, patterns, and timestamps | Parsed Polars dataframe, NetworkX filter output, filename | Persisted `InvestigationCase` in DB | Rolls back transaction and returns HTTP 500 if DB constraint or commit fails | `backend/models/forensic.py`, `PROJECT.md` §Interface Contracts |
| 3 | Ingestion & Persistence | Bulk TransactionRecord Persistence | Converts all cleaned transaction records to `TransactionRecord` rows, calculates `is_suspicious` from cycle/passthrough edges, maps timestamps to `datetime`, and bulk inserts linked to `case_id` | Cleaned transactions, suspicious edge sets, `case_id` | Persisted `transactions` rows in DB | Rolls back parent case and returns HTTP 500 on DB error | `ORIGINAL_REQUEST.md` R1/R2, `backend/models/forensic.py` |
| 4 | Pagination & Querying | Paginated Investigations Listing | Returns a paginated list of stored cases sorted chronologically (`created_at.desc()`), including total counts and summary metrics | Query params: `page: int = 1`, `page_size: int = 20`, `status: Optional[str] = None` | `InvestigationPaginationResponse` (HTTP 200) with `total`, `page`, `page_size`, `total_pages`, `items` | HTTP 422 if `page < 1` or `page_size < 1` or `page_size > 100` | `ORIGINAL_REQUEST.md` R2, User Request Prompt |
| 5 | Pagination & Querying | Investigation Case Status Filtering | Filters stored investigation cases by lifecycle state (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) in a case-insensitive manner | Query param: `status: Optional[str]` | Filtered subset of cases matching status | Returns empty list if status has no matches; HTTP 422 if status is validated against strict enum | `ORIGINAL_REQUEST.md` R2, `PROJECT.md` §Core Modules |
| 6 | Case Retrieval | Case Detail Retrieval by ID | Retrieves a single investigation case record including ingestion metadata, metrics, isolated subgraph, patterns, and verdict | Path param: `case_id: uuid.UUID` | `InvestigationDetailResponse` (HTTP 200) | HTTP 404 if case does not exist; HTTP 422 if `case_id` is not a valid UUID format | `ORIGINAL_REQUEST.md` R2, User Request Prompt |
| 7 | Streaming & Persistence | Database-Backed SSE Thought Stream | Hydrates case data from PostgreSQL, dispatches to n8n webhook (or local 6-phase simulation fallback), and streams SSE events | Path param: `case_id: uuid.UUID` | `StreamingResponse` (`text/event-stream`) with `thought` and `verdict` events | HTTP 404 if `case_id` does not exist in DB prior to stream init | `ORIGINAL_REQUEST.md` R2, `doc/architecture/README.md` §4.2 |
| 8 | Streaming & Persistence | Final Verdict Persistence | On stream completion, persists the generated verdict payload into `InvestigationCase.verdict` and updates `status = 'COMPLETED'` and `updated_at = func.now()` | Emitted verdict payload, `case_id`, `AsyncSession` | Updated `InvestigationCase` row in DB | Catches DB commit error, logs warning, stream still delivers verdict | `ORIGINAL_REQUEST.md` R2, `PROJECT.md` §Interface Contracts |
| 9 | Lifecycle & Cascading | Cascade Deletion Integrity | Foreign key constraint on `transactions.case_id` configured with `ondelete="CASCADE"`, ensuring removing a case purges its transactions | Deletion of `InvestigationCase` | All child transactions removed automatically | DB foreign key violation if constraint misconfigured | `backend/models/forensic.py` line 108 |
| 10 | Driver Compatibility | Dual-Dialect JSON/JSONB Handling | Uses `JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")` to ensure models execute seamlessly on TigerData PostgreSQL and in-memory SQLite for tests | Case & transaction schemas | Transparent JSON persistence across engines | Dialect compiler hook prevents SQLite test failures | `backend/models/forensic.py` line 47 |

---

## Edge Cases

| # | Feature | Input | Observed / Required Behavior |
|---|---------|-------|------------------------------|
| 1 | Upload Validation | Upload file with `.txt` or `.xlsx` extension | Returns `HTTP 400 Bad Request` with `{"detail": "File must be a CSV dataset."}` |
| 2 | Upload Validation | 0-byte empty file (`content = b""`) | Polars throws `NoDataError` or `df.is_empty()`; returns `HTTP 422 Unprocessable Entity` with `{"detail": "The provided CSV dataset is empty."}` |
| 3 | Upload Validation | CSV missing required column alias (e.g. no `amount` column) | `find_canonical_column` raises `ValueError`; caught and returned as `HTTP 422 Unprocessable Entity` with descriptive column names |
| 4 | Upload Validation | CSV containing only non-positive amounts (`amount <= 0`) | Polars filter yields empty DataFrame; returns `HTTP 422 Unprocessable Entity` with `{"detail": "No valid transaction rows found after cleansing."}` |
| 5 | Upload Persistence | High-volume dataset (10,000+ rows) | Bulk insert via batch chunks (e.g. 1,000 rows per chunk) or `session.add_all()` to prevent database parameter overflow in PostgreSQL/SQLite |
| 6 | Timestamp Normalization | Transaction timestamps provided as simulation step floats (`1.0`, `2.0`, `48.0`) | Normalized to `datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=ts)` to satisfy `DateTime(timezone=True)` column requirement |
| 7 | Timestamp Normalization | Transaction timestamps provided as Unix epoch seconds (`1672531200.0`) | Normalized via `datetime.fromtimestamp(ts, tz=timezone.utc)` |
| 8 | Pagination Bounds | `page = 0` or `page = -1` | FastAPI query parameter validation (`ge=1`) rejects request with `HTTP 422 Unprocessable Entity` |
| 9 | Pagination Bounds | `page_size = 0` or `page_size = 500` | FastAPI query parameter validation (`ge=1, le=100`) rejects request with `HTTP 422 Unprocessable Entity` |
| 10 | Pagination Bounds | `page = 999` with only 5 total records | Query executes cleanly with `offset=19960`; returns `HTTP 200 OK` with `total = 5`, `page = 999`, `total_pages = 1`, `items = []` |
| 11 | Pagination Status Filter | `status = "completed"` (lowercase) | Case-insensitive comparison (`func.upper(InvestigationCase.status) == "COMPLETED"`) correctly matches uppercase DB enum |
| 12 | Pagination Status Filter | `status = "UNKNOWN_STATUS"` | Returns `HTTP 200 OK` with `total = 0`, `total_pages = 0`, `items = []` |
| 13 | Case Detail by ID | Malformed UUID string (`GET /api/v1/investigations/not-a-uuid`) | FastAPI path parameter validation (`uuid.UUID`) rejects request with `HTTP 422 Unprocessable Entity` |
| 14 | Case Detail by ID | Non-existent UUID (`GET /api/v1/investigations/00000000-0000-0000-0000-000000000000`) | Query yields `None`; returns `HTTP 404 Not Found` with `{"detail": "Investigation case '00000000-0000-0000-0000-000000000000' not found."}` |
| 15 | SSE Thought Stream | Non-existent UUID for stream endpoint | Returns `HTTP 404 Not Found` immediately before establishing SSE connection |
| 16 | SSE Thought Stream | Repeated stream call on already `COMPLETED` case | Re-streams thoughts and delivers existing verdict without overwriting or erroring, maintaining idempotent behavior |
| 17 | SSE Thought Stream | Premature client disconnect mid-stream | FastAPI / Starlette cancellation handled gracefully; database connection is not leaked and existing case state remains consistent |

---

## Exact API Contracts & Pydantic Schemas

### 1. Route: `POST /api/v1/investigations/upload`

- **HTTP Method**: `POST`
- **Path**: `/api/v1/investigations/upload`
- **Content-Type**: `multipart/form-data`
- **Response Status**: `201 Created`
- **Response Model**: `InvestigationUploadResponse`

#### Request Parameter
```python
file: UploadFile = File(..., description="IBM AMLSim or compatible transaction CSV dataset")
```

#### Response JSON Schema
```json
{
  "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
  "filename": "amlsim_sample.csv",
  "status": "PENDING",
  "created_at": "2026-09-12T09:15:30.123456Z",
  "message": "Dataset successfully processed and pruned.",
  "metrics": {
    "total_nodes_analyzed": 14,
    "suspicious_nodes_count": 8,
    "pruned_nodes_count": 6,
    "total_edges_analyzed": 28,
    "suspicious_edges_count": 12,
    "pruned_edges_count": 16,
    "suspicious_volume_mxn": 1485000.0,
    "detected_cycles_count": 2,
    "passthrough_accounts_count": 3,
    "pruning_efficiency_pct": 57.14
  },
  "subgraph": {
    "nodes": [
      {
        "id": "ACC_B_102",
        "total_in": 750000.0,
        "total_out": 745000.0,
        "in_degree": 2,
        "out_degree": 2,
        "reasons": ["HIGH_VELOCITY_PASSTHROUGH_90PCT", "CIRCULAR_FLOW_CYCLE"],
        "risk_score": 0.95
      }
    ],
    "edges": [
      {
        "source": "ACC_A_101",
        "target": "ACC_B_102",
        "amount": 350000.0,
        "count": 1,
        "timestamps": [1672531200.0],
        "reasons": ["CYCLE_STEP", "PASSTHROUGH_BRIDGE"]
      }
    ]
  },
  "patterns": {
    "cycles": [
      {
        "path": ["ACC_A_101", "ACC_B_102", "ACC_C_103", "ACC_A_101"],
        "length": 3,
        "estimated_volume": 350000.0
      }
    ],
    "passthrough_accounts": [
      {
        "account": "ACC_B_102",
        "total_in": 750000.0,
        "total_out": 745000.0,
        "ratio": 0.993,
        "time_delta_hours": 14.5
      }
    ]
  }
}
```

---

### 2. Route: `GET /api/v1/investigations`

- **HTTP Method**: `GET`
- **Path**: `/api/v1/investigations`
- **Response Status**: `200 OK`
- **Response Model**: `InvestigationPaginationResponse`

#### Query Parameters
```python
page: int = Query(default=1, ge=1, description="Page number (1-indexed)")
page_size: int = Query(default=20, ge=1, le=100, description="Number of cases per page (1-100)")
status: Optional[str] = Query(default=None, description="Filter cases by status: PENDING, PROCESSING, COMPLETED, FAILED")
```

#### Response JSON Schema
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "items": [
    {
      "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
      "filename": "amlsim_sample.csv",
      "status": "COMPLETED",
      "created_at": "2026-09-12T09:15:30.123456Z",
      "updated_at": "2026-09-12T09:15:35.654321Z",
      "metrics": {
        "total_nodes_analyzed": 14,
        "suspicious_nodes_count": 8,
        "pruned_nodes_count": 6,
        "total_edges_analyzed": 28,
        "suspicious_edges_count": 12,
        "pruned_edges_count": 16,
        "suspicious_volume_mxn": 1485000.0,
        "detected_cycles_count": 2,
        "passthrough_accounts_count": 3,
        "pruning_efficiency_pct": 57.14
      },
      "has_verdict": true,
      "risk_level": "CRÍTICO"
    }
  ]
}
```

---

### 3. Route: `GET /api/v1/investigations/{case_id}`

- **HTTP Method**: `GET`
- **Path**: `/api/v1/investigations/{case_id}`
- **Response Status**: `200 OK`
- **Response Model**: `InvestigationDetailResponse`

#### Path Parameter
```python
case_id: uuid.UUID = Path(..., description="UUID of the investigation case to retrieve")
```

#### Response JSON Schema
```json
{
  "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
  "filename": "amlsim_sample.csv",
  "status": "COMPLETED",
  "created_at": "2026-09-12T09:15:30.123456Z",
  "updated_at": "2026-09-12T09:15:35.654321Z",
  "ingestion_metadata": {
    "total_records": 28,
    "total_volume": 1850000.0,
    "unique_accounts": 14,
    "original_columns": ["origin", "destination", "amount", "timestamp"]
  },
  "metrics": {
    "total_nodes_analyzed": 14,
    "suspicious_nodes_count": 8,
    "pruned_nodes_count": 6,
    "total_edges_analyzed": 28,
    "suspicious_edges_count": 12,
    "pruned_edges_count": 16,
    "suspicious_volume_mxn": 1485000.0,
    "detected_cycles_count": 2,
    "passthrough_accounts_count": 3,
    "pruning_efficiency_pct": 57.14
  },
  "subgraph": {
    "nodes": [
      {
        "id": "ACC_B_102",
        "total_in": 750000.0,
        "total_out": 745000.0,
        "in_degree": 2,
        "out_degree": 2,
        "reasons": ["HIGH_VELOCITY_PASSTHROUGH_90PCT", "CIRCULAR_FLOW_CYCLE"],
        "risk_score": 0.95
      }
    ],
    "edges": [
      {
        "source": "ACC_A_101",
        "target": "ACC_B_102",
        "amount": 350000.0,
        "count": 1,
        "timestamps": [1672531200.0],
        "reasons": ["CYCLE_STEP", "PASSTHROUGH_BRIDGE"]
      }
    ]
  },
  "patterns": {
    "cycles": [
      {
        "path": ["ACC_A_101", "ACC_B_102", "ACC_C_103", "ACC_A_101"],
        "length": 3,
        "estimated_volume": 350000.0
      }
    ],
    "passthrough_accounts": [
      {
        "account": "ACC_B_102",
        "total_in": 750000.0,
        "total_out": 745000.0,
        "ratio": 0.993,
        "time_delta_hours": 14.5
      }
    ]
  },
  "verdict": {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "risk_level": "CRÍTICO",
    "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido",
    "total_amount_mxn": 1485000.0,
    "confidence_score": 0.94,
    "entities_involved": ["ACC_A_101", "ACC_B_102", "ACC_C_103"],
    "pruned_leads_count": 16,
    "patterns_summary": {
      "closed_cycles": 2,
      "passthrough_accounts": 3,
      "pruning_efficiency_pct": 57.14
    },
    "legal_recommendation": "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente.",
    "audit_summary_text": "Dictamen Pericial Forense para el caso 8f3b204e...",
    "completed_at": "2026-09-12T09:15:35.654321Z"
  }
}
```

---

### 4. Route: `GET /api/v1/investigations/{case_id}/stream`

- **HTTP Method**: `GET`
- **Path**: `/api/v1/investigations/{case_id}/stream`
- **Response Media Type**: `text/event-stream`
- **Headers**:
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`
- **Database Action**:
  1. Verify case existence in DB (`select(InvestigationCase).where(InvestigationCase.id == case_id)`). If missing, return HTTP 404 immediately.
  2. Emit 6 SSE `thought` events.
  3. Emit 1 SSE `verdict` event.
  4. Update case in DB:
     ```python
     case.verdict = verdict_payload
     case.status = "COMPLETED"
     case.updated_at = datetime.now(timezone.utc)
     await db.commit()
     ```

---

## Recommended Pydantic Schema Specification (`backend/schemas/investigation.py`)

```python
"""
Pydantic v2 schemas for Investigation API endpoints, graph topology,
and persistent forensic analysis cases.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CaseStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# -----------------------------------------------------------------------------
# Graph & Topological Structures
# -----------------------------------------------------------------------------
class GraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique bank account identifier")
    total_in: float = Field(..., description="Total received funds in MXN")
    total_out: float = Field(..., description="Total dispersed funds in MXN")
    in_degree: int = Field(..., description="Incoming degree / number of incoming connections")
    out_degree: int = Field(..., description="Outgoing degree / number of outgoing connections")
    reasons: List[str] = Field(default_factory=list, description="Topological risk reasons")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Assigned risk score [0.0 - 1.0]")


class GraphEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(..., description="Origin account ID")
    target: str = Field(..., description="Destination account ID")
    amount: float = Field(..., description="Aggregated transfer volume in MXN")
    count: int = Field(default=1, description="Number of transfers between accounts")
    timestamps: List[float] = Field(default_factory=list, description="Observed timestamps or steps")
    reasons: List[str] = Field(default_factory=list, description="Suspicion justification flags")


class SubgraphData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nodes: List[GraphNode] = Field(..., description="Isolated suspicious graph nodes")
    edges: List[GraphEdge] = Field(..., description="Suspicious directed edges between nodes")


class InvestigationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_nodes_analyzed: int = Field(..., description="Total unique nodes in dataset")
    suspicious_nodes_count: int = Field(..., description="Count of suspicious nodes in isolated subgraph")
    pruned_nodes_count: int = Field(..., description="Count of benign nodes discarded")
    total_edges_analyzed: int = Field(..., description="Total transactions in raw dataset")
    suspicious_edges_count: int = Field(..., description="Count of suspicious edges retained")
    pruned_edges_count: int = Field(..., description="Count of benign edges discarded")
    suspicious_volume_mxn: float = Field(..., description="Total volume flagged as suspicious in MXN")
    detected_cycles_count: int = Field(..., description="Number of detected circular flow cycles")
    passthrough_accounts_count: int = Field(..., description="Number of rapid pass-through mule accounts")
    pruning_efficiency_pct: float = Field(..., description="Percentage of benign transactions pruned")


class CyclePattern(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: List[str] = Field(..., description="Closed cycle account sequence")
    length: int = Field(..., description="Cycle hop length")
    estimated_volume: float = Field(..., description="Estimated volume circulating in cycle")


class PassthroughAccountPattern(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account: str = Field(..., description="Mule account identifier")
    total_in: float = Field(..., description="Total incoming volume in MXN")
    total_out: float = Field(..., description="Total outgoing volume in MXN")
    ratio: float = Field(..., description="Pass-through ratio >= 0.90")
    time_delta_hours: float = Field(..., description="Window duration in hours between in and out")


class InvestigationPatterns(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cycles: List[CyclePattern] = Field(default_factory=list, description="Detected directed cycles")
    passthrough_accounts: List[PassthroughAccountPattern] = Field(
        default_factory=list, description="Detected mule accounts"
    )


# -----------------------------------------------------------------------------
# Verdict & Reasoning Models
# -----------------------------------------------------------------------------
class VerdictPatternsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    closed_cycles: int
    passthrough_accounts: int
    pruning_efficiency_pct: float


class VerdictPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID = Field(..., description="Case UUID")
    risk_level: str = Field(..., description="Risk tier: CRÍTICO, ALTO, MEDIO, BAJO")
    fraud_type: str = Field(..., description="Identified money laundering typology")
    total_amount_mxn: float = Field(..., description="Total flagged volume")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    entities_involved: List[str] = Field(..., description="Key suspicious account IDs")
    pruned_leads_count: int = Field(..., description="Count of discarded non-suspicious leads")
    patterns_summary: VerdictPatternsSummary
    legal_recommendation: str = Field(..., description="Legal and regulatory recommendation")
    audit_summary_text: str = Field(..., description="Narrative summary for forensic report")
    completed_at: datetime = Field(..., description="Verdict completion timestamp (UTC)")


class ThoughtEvent(BaseModel):
    step: int = Field(..., ge=1, le=6, description="Step sequence index")
    phase: str = Field(..., description="Investigation phase name")
    message: str = Field(..., description="Step reasoning observation")
    timestamp: datetime = Field(..., description="Timestamp of event emission")


# -----------------------------------------------------------------------------
# Endpoint Request & Response Schemas
# -----------------------------------------------------------------------------
class InvestigationUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID = Field(..., description="Newly allocated case UUID")
    filename: str = Field(..., description="Filename of uploaded dataset")
    status: CaseStatus = Field(default=CaseStatus.PENDING, description="Initial case status")
    created_at: datetime = Field(..., description="Creation timestamp")
    message: str = Field(default="Dataset successfully processed and pruned.", description="Status message")
    metrics: InvestigationMetrics = Field(..., description="Topological pruning metrics")
    subgraph: SubgraphData = Field(..., description="Suspicious graph topology")
    patterns: InvestigationPatterns = Field(..., description="Detected cycles and pass-through patterns")


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID = Field(..., description="Case identifier")
    filename: str = Field(..., description="Dataset filename")
    status: str = Field(..., description="Case status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    metrics: Optional[InvestigationMetrics] = Field(None, description="Topological metrics")
    has_verdict: bool = Field(default=False, description="True if verdict has been generated")
    risk_level: Optional[str] = Field(None, description="Risk level if verdict exists")


class InvestigationPaginationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int = Field(..., ge=0, description="Total matching cases in database")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")
    items: List[InvestigationSummary] = Field(..., description="Investigation summaries on this page")


class InvestigationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID = Field(..., description="Case identifier")
    filename: str = Field(..., description="Dataset filename")
    status: str = Field(..., description="Investigation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    ingestion_metadata: Dict[str, Any] = Field(..., description="Raw ingestion statistics")
    metrics: InvestigationMetrics = Field(..., description="Topological pruning metrics")
    subgraph: SubgraphData = Field(..., description="Isolated suspicious subgraph")
    patterns: InvestigationPatterns = Field(..., description="Detected patterns")
    verdict: Optional[VerdictPayload] = Field(None, description="Final forensic verdict if generated")
```

---

## Database Migration & Query Implementation Blueprint

### 1. Ingestion & Bulk Transaction Insertion
In `backend/api/routes/investigations.py`, replace in-memory dictionary `INVESTIGATION_CASES` with async SQLAlchemy transactions:

```python
case_id = uuid.uuid4()
now = datetime.now(timezone.utc)

# 1. Instantiate Case Record
case = InvestigationCase(
    id=case_id,
    filename=file.filename,
    status="PENDING",
    created_at=now,
    updated_at=now,
    ingestion_metadata=ingestion_meta,
    metrics=filter_results["metrics"],
    subgraph=filter_results["subgraph"],
    patterns=filter_results["patterns"],
    verdict=None,
)
db.add(case)

# 2. Extract and Map Transactions
# Map suspicious edges for fast O(1) suspicion lookup
suspicious_edges = {
    (e["source"], e["target"]): e.get("reasons", [])
    for e in filter_results["subgraph"]["edges"]
}

tx_records = []
for row in df.iter_rows(named=True):
    u = str(row["origin"])
    v = str(row["destination"])
    amount = Decimal(str(round(float(row["amount"]), 2)))
    raw_ts = float(row["timestamp"])
    
    # Normalize timestamp
    if raw_ts > 1e8:
        ts_dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
    else:
        ts_dt = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=raw_ts)
        
    is_susp = (u, v) in suspicious_edges
    reasons = suspicious_edges.get((u, v), [])
    
    tx = TransactionRecord(
        id=uuid.uuid4(),
        case_id=case_id,
        origin=u,
        destination=v,
        amount=amount,
        timestamp=ts_dt,
        is_suspicious=is_susp,
        reasons=reasons,
    )
    tx_records.append(tx)

# 3. Batch Add All Transactions
db.add_all(tx_records)
await db.commit()
```

### 2. Paginated List Query
```python
query = select(InvestigationCase)
count_query = select(func.count()).select_from(InvestigationCase)

if status:
    query = query.where(func.upper(InvestigationCase.status) == status.upper().strip())
    count_query = count_query.where(func.upper(InvestigationCase.status) == status.upper().strip())

# Total count
total_res = await db.execute(count_query)
total = total_res.scalar() or 0

# Order and paginate
offset = (page - 1) * page_size
query = query.order_by(InvestigationCase.created_at.desc()).offset(offset).limit(page_size)

res = await db.execute(query)
cases = res.scalars().all()
total_pages = math.ceil(total / page_size) if total > 0 else 0
```

### 3. Detail Retrieval
```python
stmt = select(InvestigationCase).where(InvestigationCase.id == case_id)
res = await db.execute(stmt)
case = res.scalar_one_or_none()

if case is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Investigation case '{case_id}' not found."
    )
```

### 4. SSE Stream Verdict Persistence
```python
# Update case in DB after streaming verdict
case.verdict = verdict_payload
case.status = "COMPLETED"
case.updated_at = datetime.now(timezone.utc)
await db.commit()
```

---

## Architectural Compatibility & Verification Matrix

| Component | Current State (M1) | Target State (M2) | Backward Compatibility |
|-----------|--------------------|-------------------|------------------------|
| `backend/models/forensic.py` | Complete ORM models (`InvestigationCase`, `TransactionRecord`, `LegalArticleVector`) | Reused as-is; zero schema changes needed | 100% compatible |
| `backend/core/database.py` | `get_db()`, `init_db()`, connection pooling, URL normalization | Reused via dependency injection `Depends(get_db)` | 100% compatible |
| `backend/schemas/investigation.py` | Not present | New file containing Pydantic v2 schemas | Pure addition, zero regression risk |
| `backend/api/routes/investigations.py` | In-memory `INVESTIGATION_CASES` dict, 2 endpoints (`/upload`, `/{id}/stream`) | Database-backed, 4 endpoints (`/upload`, `/`, `/{id}`, `/{id}/stream`) | Full compatibility with existing frontend contract |
| Frontend `useInvestigationStream` & `FileUpload` | Consumes `case_id`, `metrics`, `subgraph`, `patterns` | All response keys match existing TypeScript interfaces in `frontend/types/investigation.ts` | 100% compatible |
