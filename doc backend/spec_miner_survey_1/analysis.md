# Forensic Auditor Backend Specification & Mining Analysis

## Executive Summary
This document provides the authoritative, exhaustive technical specification for the **Forensic Auditor Python Backend** project, mined from `ORIGINAL_REQUEST.md`, architectural documentation (`doc/architecture/README.md`), backend service specifications (`doc/backend/README.md`), compliance and data specifications (`doc/data-and-compliance/README.md`), system-wide docs (`doc/README.md`, `doc/index.md`), and the existing backend source code.

The backend is an asynchronous, high-throughput microservice built on **FastAPI**, **Polars**, **NetworkX**, and **SQLAlchemy 2.0**, designed to detect and explain complex Anti-Money Laundering (AML) topographies (such as smurfing, circular round-trips, and rapid pass-through mule conduits) across banking transaction datasets (IBM AMLSim format). It deterministically eliminates 85% to 98% of transactional noise before persisting cases and subgraphs to remote **TigerData PostgreSQL** with **pgvector**, streaming real-time forensic thought steps (via SSE) to an external **n8n** ReAct agent (or high-fidelity local simulation fallback), exposing an extensible Agent Tool query registry, and proxying speech synthesis through **ElevenLabs**.

---

## Authoritative Specification Sources Mined
1. `ORIGINAL_REQUEST.md`: System objectives, functional requirements R1–R5, and explicit acceptance criteria.
2. `doc/architecture/README.md`: Multi-service topology, sequence diagrams, 6-stage lifecycle, container orchestration, unified SSE schemas, n8n webhook payload, and ElevenLabs proxy contracts.
3. `doc/backend/README.md`: FastAPI routing architecture, Polars canonical alias resolution, NetworkX deterministic pruning algorithms, SQLAlchemy TigerData target models, and test suite specs.
4. `doc/data-and-compliance/README.md`: IBM AMLSim schema definitions, graph heuristic formulas, CFF Art. 69-B (EFOS/EDOS) legal framework, NIF A-2 operational materiality, UIF/GAFI reporting rules, and `legal_knowledge_vectors` pgvector HNSW schema.
5. `backend/`: Existing implementation files (`main.py`, `core/config.py`, `api/routes/investigations.py`, `api/routes/tts.py`, `services/ingestion.py`, `services/deterministic_filter.py`, `tests/test_pipeline.py`).
6. `data/sample_amlsim.csv`: Ground-truth benchmark dataset.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Database & Persistence | Async SQLAlchemy Engine with SSL | Connects to remote TigerData PostgreSQL instance using async engine, enforcing SSL (`sslmode=require`) and resilient connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`). | `DATABASE_URL` (e.g., `postgresql+psycopg://...` or `postgresql+asyncpg://...`) | Initialized `AsyncEngine` & `async_sessionmaker` | Raises descriptive connection exception if connection fails or credentials missing | `ORIGINAL_REQUEST.md` (R1), `doc/backend/README.md` (§4.1) |
| 2 | Database & Persistence | Database Session Dependency (`get_db`) | Asynchronous generator yielding transactional sessions; commits on successful exit, rolls back on uncaught exception, closes in `finally`. | None | `AsyncGenerator[AsyncSession, None]` | Triggers transaction rollback and re-raises exception | `ORIGINAL_REQUEST.md` (R1), `doc/backend/README.md` (§4.1) |
| 3 | Database & Persistence | `InvestigationCase` Model | Relational table `investigation_cases` storing case metadata, status, raw ingestion summary, metrics, isolated subgraph, detected patterns, and terminal verdict in JSONB columns. | UUID, filename, status, JSONB objects | Persisted case record with auto-generated UUID & timestamps | Database integrity constraint errors | `ORIGINAL_REQUEST.md` (R1), `doc/backend/README.md` (§4.1) |
| 4 | Database & Persistence | `TransactionRecord` Model | Relational table `transactions` storing granular transaction rows linked via foreign key to `investigation_cases`, indexed by origin, destination, and suspicion flag. | Case FK, origin, destination, amount, timestamp, is_suspicious, reasons JSONB | Persisted transaction records with auto-increment ID | Foreign key violation if case does not exist | `ORIGINAL_REQUEST.md` (R1), `doc/backend/README.md` (§4.1) |
| 5 | Database & Persistence | `LegalArticleVector` Model | Relational table `legal_knowledge_vectors` storing Mexican AML statutes, CFF articles, and 1536-dimensional embeddings with pgvector for semantic precedent search. | article_code, law_name/regulatory_body, content, Vector(1536) embedding | Persisted legal precedent records | Dimension mismatch or pgvector extension missing error | `ORIGINAL_REQUEST.md` (R1), `doc/data-and-compliance/README.md` (§5.4) |
| 6 | Database & Persistence | Database Lifecycle Hook | Automatically verifies database connectivity and initializes schema / extensions (`CREATE EXTENSION IF NOT EXISTS vector;`) during application startup lifespan. | Application startup event | Logged initialization confirmation | Graceful startup failure with clear diagnostics | `ORIGINAL_REQUEST.md` (R1), `backend/main.py` |
| 7 | Ingestion & Graph Analytics | Column Alias Resolution | Normalizes varied banking CSV headers (`origin`, `nameorig`, `destination`, `namedest`, `amount`, `monto`, `step`, `timestamp`) into canonical concepts. | List of CSV header strings, target concept | Canonical matched column name string | Raises `ValueError` if required concept is missing | `backend/services/ingestion.py`, `doc/backend/README.md` (§6.1) |
| 8 | Ingestion & Graph Analytics | Zero-Copy Polars Ingestion | Ingests CSV into in-memory Polars DataFrame, casts types, generates synthetic sequence timestamps if missing, and cleanses invalid/negative rows. | Raw CSV bytes / file stream | Cleaned `pl.DataFrame`, ingestion telemetry dict | Raises `ValueError` on empty file or zero valid rows | `backend/services/ingestion.py`, `doc/data-and-compliance/README.md` (§2) |
| 9 | Ingestion & Graph Analytics | Directed Graph Construction | Converts Polars DataFrame into a NetworkX `DiGraph` storing aggregated flow amounts, transaction counts, and occurrence timestamp vectors per edge and node. | Normalized Polars DataFrame | `nx.DiGraph` with node & edge attributes | Handled internally; returns empty graph if no records | `backend/services/deterministic_filter.py` (§3.1) |
| 10 | Ingestion & Graph Analytics | Closed Directed Cycle Detection | Identifies elementary circular flows representing smurfing and round-trip layering ($2 \le L \le \text{MAX\_CYCLE\_LENGTH}$, default 5). | `nx.DiGraph`, `max_cycle_length` (int) | List of cycles, set of cycle nodes, set of cycle edges | Catches exceptions if graph is hyper-complex | `backend/services/deterministic_filter.py`, `doc/data-and-compliance/README.md` (§3.2) |
| 11 | Ingestion & Graph Analytics | High-Velocity Pass-Through Mule Detection | Detects accounts with bidirectional turnover $\ge 90\%$ within a window $\le 48.0\text{ hours}$, tagging adjacent edges as `PASSTHROUGH_BRIDGE`. | `nx.DiGraph`, `ratio_threshold` (0.90), `window_hours` (48.0) | List of mule metadata dicts, set of mule nodes, set of bridge edges | Returns empty sets if no nodes match criteria | `backend/services/deterministic_filter.py`, `doc/data-and-compliance/README.md` (§3.3) |
| 12 | Ingestion & Graph Analytics | Deterministic Subgraph Pruning & Risk Scoring | Eliminates benign non-suspicious edges (85%–98% noise reduction); assigns composite risk scores: 0.80 (cycle only), 0.70 (mule only), 1.00 (both). | Cleaned Polars DataFrame | Dictionary containing `subgraph` (nodes, edges), `metrics`, `patterns` | Propagates data formatting errors | `backend/services/deterministic_filter.py`, `doc/data-and-compliance/README.md` (§3.5) |
| 13 | Investigation Lifecycle | Dataset Upload & Ingestion Endpoint | `POST /api/v1/investigations/upload`: validates CSV, parses via Polars, applies pruning, creates `InvestigationCase` and `TransactionRecord`s in PostgreSQL. | `multipart/form-data` with `file: UploadFile` | HTTP 201 Created with `case_id`, `message`, `metrics`, `subgraph`, `patterns` | HTTP 400 (non-CSV), HTTP 422 (cleansing error), HTTP 500 (internal error) | `ORIGINAL_REQUEST.md` (R2), `doc/architecture/README.md` (§4.1) |
| 14 | Investigation Lifecycle | Paginated Investigations Listing | `GET /api/v1/investigations`: lists historical cases with pagination (`limit`, `offset`), status filtering, creation timestamps, and summary metrics. | Query params: `limit: int = 20`, `offset: int = 0`, `status: Optional[str]` | JSON list of case summaries with pagination metadata | HTTP 422 on invalid query parameters | `ORIGINAL_REQUEST.md` (R2), `doc/backend/README.md` (§5) |
| 15 | Investigation Lifecycle | Case Detail Retrieval | `GET /api/v1/investigations/{case_id}`: retrieves stored investigation case from TigerData PostgreSQL including full metrics, subgraph, patterns, and verdict. | Path param: `case_id: UUID` | Full case record JSON payload | HTTP 404 Not Found if case does not exist in DB | `ORIGINAL_REQUEST.md` (R2), `doc/backend/README.md` (§5) |
| 16 | Investigation Lifecycle | Real-Time SSE Thought & Verdict Stream | `GET /api/v1/investigations/{case_id}/stream`: streams Server-Sent Events (`event: thought` steps 1..6, `event: verdict`), persists final verdict to PostgreSQL. | Path param: `case_id: UUID` | `text/event-stream` with chunked SSE lines | HTTP 404 if case not found; clean generator exit on client disconnect | `ORIGINAL_REQUEST.md` (R2), `doc/architecture/README.md` (§4.2) |
| 17 | External Integrations | External n8n Webhook Proxy | Dispatches case metrics and patterns to external n8n ReAct agent webhook (`N8N_WEBHOOK_URL`) via async HTTP client with timeout of 10.0s and streams response lines. | Webhook URL, case payload JSON | Streamed SSE event lines | Automatic fallback to local simulated reasoning on timeout/error | `ORIGINAL_REQUEST.md` (R2), `doc/architecture/README.md` (§4.3) |
| 18 | External Integrations | Simulated 6-Phase Forensic Reasoning Fallback | Generates realistic, step-by-step forensic reasoning thoughts when n8n is offline/unconfigured, followed by structured legal verdict. | Case metrics and patterns | 6 `thought` SSE events + 1 terminal `verdict` SSE event | No external dependencies; guaranteed success | `doc/backend/README.md` (§2, §4.2), `backend/api/routes/investigations.py` |
| 19 | Agent Tools Registry | Dedicated Transaction Tool Endpoint | `POST /api/v1/tools/transactions`: filters case transactions by case_id, origin, destination, min/max amounts, time window, and is_suspicious flag. | JSON filter criteria | List of matching `TransactionRecord` entities + total count | HTTP 404 if case missing; HTTP 422 if criteria invalid | `ORIGINAL_REQUEST.md` (R3) |
| 20 | Agent Tools Registry | Dedicated Entity Profile Tool Endpoint | `POST /api/v1/tools/entities`: profiles nodes for a case, returning in/out volume, in/out degrees, assigned risk scores, and suspicion reasons. | JSON: `case_id`, `account_id` (optional), `min_risk_score` | List of entity profiles with topological metrics | HTTP 404 if case missing; HTTP 422 if invalid | `ORIGINAL_REQUEST.md` (R3) |
| 21 | Agent Tools Registry | Dedicated Patterns Tool Endpoint | `POST /api/v1/tools/patterns`: retrieves detected elementary cycles and high-velocity pass-through accounts for an investigation case. | JSON: `case_id`, `pattern_type` (optional) | Structured pattern object containing cycles and passthrough lists | HTTP 404 if case missing; HTTP 422 if invalid | `ORIGINAL_REQUEST.md` (R3) |
| 22 | Agent Tools Registry | Dedicated Legal Precedents Vector Search | `POST /api/v1/tools/legal-precedents`: semantic similarity search against `legal_knowledge_vectors` using cosine similarity (`<=>`) for CFF 69-B, LFPIORPI, UIF. | JSON: `embedding` (1536 vector) or `query_text`, `top_k`, `regulatory_body` | Ranked list of legal precedents with cosine similarity scores | HTTP 422 on dimension mismatch or malformed query | `ORIGINAL_REQUEST.md` (R3), `doc/data-and-compliance/README.md` (§5.4) |
| 23 | Agent Tools Registry | Dynamic Composable Query Endpoint | `POST /api/v1/tools/query`: composable query builder accepting dynamic target, filters (field, operator, value), sort, and limit. | JSON: `target`, `filters`, `sort_by`, `sort_order`, `limit`, `offset` | Filtered result records matching query criteria | HTTP 400 for unknown targets; HTTP 422 for malformed operators | `ORIGINAL_REQUEST.md` (R3) |
| 24 | Agent Tools Registry | Extensible Tool Handler Registry Pattern | Dynamic in-code registry allowing developers to register new agent tool query targets and handlers with minimal configuration without altering DB schema. | Handler registration decorators/functions | Extensible mapping of target to query handler callable | Clean error response if handler raises exception | `ORIGINAL_REQUEST.md` (R3) |
| 25 | Speech Synthesis Proxy | ElevenLabs Streaming Audio Proxy | `POST /api/v1/tts/synthesize`: proxies text to ElevenLabs TTS API (`v1/text-to-speech/{voice_id}/stream`), streaming chunked `audio/mpeg` while shielding `ELEVENLABS_API_KEY`. | JSON: `text` (1-5000 chars), `voice_id` (optional), `model_id` (optional) | Streaming `audio/mpeg` chunked binary stream | HTTP 502 Bad Gateway if ElevenLabs API errors | `ORIGINAL_REQUEST.md` (R4), `backend/api/routes/tts.py` |
| 26 | Speech Synthesis Proxy | Silent MPEG Frame Fallback Generator | Emits valid minimal 320-byte MPEG-1 Layer 3 silent frames sequence when `ELEVENLABS_API_KEY` is absent or starts with `your_`, with header `X-Audio-Source: synthetic-fallback-mode`. | Synthesize request with unconfigured API key | Streaming `audio/mpeg` silent fallback frames | Never fails; ensures client audio element does not crash | `backend/api/routes/tts.py` (§24-30), `doc/architecture/README.md` (§4.4) |
| 27 | System Monitoring | Health Check Endpoint | `GET /health`: provides service status, project name, and active environment. | None | JSON: `{"status": "healthy", "project": "...", "environment": "..."}` | None (HTTP 200) | `backend/main.py` (§43-50), `ORIGINAL_REQUEST.md` |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Ingestion (`/upload`) | Non-CSV file uploaded (e.g. `test.pdf` or `test.xlsx`) | Request immediately rejected with HTTP 400 Bad Request: `"File must be a CSV dataset."`. |
| 2 | Ingestion (`/upload`) | 0-byte empty CSV file | Ingestion raises `ValueError: "The provided CSV dataset is empty."` which maps to HTTP 422 Unprocessable Entity. |
| 3 | Ingestion (`/upload`) | CSV missing mandatory column aliases (e.g. headers: `foo,bar,baz`) | `find_canonical_column` raises `ValueError: "Column matching required concept 'origin' was not found..."`, returning HTTP 422. |
| 4 | Ingestion (`/upload`) | CSV containing only non-positive amounts ($\le 0$) or null origins/destinations | Polars filter drops all rows; raises `ValueError: "No valid transaction rows found after cleansing."`, returning HTTP 422. |
| 5 | Ingestion (`/upload`) | CSV without `timestamp` column | Polars automatically synthesizes sequential steps using `pl.int_range(0, df.height, dtype=pl.Float64).alias("timestamp")`, allowing successful graph processing. |
| 6 | Deterministic Filter | Dense cyclic transaction graph with combinatorial cycle explosion | Simple cycle search is bounded by `MAX_CYCLE_LENGTH` (default 5) and skips deeper branches, preventing exponential algorithmic stalls. |
| 7 | Deterministic Filter | Temporal pass-through window with step values representing days instead of hours | If timestamps are in step units (days), the `PASS_THROUGH_WINDOW_HOURS` (48h) must match the time scale to avoid improper pruning. |
| 8 | Deterministic Filter | Legitimate payment aggregators (e.g., Stripe, MercadoPago) with $\ge 90\%$ turnover | Aggregators exhibit star-topology with high out-degree rather than closed cyclic loops; marked as pass-through unless whitelisted or filtered. |
| 9 | SSE Stream (`/stream`) | Investigation case ID not found in database | Endpoint raises HTTP 404 Not Found: `"Investigation case '{case_id}' not found."`. |
| 10 | SSE Stream (`/stream`) | Client disconnects or aborts EventSource mid-stream | Async generator catches cancellation and terminates cleanly without leaking background tasks or corrupting case status. |
| 11 | SSE Stream (`/stream`) | Reverse proxy (Nginx / ALB) buffers chunked HTTP response | Backend explicitly emits `X-Accel-Buffering: no` header to force immediate chunk flushing to the client. |
| 12 | n8n Webhook Integration | `N8N_WEBHOOK_URL` unreachable, returns non-200, or times out (> 10s) | Exception is cleanly caught; pipeline falls back smoothly to internal 6-phase simulated reasoning and verdict generation without interrupting user stream. |
| 13 | ElevenLabs TTS (`/synthesize`) | `ELEVENLABS_API_KEY` missing, empty, or placeholder (`your_...`) | Backend returns valid 320-byte MPEG-1 Layer 3 silent audio stream with header `X-Audio-Source: synthetic-fallback-mode`, preventing frontend `<audio>` errors. |
| 14 | ElevenLabs TTS (`/synthesize`) | ElevenLabs upstream API returns 401, 429, or 500 error | Backend reads error body and raises HTTP 502 Bad Gateway with diagnostic upstream error message. |
| 15 | Database Layer | TigerData PostgreSQL connection drops or times out | SQLAlchemy async engine with `pool_pre_ping=True` and `pool_recycle=3600` automatically detects stale sockets and reconnects. |
| 16 | Database Layer | Missing `pgvector` extension in PostgreSQL | Application startup lifecycle executes `CREATE EXTENSION IF NOT EXISTS vector;` or produces an explicit diagnostic error if permissions are lacking. |
| 17 | Legal Vector Search | Query embedding dimension differs from 1536 (e.g., 768 or 3072) | PostgreSQL/pgvector raises type mismatch error; backend must validate vector length before executing query. |
| 18 | Agent Dynamic Query (`/query`) | Invalid target entity or unknown field in filter | Dynamic query builder validates target against registered handlers, returning HTTP 400 Bad Request with allowed targets. |

---

## Technical Specifications Deep-Dive

### 1. Database Architecture & TigerData PostgreSQL Integration
- **Engine Configuration**:
  - Connection protocol: `postgresql+psycopg://` or `postgresql+asyncpg://`.
  - SSL Configuration: Enforced via `sslmode=require` in URL or `connect_args={"sslmode": "require"}`.
  - Connection Pool:
    - `pool_size = 20`
    - `max_overflow = 10`
    - `pool_pre_ping = True`
    - `pool_recycle = 3600`
    - `echo = settings.DEBUG`
- **Dependency**:
  - `get_db() -> AsyncGenerator[AsyncSession, None]`: Context-managed async session yielding transactional sessions with automatic rollback on exception.
- **Relational & Vector Schemas (`backend/models/forensic.py`)**:
  - `InvestigationCase` (`investigation_cases`):
    - `id`: `UUID(as_uuid=True)`, Primary Key, default `uuid.uuid4`.
    - `filename`: `String(255)`, `nullable=False`.
    - `status`: `String(50)`, default `"PROCESSED"`.
    - `created_at`: `DateTime(timezone=True)`, default `datetime.utcnow`.
    - `ingestion_metadata`: `JSONB`, `nullable=False`.
    - `metrics`: `JSONB`, `nullable=False`.
    - `subgraph`: `JSONB`, `nullable=False`.
    - `patterns`: `JSONB`, `nullable=False`.
    - `verdict`: `JSONB`, `nullable=True`.
    - `transactions`: 1-to-many relationship with `TransactionRecord` (`cascade="all, delete-orphan"`).
  - `TransactionRecord` (`transactions`):
    - `id`: `Integer`, Primary Key, autoincrement.
    - `case_id`: `UUID(as_uuid=True)`, `ForeignKey("investigation_cases.id", ondelete="CASCADE")`, indexed.
    - `origin`: `String(128)`, indexed, `nullable=False`.
    - `destination`: `String(128)`, indexed, `nullable=False`.
    - `amount`: `Float`, `nullable=False`.
    - `timestamp`: `Float`, `nullable=False`.
    - `is_suspicious`: `Boolean`, default `False`, indexed.
    - `reasons`: `JSONB`, default `list`.
  - `LegalArticleVector` (`legal_knowledge_vectors`):
    - `id`: `Integer` (or `UUID`), Primary Key.
    - `article_code`: `String(64)`, indexed, `nullable=False` (e.g. `"CFF-Art-69B"`).
    - `law_name`: `String(255)`, `nullable=False` (e.g. `"Código Fiscal de la Federación"`).
    - `content`: `Text`, `nullable=False`.
    - `embedding`: `Vector(1536)`, `nullable=False`.
    - Index: HNSW cosine index `idx_legal_vectors_hnsw` (`m = 16, ef_construction = 64`).

### 2. Mexican AML & Fiscal Jurisprudence Specifications
- **Artículo 69-B del CFF**:
  - Presumption of non-existence of operations based on absence of personnel, physical assets, operational infrastructure, or localized fiscal address.
  - **EFOS (*Empresas que Facturan Operaciones Simuladas*)**: Ghost companies issuing fake invoices (CFDI). In the graph, they act as cyclic hubs or structuring dispatchers.
  - **EDOS (*Empresas que Deducen Operaciones Simuladas*)**: Beneficiaries deducting false CFDIs to evade income tax (ISR) or recover VAT (IVA). In the graph, they are often originators of funds that cycle back through mule accounts.
  - Procedural deadlines: 15 business days (extendable by 10) for presuntos; 30 business days for EDOS regularization once definitive list is published.
- **Materialidad de Operaciones (NIF A-2 & SCJN Tesis 2a./J. 78/2019)**:
  - Economic substance must supersede formal contractual documentation.
  - Evidentiary Triad:
    1. Certified public contracts with verifiable timestamps (Fecha Cierta / NOM-151).
    2. Tangible deliverables (git commits, inspection reports, georeferenced logs, cartas porte).
    3. Continuous financial traceability without circular round-trips.
- **UIF & GAFI Framework**:
  - **Reporte de Operación Inusual (ROI)**: Mandatory filing within 24–48 hours upon detecting circular layering, structuring below $10,000 USD / $180,000 MXN, or rapid pass-through conduits.
  - **Reporte de Operación Relevante (ROR)**: Cash transactions exceeding $7,500 USD.
  - **Lista de Personas Bloqueadas (LPB)**: Immediate precautionary account freeze under Art. 115 LIC.
  - **FATF Recommendations**: Rec. 10 (Beneficiario Controlador/UBO) and Rec. 20 (Mandatory suspicious activity reporting without tipping off).

### 3. Graph Analytics & Pruning Math
- **Canonical Aliases**: `origin`, `destination`, `amount`, `timestamp` mapped via `COLUMN_ALIASES`.
- **Closed Directed Cycles**: Bounded elementary cycles $2 \le |C| \le 5$ via `nx.simple_cycles(G)`.
- **High-Velocity Mule Conduits**:
  $$\text{Ratio} = \frac{\min(\text{total\_in}, \text{total\_out})}{\max(\text{total\_in}, \text{total\_out})} \ge 0.90$$
  $$\Delta t = |\max(T_{\text{out}}) - \min(T_{\text{in}})| \le 48.0\text{ hours}$$
- **Pruning Noise Reduction Ratio**:
  $$\eta_{\text{prune}} = \left(\frac{|E_{\text{total}}| - |E_{\text{suspicious}}|}{|E_{\text{total}}|}\right) \times 100\% \in [85\%, 98\%]$$
- **Composite Risk Score**:
  $$\text{RiskScore}(v) = \min(1.0, \; 0.5 + 0.3 \cdot \mathbb{I}_{\text{cycle}}(v) + 0.2 \cdot \mathbb{I}_{\text{pt}}(v))$$

### 4. Scalable n8n Agent Tool Registry
- Versioned router: `backend/api/routes/agent_tools.py` registered under `/api/v1/tools`.
- Dynamic Tool Registry pattern:
  - Base registry class: `AgentToolRegistry` maintaining a dictionary of handlers.
  - Composable query execution: parses dynamic filters (operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `in`), translates safely to SQLAlchemy Core / ORM statements, applies pagination, and returns serializable dictionaries.
- Endpoints:
  1. `POST /api/v1/tools/transactions`: Filters case transactions by case, origin/destination, amount range, timestamps, and suspicion.
  2. `POST /api/v1/tools/entities`: Profiles nodes with in/out degree, volumes, risk scores, and suspicion reasons.
  3. `POST /api/v1/tools/patterns`: Returns detected cycles and pass-through mule accounts.
  4. `POST /api/v1/tools/legal-precedents`: Executes pgvector cosine distance search against Mexican legal knowledge base.
  5. `POST /api/v1/tools/query`: Composable query builder endpoint for dynamic criteria.

### 5. SSE Streaming & Verdict Lifecycle
- Endpoint: `GET /api/v1/investigations/{case_id}/stream`.
- Protocol: `text/event-stream` with headers `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`.
- Events:
  - `event: thought`: Sequential updates with `step` (1..6), `phase`, `message`, `timestamp`.
  - `event: verdict`: Concluding dictamen with `case_id`, `risk_level`, `fraud_type`, `total_amount_mxn`, `confidence_score`, `entities_involved`, `patterns_summary`, `legal_recommendation`, `audit_summary_text`, `completed_at`.
- State transition: Case record in PostgreSQL transitions from `status="PROCESSED"` to `status="STREAMING"` to `status="COMPLETED"`, persisting the full verdict in `verdict` JSONB.

### 6. ElevenLabs Voice Synthesis Proxy
- Endpoint: `POST /api/v1/tts/synthesize`.
- Upstream: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream`.
- Headers: `Accept: audio/mpeg`, `xi-api-key: {settings.ELEVENLABS_API_KEY}`.
- Offline Fallback: Valid 320-byte MPEG-1 Layer 3 silent frames sequence (repeated 10x) with header `X-Audio-Source: synthetic-fallback-mode`.
