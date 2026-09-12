# Forensic Auditor Python Backend — Comprehensive Architectural Analysis

**Survey Date**: 2026-09-12  
**Target Reference**: `ORIGINAL_REQUEST.md`, `doc/backend/README.md`, `doc/architecture/README.md`, `doc/data-and-compliance/README.md`  
**Investigator**: Explorer Agent (`explorer_survey_1`)  
**Status**: Read-only codebase investigation complete  

---

## 1. Executive Summary

An exhaustive inspection of the `backend/` directory in the repository reveals that while the **core ingestion and deterministic graph algorithms** (Polars + NetworkX) and **basic HTTP streaming/TTS proxy endpoints** are functional, the **TigerData PostgreSQL persistence layer**, **relational & vector models**, **investigation lifecycle persistence endpoints**, and **dynamic n8n agent tool interface** are **completely missing or stubbed with in-memory dictionaries**.

### Current Implementation Scorecard

| Module / Requirement | Target Location | Current Implementation Status | Gap Summary |
| :--- | :--- | :--- | :--- |
| **R1: TigerData DB & pgvector** | `backend/core/database.py`, `backend/models/forensic.py` | ❌ **NON-EXISTENT** | `backend/core/database.py` and `backend/models/` do not exist. No SQLAlchemy engine, no session lifecycle (`get_db`), no PostgreSQL connection string, no SSL enforcement, no pgvector integration. |
| **R1: Core Config & Settings** | `backend/core/config.py` | ⚠️ **PARTIAL** | Contains CORS, ElevenLabs, and graph thresholds, but lacks all database configuration (`DATABASE_URL`, `POSTGRES_*`, connection pool parameters, SSL settings). |
| **R1: Requirements** | `backend/requirements.txt` | ⚠️ **PARTIAL** | Missing `sqlalchemy>=2.0.0`, `asyncpg` or `psycopg`, `pgvector`, and async testing drivers like `aiosqlite`. |
| **R2: Ingestion & Upload Route** | `backend/api/routes/investigations.py` | ⚠️ **PARTIAL (IN-MEMORY ONLY)** | `POST /upload` executes Polars ingestion and NetworkX pruning, but stores case metadata in a process-local `INVESTIGATION_CASES` dictionary; does NOT persist cases or individual `TransactionRecord` rows to PostgreSQL. |
| **R2: Investigation Case List** | `backend/api/routes/investigations.py` | ❌ **NON-EXISTENT** | `GET /api/v1/investigations` (paginated case history) is not implemented. |
| **R2: Investigation Detail** | `backend/api/routes/investigations.py` | ❌ **NON-EXISTENT** | `GET /api/v1/investigations/{case_id}` is not implemented. |
| **R2: SSE Stream & Verdict** | `backend/api/routes/investigations.py` | ⚠️ **PARTIAL (IN-MEMORY ONLY)** | `GET /{case_id}/stream` streams 6 thought phases + verdict event, but reads from in-memory dict and does NOT update the verdict or status in the database on completion. |
| **R3: Dedicated n8n Agent Tools** | `backend/api/routes/agent_tools.py` | ❌ **NON-EXISTENT** | No tool endpoints exist for `/tools/transactions`, `/tools/entities`, `/tools/patterns`, or `/tools/legal-precedents`. |
| **R3: Dynamic Query Registry** | `backend/api/routes/agent_tools.py` | ❌ **NON-EXISTENT** | Dynamic `/tools/query` endpoint and extensible tool registry pattern are completely missing. |
| **R4: Speech Synthesis Proxy** | `backend/api/routes/tts.py` | ✅ **IMPLEMENTED (NEEDS HARDENING)** | Full streaming proxy to ElevenLabs API and synthetic silent MPEG frame fallback are present. Needs exception hardening for mid-stream failures and timeouts. |
| **R5: Verification & Tests** | `backend/tests/test_pipeline.py` | ⚠️ **MINIMAL COVERAGE (2 tests)** | Only tests health, upload, stream, and TTS using in-memory state. Zero tests for database connections, models, relational persistence, case listing/retrieval, or agent tools. |
| **App Entrypoint** | `backend/main.py` | ⚠️ **PARTIAL** | Lifespan does not manage DB engine startup/shutdown; `agent_tools` router is not imported or registered. |

---

## 2. Component-by-Component Codebase Audit

### 2.1 `backend/core/`

#### 2.1.1 `backend/core/config.py` (55 lines)
- **Observed Content**: Defines `Settings(BaseSettings)` with:
  - App metadata: `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`, `DEBUG`.
  - CORS: `BACKEND_CORS_ORIGINS` (validator normalizes comma-separated strings or JSON arrays).
  - Integrations: `N8N_WEBHOOK_URL`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`.
  - Graph thresholds: `MAX_CYCLE_LENGTH = 5`, `PASS_THROUGH_RATIO_THRESHOLD = 0.90`, `PASS_THROUGH_WINDOW_HOURS = 48.0`.
- **Gaps / Deficiencies**:
  - No `DATABASE_URL` setting.
  - No granular PostgreSQL connection variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_SSL_MODE`).
  - No pool configuration (`DB_POOL_SIZE = 20`, `DB_MAX_OVERFLOW = 10`, `DB_POOL_PRE_PING = True`, `DB_POOL_RECYCLE = 3600`).
  - No validation or helper method to assemble a clean `postgresql+asyncpg://` or `postgresql+psycopg://` URI with `sslmode=require`.

#### 2.1.2 `backend/core/database.py` (MISSING)
- **Current State**: File does not exist.
- **Required Implementation**:
  - Asynchronous engine instantiation (`create_async_engine`) using `settings.DATABASE_URL`.
  - SSL enforcement (`connect_args={"ssl": "require"}` for asyncpg, or `sslmode=require` in URI/psycopg).
  - Pool parameters: `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`.
  - `AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`.
  - `Base = declarative_base()` / `class Base(DeclarativeBase): pass` (SQLAlchemy 2.0 style).
  - FastAPI dependency generator `async def get_db() -> AsyncGenerator[AsyncSession, None]`.
  - Schema initialization helper (`init_db()`) to register `vector` extension and create tables safely on startup, with graceful degradation when `DATABASE_URL` is unconfigured.

---

### 2.2 `backend/models/` (MISSING DIRECTORY)

- **Current State**: The directory `backend/models/` does not exist.
- **Required Implementation (`backend/models/forensic.py`)**:
  Three primary SQLAlchemy 2.0 declarative entities:
  
  1. **`InvestigationCase`** (`investigation_cases` table):
     - `id`: `UUID(as_uuid=True)`, primary key, default `uuid.uuid4`.
     - `filename`: `String(255)`, non-nullable.
     - `status`: `String(50)`, default `"PROCESSED"`, index=True (e.g. `"PROCESSED"`, `"STREAMING"`, `"COMPLETED"`, `"FAILED"`).
     - `created_at`: `DateTime(timezone=True)`, default `datetime.utcnow`.
     - `completed_at`: `DateTime(timezone=True)`, nullable=True.
     - `ingestion_metadata`: `JSONB`, non-nullable (stores total records, volume, unique accounts, schema).
     - `metrics`: `JSONB`, non-nullable (stores topological stats, pruned edges, cycles count, mule count).
     - `subgraph`: `JSONB`, non-nullable (stores isolated nodes and edges).
     - `patterns`: `JSONB`, non-nullable (stores elementary cycles list and pass-through mule profiles).
     - `verdict`: `JSONB`, nullable=True (stores risk level, legal recommendation, audit summary).
     - `transactions`: 1-to-many relationship with `TransactionRecord`, cascade `"all, delete-orphan"`.

  2. **`TransactionRecord`** (`transactions` table):
     - `id`: `Integer`, primary key, autoincrement.
     - `case_id`: `UUID(as_uuid=True)`, foreign key to `investigation_cases.id` with `ondelete="CASCADE"`, index=True.
     - `origin`: `String(128)`, indexed, non-nullable (source account / CLABE / RFC).
     - `destination`: `String(128)`, indexed, non-nullable (target account / CLABE / RFC).
     - `amount`: `Float`, non-nullable, index=True.
     - `timestamp`: `Float`, non-nullable, index=True.
     - `is_suspicious`: `Boolean`, default `False`, indexed.
     - `reasons`: `JSONB`, default `list` (e.g. `["CYCLE_STEP"]`, `["PASSTHROUGH_BRIDGE"]`).
     - `case`: relationship back to `InvestigationCase`.

  3. **`LegalArticleVector`** (`legal_knowledge_vectors` table):
     - `id`: `Integer`, primary key, autoincrement (or UUID).
     - `article_code`: `String(64)`, indexed, non-nullable (e.g. `"CFF-Art-69B"`, `"LFPIORPI-Art-17"`).
     - `law_name`: `String(255)`, non-nullable (e.g. `"Código Fiscal de la Federación"`, `"Ley Antilavado"`).
     - `content`: `Text`, non-nullable.
     - `embedding`: `Vector(1536)` (pgvector type for cosine similarity search).
     - Index: HNSW index using `vector_cosine_ops`.

---

### 2.3 `backend/api/routes/investigations.py` (215 lines)

- **Observed Content**:
  - Line 17: `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}` (in-memory state store).
  - Lines 20–67: `POST /upload`
    - Accepts multipart CSV.
    - Calls `read_amlsim_csv(content)` and `apply_deterministic_filter(df)`.
    - Generates a UUID, stores into `INVESTIGATION_CASES[case_id]`.
    - Returns `{case_id, message, metrics, subgraph, patterns}` with HTTP 201.
  - Lines 69–190: `generate_n8n_or_simulated_stream()`
    - If `N8N_WEBHOOK_URL` is configured, posts `{case_id, metrics, patterns}` and proxies SSE response.
    - If unconfigured or failed, runs 6 simulated reasoning steps via `asyncio.sleep` emitting `event: thought`.
    - Yields terminal `event: verdict` payload.
  - Lines 192–215: `GET /{case_id}/stream`
    - Looks up `case_id` in `INVESTIGATION_CASES` (raises 404 if absent).
    - Returns `StreamingResponse(generate_n8n_or_simulated_stream(...), media_type="text/event-stream")`.
- **Gaps / Deficiencies**:
  - **No Database Persistence**: Ingestion results and transactions are never written to PostgreSQL.
  - **Missing `GET /api/v1/investigations`**: Cannot list past investigation cases or retrieve case history with pagination.
  - **Missing `GET /api/v1/investigations/{case_id}`**: Cannot retrieve case details, metrics, and subgraph by ID.
  - **No Stream Verdict Persistence**: When the SSE stream finishes emitting `verdict`, the verdict and `completed_at` are never saved back into the database.
  - **Single Point of Failure / Memory Leak**: Memory dictionary grows unbounded on every upload and is wiped on server reboot.

---

### 2.4 `backend/api/routes/agent_tools.py` (MISSING)

- **Current State**: File does not exist.
- **Required Implementation**:
  To fulfill **R3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents)**, this router must provide:

  1. **`POST /api/v1/tools/transactions`**:
     - Query parameters / request body:
       - `case_id: Optional[UUID]`
       - `account_id: Optional[str]` (matches either origin or destination)
       - `origin: Optional[str]`
       - `destination: Optional[str]`
       - `min_amount: Optional[float]`, `max_amount: Optional[float]`
       - `start_time: Optional[float]`, `end_time: Optional[float]`
       - `is_suspicious: Optional[bool]`
       - `limit: int = 50`, `offset: int = 0`
     - Returns filtered list of transactions with count and pagination metadata.

  2. **`POST /api/v1/tools/entities`**:
     - Request body:
       - `case_id: UUID`
       - `entity_ids: Optional[List[str]]` (specific node IDs to inspect)
       - `min_risk_score: Optional[float]`
     - Extracts entity profiles directly from the case subgraph or aggregated transactions:
       - Inflow volume, outflow volume, net delta.
       - In-degree, out-degree, counterparty account list.
       - Assigned risk score and risk reasons (`CIRCULAR_FLOW_CYCLE`, `HIGH_VELOCITY_PASSTHROUGH_90PCT`).

  3. **`POST /api/v1/tools/patterns`**:
     - Request body: `case_id: UUID`, `pattern_type: Optional[str]` (`"cycles"`, `"passthrough"`, `"all"`).
     - Returns:
       - Detected elementary cycles: path nodes, cycle length, estimated volume.
       - Pass-through mule accounts: turnover ratio, time delta in hours, inflow vs outflow.

  4. **`POST /api/v1/tools/legal-precedents`**:
     - Request body:
       - `query: str` (free text query, e.g. "cuentas puente sin infraestructura materialidad 69-B")
       - `embedding: Optional[List[float]]` (optional pre-computed embedding vector)
       - `limit: int = 5`
       - `regulatory_body: Optional[str]` (e.g. `"SAT"`, `"UIF"`, `"GAFI"`)
     - Executes vector similarity (cosine distance `<=>`) against `legal_knowledge_vectors`.
     - Supports fallback to text keyword / ilike matching if vector extensions or embeddings are unavailable during testing.

  5. **`POST /api/v1/tools/query` (Dynamic Tool Registry & Query Builder)**:
     - Request body:
       - `target: str` (`"transactions"`, `"cases"`, `"entities"`, `"legal_precedents"`)
       - `filters: List[FilterCriterion]` where criterion has `field`, `operator` (`"eq"`, `"neq"`, `"gt"`, `"gte"`, `"lt"`, `"lte"`, `"like"`, `"ilike"`, `"in"`), `value`
       - `sort_by: Optional[str]`, `sort_order: Optional[str] = "asc"`
       - `limit: int = 50`, `offset: int = 0`
     - Uses an extensible handler registry:
       ```python
       class ToolRegistry:
           handlers: Dict[str, Callable]
           def register(name: str, handler: Callable): ...
           async def execute(target: str, query_spec: QuerySpec, db: AsyncSession): ...
       ```
     - Safely builds SQLAlchemy criteria using column mappings to prevent SQL injection.

---

### 2.5 `backend/api/routes/tts.py` (106 lines)

- **Observed Content**:
  - Lines 13–17: `SynthesizeRequest` (text 1–5000 chars, optional voice_id, model_id).
  - Lines 19–30: `generate_fallback_silence_mp3()` produces 320-byte valid MPEG-1 Layer 3 frames repeated 10 times.
  - Lines 33–65: `stream_elevenlabs_audio()` streams bytes from ElevenLabs API using `httpx.AsyncClient`.
  - Lines 67–106: `synthesize_speech()`:
    - Checks if `ELEVENLABS_API_KEY` is missing or placeholder (`your_...`); if so, emits silent MP3 fallback with header `X-Audio-Source: synthetic-fallback-mode`.
    - Otherwise, streams from upstream.
- **Hardening Needs**:
  - Better client connection close handling (`CancelledError`).
  - Timeout handling: ElevenLabs API can hang during network latency; `httpx.TimeoutException` should gracefully fall back to synthetic silence rather than failing with a 502 error during live demonstrations.
  - Header preservation and audio length metadata validation.

---

### 2.6 `backend/services/`

#### 2.6.1 `backend/services/ingestion.py` (103 lines)
- **Observed Content**:
  - `COLUMN_ALIASES`: maps variations of `origin`, `destination`, `amount`, `timestamp`.
  - `read_amlsim_csv()`: loads via `polars.read_csv`, handles synthetic timestamp step fallback, validates positive amounts, returns `cleaned_df` and `metadata`.
- **Integrity Assessment**: Highly efficient, robust zero-copy Polars ingestion. Tested and functional.
- **Persistence Integration Hook**: The resulting `cleaned_df` can be transformed into `TransactionRecord` model instances via `.iter_rows(named=True)` or batch mapping.

#### 2.6.2 `backend/services/deterministic_filter.py` (260 lines)
- **Observed Content**:
  - `build_transaction_graph(df)`: constructs `nx.DiGraph` with node attributes (`total_in`, `total_out`, timestamps) and edge attributes (`amount`, `count`, `timestamps`).
  - `detect_closed_cycles(G, max_cycle_length)`: bounded cycle search using `nx.simple_cycles(G)`.
  - `detect_passthrough_accounts(G, ratio_threshold, window_hours)`: checks turnover ratio $\ge 0.90$ within $\le 48.0$ hours.
  - `apply_deterministic_filter()`: unions suspicious nodes/edges, calculates pruning statistics, returns structured dict with `subgraph`, `metrics`, and `patterns`.
- **Integrity Assessment**: Implements sound graph-theoretic pruning. The returned `subgraph` and `patterns` are structured JSON that map 1:1 to the `JSONB` columns in `InvestigationCase`.

---

### 2.7 `backend/tests/` (100 lines)

- **Observed Content (`backend/tests/test_pipeline.py`)**:
  - `SYNTHETIC_AML_CSV`: 7 transactions containing 1 triangle cycle, 1 pass-through mule, 2 noise transactions.
  - `test_complete_forensic_pipeline`: tests `/health`, `POST /upload`, and `GET /stream` (in-memory).
  - `test_tts_synthesize_proxy`: tests `POST /tts/synthesize` (fallback silent MP3).
- **Gaps / Deficiencies**:
  - Zero tests for database session initialization, engine creation, or SSL settings.
  - Zero tests for model schemas (`InvestigationCase`, `TransactionRecord`, `LegalArticleVector`).
  - Zero tests for relational persistence after upload.
  - Zero tests for `GET /api/v1/investigations` or `GET /api/v1/investigations/{case_id}`.
  - Zero tests for database verdict updates after SSE stream completion.
  - Zero tests for any of the 5 agent tool endpoints (`/tools/transactions`, `/tools/entities`, `/tools/patterns`, `/tools/legal-precedents`, `/tools/query`).
  - No SQLite / in-memory DB fixture for running isolated automated tests without an active remote TigerData cluster.

---

### 2.8 `backend/requirements.txt` (11 lines)

- **Observed Content**:
  ```text
  fastapi>=0.110.0
  uvicorn[standard]>=0.28.0
  polars>=0.20.0
  networkx>=3.2.1
  pydantic>=2.6.0
  pydantic-settings>=2.2.0
  httpx>=0.27.0
  pytest>=8.0.0
  pytest-asyncio>=0.23.0
  python-multipart>=0.0.9
  ```
- **Missing Required Packages**:
  - `sqlalchemy>=2.0.28` (ORM & AsyncEngine)
  - `asyncpg>=0.29.0` (high-performance async PostgreSQL driver)
  - `pgvector>=0.2.5` (SQLAlchemy pgvector support)
  - `aiosqlite>=0.20.0` (for isolated in-memory test fixtures)

---

### 2.9 `backend/main.py` (56 lines)

- **Observed Content**:
  - Instantiates `app = FastAPI(...)`.
  - Configures `CORSMiddleware`.
  - Includes `investigations_router` and `tts_router`.
  - `/health` endpoint returns `{status: "healthy", project, environment}`.
- **Gaps**:
  - Does not import or register `agent_tools_router`.
  - Lifespan handler does not initialize database schemas/extensions or gracefully close engine connection pools.

---

## 3. Database Architecture & Schema Mapping

### 3.1 Entity Relationship Diagram

```
+------------------------------------------------------------------------------------+
|                                 investigation_cases                                |
+------------------------------------------------------------------------------------+
| id: UUID (PK)                                                                      |
| filename: VARCHAR(255)                                                             |
| status: VARCHAR(50)  ['PROCESSED', 'STREAMING', 'COMPLETED', 'FAILED']            |
| created_at: TIMESTAMPTZ                                                            |
| completed_at: TIMESTAMPTZ (nullable)                                               |
| ingestion_metadata: JSONB                                                          |
| metrics: JSONB                                                                     |
| subgraph: JSONB                                                                    |
| patterns: JSONB                                                                    |
| verdict: JSONB (nullable)                                                          |
+------------------------------------------+-----------------------------------------+
                                           | 1
                                           |
                                           | N
+------------------------------------------v-----------------------------------------+
|                                    transactions                                    |
+------------------------------------------------------------------------------------+
| id: INT (PK, autoincrement)                                                        |
| case_id: UUID (FK -> investigation_cases.id ON DELETE CASCADE, INDEX)              |
| origin: VARCHAR(128) (INDEX)                                                       |
| destination: VARCHAR(128) (INDEX)                                                  |
| amount: FLOAT (INDEX)                                                              |
| timestamp: FLOAT (INDEX)                                                           |
| is_suspicious: BOOLEAN (INDEX)                                                     |
| reasons: JSONB                                                                     |
+------------------------------------------------------------------------------------+

+------------------------------------------------------------------------------------+
|                               legal_knowledge_vectors                              |
+------------------------------------------------------------------------------------+
| id: INT (PK, autoincrement)                                                        |
| article_code: VARCHAR(64) (INDEX)                                                  |
| law_name: VARCHAR(255)                                                             |
| content: TEXT                                                                      |
| embedding: VECTOR(1536)                                                            |
| HNSW INDEX on embedding (vector_cosine_ops)                                        |
+------------------------------------------------------------------------------------+
```

### 3.2 TigerData PostgreSQL Connectivity & Resilience Strategy

1. **Remote Connection URI**:
   - Format: `postgresql+asyncpg://user:password@host:port/dbname?ssl=require`
   - Connection args: `{"ssl": "require"}` for asyncpg when connecting over internet/VPC to TigerData.
2. **Connection Pooling**:
   - `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`.
3. **Graceful Fallback & Error Handling**:
   - If `DATABASE_URL` is not set:
     - FastAPI logs a warning: `⚠️ [DATABASE] DATABASE_URL is not set. Database persistence is disabled (in-memory mode).`
     - Routes that require database operation provide a clear informative HTTP 503 or graceful fallback to in-memory store so the service remains operable and tests can run reliably without network dependencies.
4. **Lifecycle Hooks in `backend/core/database.py`**:
   - `init_db()`: executes `CREATE EXTENSION IF NOT EXISTS vector;` and `Base.metadata.create_all(bind=engine)`.
   - `get_db()`: dependency yielding an `AsyncSession`, automatically committing on clean exit and rolling back on exceptions.
   - `close_db()`: disposes of the engine pool on application shutdown.

---

## 4. API Endpoints: Current vs. Required State

| Endpoint | Method | Status | Purpose | Implementation Details |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | ✅ Exists | Health check | Returns `{"status": "healthy", ...}` |
| `/api/v1/investigations/upload` | POST | ⚠️ Partial | CSV upload & graph pruning | Must persist `InvestigationCase` and `TransactionRecord` rows into DB. |
| `/api/v1/investigations` | GET | ❌ Missing | Case list with pagination | `GET /api/v1/investigations?page=1&limit=20` returning case summaries. |
| `/api/v1/investigations/{case_id}` | GET | ❌ Missing | Case detail & subgraph | Retrieves complete case, metrics, subgraph from DB. |
| `/api/v1/investigations/{case_id}/stream` | GET | ⚠️ Partial | SSE thoughts & verdict | Reads from DB, updates case verdict and status upon stream completion. |
| `/api/v1/tools/transactions` | POST | ❌ Missing | Filtered transaction queries | Filter by case, accounts, amount range, timestamps, suspicion flag. |
| `/api/v1/tools/entities` | POST | ❌ Missing | Entity profile analyzer | Aggregates volume in/out, degree, risk score, reasons. |
| `/api/v1/tools/patterns` | POST | ❌ Missing | Cycle & pass-through metrics | Returns isolated cycles and mule accounts for a case. |
| `/api/v1/tools/legal-precedents` | POST | ❌ Missing | Legal vector search | Cosine similarity against `legal_knowledge_vectors` for AML laws. |
| `/api/v1/tools/query` | POST | ❌ Missing | Dynamic composable query | Safely executes structured JSON criteria against target entities. |
| `/api/v1/tts/synthesize` | POST | ✅ Exists | ElevenLabs speech proxy | Audio stream proxy with silent MP3 fallback. |

---

## 5. Architectural Recommendations for Implementation

1. **Phase 1: Dependencies & Configuration**
   - Update `backend/requirements.txt` with `sqlalchemy>=2.0.28`, `asyncpg>=0.29.0`, `pgvector>=0.2.5`, `aiosqlite>=0.20.0`.
   - Update `backend/core/config.py` with `DATABASE_URL`, `POSTGRES_*` fields, connection pooling options, and helper properties.

2. **Phase 2: Database Layer & Models**
   - Implement `backend/core/database.py` with `create_async_engine`, `AsyncSessionLocal`, `get_db()`, `init_db()`, `close_db()`.
   - Create `backend/models/__init__.py` and `backend/models/forensic.py` with `InvestigationCase`, `TransactionRecord`, `LegalArticleVector`.
   - Provide a seeding routine for `legal_knowledge_vectors` (populating Mexican AML jurisprudence: CFF 69-B, LFPIORPI, UIF regulations).

3. **Phase 3: Persistent Investigation Management**
   - In `backend/api/routes/investigations.py`:
     - Inject `db: AsyncSession = Depends(get_db)`.
     - In `POST /upload`: Bulk-insert transactions and save the case record into TigerData PostgreSQL; maintain in-memory fallback for offline test resilience.
     - Implement `GET /api/v1/investigations`: Paginated query on `InvestigationCase`.
     - Implement `GET /api/v1/investigations/{case_id}`: Query case by UUID, returning 404 if missing.
     - In `GET /{case_id}/stream`: Fetch case from DB; upon terminal verdict, update `status = "COMPLETED"`, `verdict = verdict_payload`, `completed_at = now()`.

4. **Phase 4: Scalable n8n Agent Tools & Dynamic Registry**
   - Create `backend/api/routes/agent_tools.py`:
     - Define Pydantic request/response schemas for `/tools/transactions`, `/tools/entities`, `/tools/patterns`, `/tools/legal-precedents`, `/tools/query`.
     - Implement dynamic `QueryBuilder` with safe operator parsing to prevent SQL injection.
     - Implement `ToolRegistry` pattern allowing dynamic registration of tool handlers.
   - Register `agent_tools_router` in `backend/main.py`.

5. **Phase 5: Audio Proxy Hardening**
   - Add timeout resilience and `CancelledError` handling in `backend/api/routes/tts.py`.

6. **Phase 6: Comprehensive Automated Test Suite**
   - Create `backend/tests/conftest.py` with in-memory SQLite async engine fixture and test database sessions.
   - Add tests for:
     - Database connection and model CRUD operations.
     - CSV upload and relational persistence verification.
     - Case listing and retrieval.
     - SSE stream execution and database verdict update verification.
     - All dedicated agent tool endpoints (`transactions`, `entities`, `patterns`, `legal-precedents`).
     - Dynamic query builder endpoint (`/tools/query`).
     - TTS synthesis proxy and fallback generation.

---
