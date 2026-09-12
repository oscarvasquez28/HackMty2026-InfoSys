# Backend Architecture & Service Specification

[← Back to Master Documentation](../README.md) | [Agent Routing Index](../index.md)

---

## 1. Overview

The **Forensic Auditor AML Engine** backend is an asynchronous, high-performance microservice built on **FastAPI**. It is designed to detect, prune, and explain complex money laundering topographies (such as smurfing, circular layering, and rapid pass-through mule networks) across massive financial transaction datasets.

### Core Architectural Pillars
- **High-Throughput Columnar Ingestion**: Employs **Polars** (`polars.DataFrame`) for sub-second ingestion, alias normalization, and memory-efficient filtering of banking transaction datasets (including IBM AMLSim format).
- **Deterministic Graph Pruning**: Uses **NetworkX** (`networkx.DiGraph`) to execute mathematical pruning algorithms:
  - Directed cycle extraction (length 2 to $k$, default $k=5$) identifying circular layering and smurfing rings.
  - Temporal pass-through velocity detection (in/out ratio $\ge 90\%$ within a $\le 48\text{h}$ window) isolating mule accounts.
  - Noise reduction that prunes $80\%\text{--}99\%$ of legitimate volume, isolating the suspicious subgraph.
- **Real-Time Forensic Agent Reasoning (SSE)**: Streams turn-by-turn investigative thoughts and legal verdicts via Server-Sent Events (`text/event-stream`), natively integrating with an external **n8n** webhook orchestrator with built-in high-fidelity fallback simulation.
- **Shielded ElevenLabs Audio Proxy**: Direct audio streaming proxy for verdict narration via ElevenLabs API, featuring a synthetic silent MP3 generator fallback for zero-downtime offline demos.

```
+------------------------------------------------------------------------------------+
|                                FastAPI Application                                 |
|                                                                                    |
|  +---------------------------+             +------------------------------------+  |
|  |   /investigations/upload  |             |      /investigations/{id}/stream   |  |
|  |    - Polars Ingestion     |             |      - External n8n Webhook /      |  |
|  |    - NetworkX Pruning     |             |        SSE Thought Simulation      |  |
|  +-------------+-------------+             +-----------------+------------------+  |
|                |                                             |                     |
|                v                                             v                     |
|  +---------------------------+             +------------------------------------+  |
|  |     In-Memory / TigerData |             |          /tts/synthesize           |  |
|  |    PostgreSQL + pgvector  |             |      - ElevenLabs Stream Proxy /   |  |
|  |          Store            |             |        Fallback Silent MPEG Frame  |  |
|  +---------------------------+             +------------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

## 2. Architecture & Design

### Request Flow 1: Dataset Upload & Deterministic Pruning Pipeline

When a financial investigator uploads an AML transaction file (CSV), the ingestion and deterministic filter services execute synchronously to produce topological metrics and an isolated suspicious subgraph.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Forensic Investigator (Frontend)
    participant Route as api/routes/investigations.py
    participant Ingest as services/ingestion.py (Polars)
    participant Filter as services/deterministic_filter.py (NetworkX)
    participant Store as State Store (In-Memory / TigerData)

    Client->>Route: POST /api/v1/investigations/upload (multipart/form-data)
    Route->>Ingest: read_amlsim_csv(content)
    Note over Ingest: Canonical alias resolution<br/>Column casting & positive amount filter
    Ingest-->>Route: Cleaned Polars DataFrame + Ingestion Metadata
    Route->>Filter: apply_deterministic_filter(df)
    Note over Filter: 1. Build DiGraph with edge & node metadata<br/>2. Detect cycles (len <= MAX_CYCLE_LENGTH)<br/>3. Detect pass-through accounts (ratio >= 0.90, dt <= 48h)<br/>4. Prune legitimate edges & calculate metrics
    Filter-->>Route: Suspicious Subgraph, Metrics, Patterns
    Route->>Store: Persist Case Record (case_id, subgraph, metrics)
    Route-->>Client: 201 Created (case_id, metrics, subgraph, patterns)
```

### Request Flow 2: SSE Thought Streaming & Forensic Verdict

Once a case is created, the frontend connects to the streaming endpoint to receive live forensic agent reasoning steps and the concluding legal verdict.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend UI (EventSource)
    participant Route as api/routes/investigations.py
    participant N8N as External n8n Webhook (Optional)
    
    Client->>Route: GET /api/v1/investigations/{case_id}/stream
    Route->>Route: Fetch case_data from Store
    alt N8N_WEBHOOK_URL is configured & active
        Route->>N8N: POST {case_id, metrics, patterns}
        N8N-->>Route: SSE text/event-stream
        Route-->>Client: Proxy SSE events
    else Fallback or Simulation Mode
        loop Forensic Reasoning Steps (1 to 6)
            Note over Route: Ingestion Validation -> Topology Graph -><br/>Cycle Extraction -> Velocity Check -><br/>Deterministic Pruning -> Regulatory Assessment
            Route-->>Client: event: thought\ndata: {"step": i, "phase": "...", "message": "..."}\n\n
        end
        Note over Route: Calculate final risk score & GAFI/UIF verdict
        Route-->>Client: event: verdict\ndata: {"risk_level": "...", "fraud_type": "...", ...}\n\n
    end
    Route-->>Client: Close stream
```

### Request Flow 3: ElevenLabs Audio Synthesis Proxy

The speech synthesis route acts as a security gateway, preventing leakage of `ELEVENLABS_API_KEY` to client browsers while supporting offline demonstration resilience.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend Audio Player
    participant Route as api/routes/tts.py
    participant Eleven as ElevenLabs API

    Client->>Route: POST /api/v1/tts/synthesize ({"text": "..."})
    alt Valid ELEVENLABS_API_KEY exists
        Route->>Eleven: POST /v1/text-to-speech/{voice_id}/stream
        Eleven-->>Route: HTTP 200 chunked audio/mpeg
        Route-->>Client: StreamingResponse (audio/mpeg, verdict.mp3)
    else Missing or Placeholder API Key
        Note over Route: generate_fallback_silence_mp3()<br/>Emits valid minimal MPEG-1 Layer 3 frames
        Route-->>Client: StreamingResponse (audio/mpeg, X-Audio-Source: synthetic-fallback-mode)
    end
```

---

## 3. Key Components & File Breakdown

The backend codebase follows a clean, modular structure organized by concerns:

```
backend/
├── Dockerfile
├── requirements.txt
├── main.py
├── core/
│   ├── __init__.py
│   └── config.py
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── investigations.py
│       └── tts.py
├── services/
│   ├── __init__.py
│   ├── ingestion.py
│   └── deterministic_filter.py
└── tests/
    ├── __init__.py
    └── test_pipeline.py
```

### Component Responsibility Matrix

| File / Module | Responsibility | Key Symbols / Classes | External Dependencies |
| :--- | :--- | :--- | :--- |
| `backend/main.py` | Application entry point, lifespan management, CORS middleware configuration, route inclusion, `/health` endpoint. | `app`, `lifespan()`, `health_check()` | `fastapi`, `uvicorn` |
| `backend/core/config.py` | Pydantic v2 application configuration, environment parsing, CORS origin normalization, and deterministic algorithm thresholds. | `Settings`, `settings` | `pydantic`, `pydantic-settings` |
| `backend/api/routes/investigations.py` | HTTP controller for CSV upload, case storage, and SSE streaming generator proxying n8n or simulated reasoning. | `upload_investigation_dataset()`, `stream_investigation_thoughts()`, `generate_n8n_or_simulated_stream()`, `INVESTIGATION_CASES` | `fastapi`, `httpx`, `asyncio`, `uuid` |
| `backend/api/routes/tts.py` | Audio synthesis controller, ElevenLabs streaming proxy, and silent MPEG-1 Layer 3 fallback generator. | `SynthesizeRequest`, `synthesize_speech()`, `stream_elevenlabs_audio()`, `generate_fallback_silence_mp3()` | `fastapi`, `httpx`, `pydantic` |
| `backend/services/ingestion.py` | High-speed ingestion using Polars. Handles alias detection for IBM AMLSim datasets, column casting, sanitization, and dataset metrics. | `read_amlsim_csv()`, `find_canonical_column()`, `COLUMN_ALIASES` | `polars` |
| `backend/services/deterministic_filter.py` | Topological graph construction, directed cycle search, rapid pass-through node detection, and noise pruning. | `build_transaction_graph()`, `detect_closed_cycles()`, `detect_passthrough_accounts()`, `apply_deterministic_filter()` | `networkx`, `polars` |
| `backend/tests/test_pipeline.py` | Comprehensive async test suite validating health checks, CSV upload, deterministic metrics, SSE streaming, and TTS synthesis. | `test_complete_forensic_pipeline()`, `test_tts_synthesize_proxy()`, `SYNTHETIC_AML_CSV` | `pytest`, `pytest-asyncio`, `httpx` |
| `backend/Dockerfile` | Minimal Docker container definition based on `python:3.11-slim` with build dependencies. | Multi-stage container instructions | Docker |
| `backend/requirements.txt` | Explicit pinned and ranged dependencies for runtime and testing. | Dependencies list | pip |

---

## 4. External Integrations & Blueprint for Target Architecture

### 4.1 Database Architecture: Current State vs. TigerData Blueprint

#### Current In-Memory State
In the current implementation, investigation cases are persisted in a process-local Python dictionary:
```python
# backend/api/routes/investigations.py
INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}
```
*Limitations*: Data is lost on process restart; does not scale horizontally across multiple Uvicorn worker processes or container replicas.

#### Target TigerData Blueprint: SQLAlchemy Client & pgvector Design
The production architecture interfaces with the TigerData instance (backed by PostgreSQL 16 with the `pgvector` extension) defined in `docker-compose.yml`. Communication is conducted via the Python `sqlalchemy` package (version 2.0+).

```
+----------------------------------------------------------------------------------------------------+
|                                    SQLAlchemy Database Engine Layer                                |
|                                                                                                    |
|  Connection URI: postgresql+psycopg://forensic_user:forensic_password@postgres-pgvector:5432/...   |
|  Pool Settings: pool_size=20, max_overflow=10, pool_pre_ping=True, pool_recycle=3600               |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
        +----------------------------------+             +----------------------------------+
        |        Relational Tables         |             |      Vector Embeddings Table     |
        |  - investigation_cases (JSONB)   |             |  - legal_knowledge_vectors       |
        |  - transactions (Timescale/SQL)  |             |    (article_code, jurisdiction,  |
        |  - suspicious_entities           |             |     embedding: Vector(1536))      |
        +----------------------------------+             +----------------------------------+
```

#### Proposed Database Module: `backend/core/database.py`
```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.core.config import settings

# Async PostgreSQL connection string with psycopg or asyncpg
DATABASE_URL = (
    f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,       # Reconnects automatically on dropped connections
    pool_recycle=3600,        # Recycles connections older than 1 hour
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for transactional database session management."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

#### Proposed Target Models: `backend/models/forensic.py`
```python
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base

class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PROCESSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Store high-dimension metrics, graph topology, and patterns as structured JSONB
    ingestion_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    subgraph: Mapped[dict] = mapped_column(JSONB, nullable=False)
    patterns: Mapped[dict] = mapped_column(JSONB, nullable=False)
    verdict: Mapped[dict] = mapped_column(JSONB, nullable=True)

    transactions: Mapped[list["TransactionRecord"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    is_suspicious: Mapped[bool] = mapped_column(default=False, index=True)
    reasons: Mapped[dict] = mapped_column(JSONB, default=list)

    case: Mapped["InvestigationCase"] = relationship(back_populates="transactions")


class LegalArticleVector(Base):
    """Vector database table storing Mexican AML Law (LFPIORPI / UIF) articles for RAG retrieval."""
    __tablename__ = "legal_knowledge_vectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "LFPIORPI Art. 17 Fracc. IV"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 1536-dimensional vector embedding for cosine semantic similarity
    embedding: Mapped[Vector] = mapped_column(Vector(1536), nullable=False)
```

---

### 4.2 External n8n Webhook Integration

The route `GET /api/v1/investigations/{case_id}/stream` contains an SSE proxy mechanism that connects to `settings.N8N_WEBHOOK_URL` (configured via environment variable or default `http://n8n:5678/webhook/investigation-stream`):

1. **Payload Dispatch**:
   ```json
   {
     "case_id": "8f3b2591-628d-4b89-a720-d3d63b210a56",
     "metrics": {
       "total_nodes_analyzed": 14,
       "total_edges_analyzed": 28,
       "suspicious_nodes_count": 5,
       "detected_cycles_count": 1,
       "passthrough_accounts_count": 1,
       "pruned_edges_count": 22,
       "pruning_efficiency_pct": 78.57,
       "suspicious_volume_mxn": 985000.0
     },
     "patterns": {
       "cycles": [{"path": ["ACC_A", "ACC_B", "ACC_C", "ACC_A"], "length": 3, "estimated_volume": 443000.0}],
       "passthrough_accounts": [{"account": "MULE_01", "total_in": 500000.0, "total_out": 485000.0, "ratio": 0.97, "time_delta_hours": 12.0}]
     }
   }
   ```
2. **Streaming Response Parsing**:
   - The backend checks for `Content-Type: text/event-stream`.
   - Iterates lines asynchronously (`response.aiter_lines()`) and forwards them verbatim to the frontend client.
3. **Resilience & Fallback Mode**:
   - If `N8N_WEBHOOK_URL` is empty, times out (`timeout=10.0`), or returns a non-200 error, the route **catches the exception cleanly** and generates the 6 internal simulated forensic reasoning steps and final verdict. This guarantees that UI demonstrations and automated tests succeed without external dependencies.

---

### 4.3 ElevenLabs TTS Integration

The route `POST /api/v1/tts/synthesize` provides speech synthesis for the final forensic audit summary:

- **Upstream Endpoint**: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream`
- **Default Voice**: Rachel (`21m00Tcm4TlvDq8ikWAM`)
- **Default Model**: `eleven_multilingual_v2`
- **Streaming Output**: `audio/mpeg` delivered in real-time binary chunks.
- **Offline Safeguard**: When `ELEVENLABS_API_KEY` is not set or starts with `your_`, the service immediately streams a valid 320-byte MPEG-1 Layer 3 silent frame:
  ```python
  silent_mp3_frame = (
      b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
      b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
      * 10
  )
  ```
  This returns HTTP 200 with header `X-Audio-Source: synthetic-fallback-mode`, preventing frontend HTML5 `<audio>` elements from throwing decoder errors.

---

## 5. Public API Specifications

### 5.1 Ingest Dataset & Apply Filter
- **Method**: `POST`
- **Path**: `/api/v1/investigations/upload`
- **Content-Type**: `multipart/form-data`
- **Request Parameters**:
  - `file`: CSV file (required).
- **Validation Rules**:
  - Filename must end with `.csv`.
  - Must include columns mapping to origin, destination, amount, and optionally timestamp.
  - Amount must be strictly greater than zero.

#### Response: `201 Created`
```json
{
  "case_id": "4a71d87e-4081-4877-94a2-23c28c89b3f1",
  "message": "Dataset successfully processed and pruned.",
  "metrics": {
    "total_nodes_analyzed": 7,
    "suspicious_nodes_count": 5,
    "pruned_nodes_count": 2,
    "total_edges_analyzed": 7,
    "suspicious_edges_count": 5,
    "pruned_edges_count": 2,
    "suspicious_volume_mxn": 943000.0,
    "detected_cycles_count": 1,
    "passthrough_accounts_count": 1,
    "pruning_efficiency_pct": 28.57
  },
  "subgraph": {
    "nodes": [
      {
        "id": "ACC_A",
        "total_in": 145000.0,
        "total_out": 150000.0,
        "in_degree": 1,
        "out_degree": 1,
        "reasons": ["CIRCULAR_FLOW_CYCLE"],
        "risk_score": 0.8
      },
      {
        "id": "MULE_01",
        "total_in": 500000.0,
        "total_out": 485000.0,
        "in_degree": 1,
        "out_degree": 1,
        "reasons": ["HIGH_VELOCITY_PASSTHROUGH_90PCT"],
        "risk_score": 0.7
      }
    ],
    "edges": [
      {
        "source": "ACC_A",
        "target": "ACC_B",
        "amount": 150000.0,
        "count": 1,
        "timestamps": [1.0],
        "reasons": ["CYCLE_STEP"]
      }
    ]
  },
  "patterns": {
    "cycles": [
      {
        "path": ["ACC_A", "ACC_B", "ACC_C", "ACC_A"],
        "length": 3,
        "estimated_volume": 443000.0
      }
    ],
    "passthrough_accounts": [
      {
        "account": "MULE_01",
        "total_in": 500000.0,
        "total_out": 485000.0,
        "ratio": 0.97,
        "time_delta_hours": 12.0
      }
    ]
  }
}
```

---

### 5.2 Stream Investigation Thoughts (SSE)
- **Method**: `GET`
- **Path**: `/api/v1/investigations/{case_id}/stream`
- **Media-Type**: `text/event-stream`
- **Headers**:
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`

#### Event Formats:
1. **Thought Event (`event: thought`)**:
   ```text
   event: thought
   data: {"step": 3, "phase": "Extracción de Ciclos Dirigidos", "message": "Detección de patrones circulares: 1 ciclos cerrados detectados (evidencia de tipología de pitufeo / smurfing).", "timestamp": "2026-09-12T08:15:30.123456+00:00"}
   ```

2. **Verdict Event (`event: verdict`)**:
   ```text
   event: verdict
   data: {"case_id": "4a71d87e-4081-4877-94a2-23c28c89b3f1", "risk_level": "CRÍTICO", "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido", "total_amount_mxn": 943000.0, "confidence_score": 0.94, "entities_involved": ["ACC_A", "ACC_B", "ACC_C", "MULE_01", "OFFSHORE_OUT"], "pruned_leads_count": 2, "patterns_summary": {"closed_cycles": 1, "passthrough_accounts": 1, "pruning_efficiency_pct": 28.57}, "legal_recommendation": "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente.", "audit_summary_text": "Dictamen Pericial Forense para el caso 4a71d87e. Se identificó una red estructurada de lavado de dinero...", "completed_at": "2026-09-12T08:15:33.456789+00:00"}
   ```

---

### 5.3 Synthesize Speech Proxy (TTS)
- **Method**: `POST`
- **Path**: `/api/v1/tts/synthesize`
- **Content-Type**: `application/json`
- **Media-Type Response**: `audio/mpeg`
- **Request Body**:
  ```json
  {
    "text": "Dictamen pericial forense completado con éxito. Se identificó una red de lavado de dinero con nivel de riesgo CRÍTICO.",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "model_id": "eleven_multilingual_v2"
  }
  ```

---

### 5.4 Health Check
- **Method**: `GET`
- **Path**: `/health`
- **Response**: `200 OK`
  ```json
  {
    "status": "healthy",
    "project": "Forensic Auditor AML Engine",
    "environment": "development"
  }
  ```

---

## 6. Algorithmic Deep-Dive: Deterministic Pruning Engine

The deterministic filter is located in `backend/services/deterministic_filter.py`. It is engineered to mathematically strip benign transaction noise while preserving suspicious clusters.

### 6.1 Column Alias Resolution & Polars Ingestion
To handle varying banking formats without manual schema remodeling, `services/ingestion.py` maps column variations using alias lookup tables:
```python
COLUMN_ALIASES = {
    "origin": ["origin", "nameorig", "from_account", "source", "orig_account", "orig"],
    "destination": ["destination", "namedest", "to_account", "target", "dest_account", "dest"],
    "amount": ["amount", "value", "monto", "sum"],
    "timestamp": ["timestamp", "step", "time", "date", "datetime", "trans_time"],
}
```
If timestamps are absent, Polars generates an synthetic sequence step:
```python
select_exprs.append(pl.int_range(0, df.height, dtype=pl.Float64).alias("timestamp"))
```

### 6.2 Directed Cycle Search (`detect_closed_cycles`)
Identifies cyclical smurfing topologies where money leaves an origin and returns through intermediaries to obfuscate origin:
- Algorithm: Evaluates elementary directed cycles using `networkx.simple_cycles(G)`.
- Complexity Safeguard: Bounded by `max_cycle_length: int = settings.MAX_CYCLE_LENGTH` (default `5`).
- Paths longer than $k$ are ignored to prevent combinatorial explosion on dense graphs ($\mathcal{O}((V + E)(C + 1))$).

### 6.3 Temporal Pass-Through Mule Detection (`detect_passthrough_accounts`)
Identifies rapid layering accounts (mules or shell entities) based on retention ratio and velocity:
$$\text{Ratio} = \frac{\min(\text{total\_in}, \text{total\_out})}{\max(\text{total\_in}, \text{total\_out})} \ge 0.90$$
$$\Delta t = |\max(t_{\text{out}}) - \min(t_{\text{in}})| \le 48.0\text{ hours}$$
Accounts meeting these criteria have incoming and outgoing edges tagged with `PASSTHROUGH_BRIDGE`.

### 6.4 Graph Noise Reduction Ratio
Transactions not participating in detected cycles or pass-through bridges are pruned:
$$\text{Pruning Efficiency} = \left(\frac{E_{\text{total}} - E_{\text{suspicious}}}{E_{\text{total}}}\right) \times 100\%$$
On standard AMLSim datasets, this eliminates over $90\%$ of edges, allowing the forensic auditor LLM to concentrate only on the high-probability criminal core.

---

## 7. Testing & Quality Assurance

The backend includes an asynchronous integration test suite located at `backend/tests/test_pipeline.py`.

### Test Architecture
- Framework: **pytest** with **pytest-asyncio**.
- In-process HTTP client: **httpx** using `httpx.ASGITransport(app=app)`.
- Synthetic Test Dataset: `SYNTHETIC_AML_CSV` containing:
  - Circular triangle: `ACC_A` $\rightarrow$ `ACC_B` $\rightarrow$ `ACC_C` $\rightarrow$ `ACC_A`.
  - Pass-through mule: `CORP_INFLOW` $\rightarrow$ `MULE_01` $\rightarrow$ `OFFSHORE_OUT` ($97\%$ ratio within 12 hours).
  - Benign noise: Payroll transfer (`LEGIT_PAYROLL` $\rightarrow$ `EMPLOYEE_01`) and retail merchant payment (`STORE_MERCHANT` $\rightarrow$ `CONSUMER_99`).

### Running Tests
From the project root:
```bash
# Set PYTHONPATH to include project root
export PYTHONPATH=.
pytest backend/tests/test_pipeline.py -v
```

### Verification Points Covered
1. `/health` responds with HTTP 200 and `"status": "healthy"`.
2. `/api/v1/investigations/upload` successfully cleanses synthetic CSV, extracts $\ge 1$ cycle and $\ge 1$ pass-through account, and prunes at least 2 benign edges.
3. `/api/v1/investigations/{case_id}/stream` delivers at least 5 `thought` events and finishes with a valid `verdict` event containing risk levels, financial amounts, and legal recommendations.
4. `/api/v1/tts/synthesize` returns valid streaming `audio/mpeg` without exceptions.

---

## 8. Edge Cases, Performance & Gotchas

### 8.1 Cycle Explosion Safeguards in NetworkX
In dense or fully connected subgraphs, standard elementary cycle detection algorithms (Johnson's algorithm) can exhibit exponential time complexity $\mathcal{O}((V + E)(c + 1))$ where $c$ is the number of cycles.
- **Safeguard**: The backend strictly caps cycle length at `settings.MAX_CYCLE_LENGTH` (default 5).
- **Production Recommendation**: If scaling to graphs with $>100,000$ edges, compute weakly connected components first via `nx.weakly_connected_components(G)` and run cycle detection independently per component inside a thread/process pool.

### 8.2 Polars Memory Efficiency
Polars uses Apache Arrow memory layouts with zero-copy operations. However, constructing a NetworkX Python graph requires creating Python objects for nodes and edges:
- For files $> 500\text{ MB}$, avoid `df.to_dicts()`. Instead, extract native Polars series (`df["origin"].to_numpy()`, `df["destination"].to_numpy()`) to build graph edges directly, or stream edge batches to reduce memory consumption.

### 8.3 Server-Sent Events (SSE) Client Disconnection & Buffering
- **Proxy Buffering**: Reverse proxies (such as Nginx or AWS ALB) often buffer chunked HTTP responses by default, delaying real-time event delivery. The backend sets the `X-Accel-Buffering: no` header to ensure immediate streaming.
- **Client Cancellation**: In `investigations.py`, `asyncio.sleep()` is used between reasoning steps. If the client closes the connection, FastAPI handles the cancelled generator cleanly, aborting subsequent steps without leaking tasks.

### 8.4 CORS Configuration
When running the Next.js frontend on `http://localhost:3000` or production domains, CORS origins must be configured via the `BACKEND_CORS_ORIGINS` environment variable. `core/config.py` supports comma-separated strings (`"http://localhost:3000,http://app.domain.com"`) or JSON arrays (`'["http://localhost:3000"]'`).

---

## 9. Configuration Reference

All settings can be specified via environment variables or a `.env` file loaded in `backend/core/config.py`:

| Variable | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | string | `"Forensic Auditor AML Engine"` | API title in Swagger documentation |
| `API_V1_STR` | string | `"/api/v1"` | URL prefix for V1 endpoints |
| `ENVIRONMENT` | string | `"development"` | Environment indicator (`development`, `production`, `test`) |
| `DEBUG` | boolean | `True` | Enables debug logging and interactive API docs |
| `BACKEND_CORS_ORIGINS` | list / str | `["http://localhost:3000", ...]` | Allowed HTTP origins for CORS validation |
| `N8N_WEBHOOK_URL` | string | `""` | Optional external n8n orchestrator webhook URL |
| `ELEVENLABS_API_KEY` | string | `""` | ElevenLabs API token |
| `ELEVENLABS_VOICE_ID` | string | `"21m00Tcm4TlvDq8ikWAM"` | ElevenLabs voice ID (Rachel) |
| `ELEVENLABS_MODEL_ID` | string | `"eleven_multilingual_v2"` | ElevenLabs model ID |
| `MAX_CYCLE_LENGTH` | integer | `5` | Upper limit on path length for cycle detection |
| `PASS_THROUGH_RATIO_THRESHOLD` | float | `0.90` | Minimum turnover ratio for mule account detection |
| `PASS_THROUGH_WINDOW_HOURS` | float | `48.0` | Maximum time window in hours for pass-through analysis |
