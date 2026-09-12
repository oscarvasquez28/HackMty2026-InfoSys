# Handoff Report: Forensic Auditor Backend Architectural Survey

**Agent**: Explorer (`explorer_survey_1`)  
**Parent Orchestrator ID**: `aa7bce53-1d36-4848-bf78-a047dfb94d28`  
**Working Directory**: `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_survey_1`  
**Handoff Type**: Hard (Investigation complete)  

---

## 1. Observation

Direct code inspections across the workspace revealed the following specific findings:

### 1.1 Ingestion & Graph Analytics Services (Functional)
- `backend/services/ingestion.py` (lines 7–12, 28–85):
  - Normalizes IBM AMLSim columns (`origin`, `destination`, `amount`, `timestamp`) using `COLUMN_ALIASES`.
  - Filters strictly positive amounts (`amount > 0`) and generates synthetic steps if timestamps are omitted.
- `backend/services/deterministic_filter.py` (lines 53–88, 90–136, 139–259):
  - Builds `networkx.DiGraph` from the Polars DataFrame.
  - Detects directed cycles bounded by `settings.MAX_CYCLE_LENGTH` (`detect_closed_cycles`).
  - Detects rapid pass-through accounts (`detect_passthrough_accounts`) matching retention ratio $\ge 0.90$ within $\le 48.0$ hours.
  - Returns `subgraph`, `metrics`, and `patterns` dictionaries.

### 1.2 State Persistence & Database Layer (Missing / Non-Existent)
- Directory inspection: `backend/models/` does not exist.
- File inspection: `backend/core/database.py` does not exist.
- `backend/core/config.py` (lines 7–54):
  - Contains configuration for `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`, `DEBUG`, `BACKEND_CORS_ORIGINS`, `N8N_WEBHOOK_URL`, `ELEVENLABS_*`, `MAX_CYCLE_LENGTH`, and `PASS_THROUGH_*`.
  - Lacks any database parameters: no `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, or connection pool attributes.
- `backend/requirements.txt` (lines 1–11):
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
  - `sqlalchemy`, `asyncpg`, `psycopg`, and `pgvector` are absent.

### 1.3 Investigation API Routes (In-Memory & Incomplete)
- `backend/api/routes/investigations.py`:
  - Line 17: `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}` — investigation cases are held purely in an in-memory dictionary.
  - Lines 20–67: `POST /upload` creates a case in `INVESTIGATION_CASES` with a UUID key, returning HTTP 201 with metrics, subgraph, and patterns. No database persistence or individual transaction storage is performed.
  - Lines 192–214: `GET /{case_id}/stream` checks `INVESTIGATION_CASES` and streams SSE thoughts and verdict, but does not persist the completed verdict or update case status in a database.
  - Neither `GET /api/v1/investigations` (paginated case listing) nor `GET /api/v1/investigations/{case_id}` (retrieval by ID) exist in the codebase.

### 1.4 Agent Tools & Dynamic Tool Registry (Missing / Non-Existent)
- `backend/api/routes/agent_tools.py` does not exist.
- None of the required n8n agent tool endpoints exist:
  - `POST /api/v1/tools/transactions`
  - `POST /api/v1/tools/entities`
  - `POST /api/v1/tools/patterns`
  - `POST /api/v1/tools/legal-precedents`
  - `POST /api/v1/tools/query`
- `backend/main.py` (lines 6–7, 39–40) imports and registers only `investigations_router` and `tts_router`.

### 1.5 Speech Synthesis Proxy (Present, Minor Hardening Opportunity)
- `backend/api/routes/tts.py` (lines 19–30, 67–106):
  - Provides `generate_fallback_silence_mp3()` emitting 320-byte MPEG-1 Layer 3 frames repeated 10 times with `X-Audio-Source: synthetic-fallback-mode`.
  - Proxies to ElevenLabs `stream` API when `ELEVENLABS_API_KEY` is present.
  - Needs hardening against network timeout and client disconnect exceptions.

### 1.6 Verification & Test Coverage (Deficient)
- `backend/tests/test_pipeline.py` (lines 18–100):
  - Contains only two tests: `test_complete_forensic_pipeline` (validating in-memory upload and SSE streaming) and `test_tts_synthesize_proxy`.
  - Contains zero tests for database operations, models, transaction records, agent tools, or persistence lifecycle.

---

## 2. Logic Chain

1. **Premise 1**: The user request and target blueprint (`ORIGINAL_REQUEST.md`, `doc/backend/README.md`) require persistence of cases (`investigation_cases`), relational transactions (`transactions`), and Mexican AML statutes (`legal_knowledge_vectors`) in TigerData PostgreSQL with `pgvector` using async SQLAlchemy 2.0.
2. **Deduction from 1.2**: Because `backend/models/` and `backend/core/database.py` do not exist, and `requirements.txt` lacks `sqlalchemy`, `asyncpg`, and `pgvector`, the database tier is completely unimplemented.
3. **Premise 2**: Requirement R2 specifies that `POST /upload` must persist the case record and individual transactions, `GET /investigations` must return paginated history, `GET /investigations/{case_id}` must retrieve case data from PostgreSQL, and `GET /stream` must update verdict and status upon completion.
4. **Deduction from 1.3**: Currently, `POST /upload` and `GET /{case_id}/stream` rely exclusively on an ephemeral global dictionary `INVESTIGATION_CASES`. `GET /investigations` and `GET /investigations/{case_id}` are completely missing.
5. **Premise 3**: Requirement R3 specifies an extensible, versioned agent tool router in `backend/api/routes/agent_tools.py` with 4 dedicated endpoints (`/tools/transactions`, `/entities`, `/patterns`, `/legal-precedents`) and 1 dynamic query endpoint (`/tools/query`).
6. **Deduction from 1.4**: Since `agent_tools.py` does not exist and `main.py` has no reference to it, all n8n AI agent tool functionality is currently absent.
7. **Premise 4**: Requirement R5 demands comprehensive automated test coverage for database CRUD, CSV ingestion and persistence, agent tools, SSE streaming, and TTS.
8. **Deduction from 1.6**: Current test coverage is limited to 2 happy-path tests on in-memory endpoints, leaving all newly required database and tool functionalities unverified.

---

## 3. Caveats

1. **Remote TigerData Instance Availability**: The actual external TigerData PostgreSQL credentials and live connectivity depend on runtime environment variables (`DATABASE_URL`). An offline/mock testing strategy (e.g. SQLite async or mock session) is essential during local test execution to ensure tests pass without network flakiness.
2. **Vector Embeddings Dimension**: `doc/backend/README.md` and `ORIGINAL_REQUEST.md` specify `Vector(1536)` (standard OpenAI text-embedding-3-small dimension) or Gemini-compatible dimension. The schema should default to 1536 while allowing keyword fallback in legal precedent searches if embeddings are not supplied in requests.
3. **No Code Modified**: As an explorer with read-only constraints, no application code, configuration files, or database schemas outside `.agents/explorer_survey_1/` were altered.

---

## 4. Conclusion

The existing backend is an operational prototype with robust Polars and NetworkX graph pruning algorithms, but it lacks the enterprise persistence, model layer, and agent query interfaces needed for the target production state.

To fulfill all requirements in `ORIGINAL_REQUEST.md`, the implementation roadmap must execute:
1. **Dependencies & Settings**: Update `requirements.txt` (SQLAlchemy 2.0, asyncpg, pgvector, aiosqlite) and `backend/core/config.py` (PostgreSQL and pooling settings).
2. **Database Engine & Lifespan**: Implement `backend/core/database.py` (`engine`, `get_db`, `init_db`, `close_db`) with SSL enforcement and integrate with `lifespan` in `backend/main.py`.
3. **Declarative Models**: Implement `backend/models/forensic.py` with `InvestigationCase`, `TransactionRecord`, and `LegalArticleVector`, including HNSW vector index and legal seed data.
4. **Persistent Investigations**: Expand `backend/api/routes/investigations.py` to persist cases and transactions in PostgreSQL, add `GET /investigations` (paginated list) and `GET /investigations/{case_id}`, and update the verdict and status upon SSE stream completion.
5. **n8n Agent Tool Registry**: Implement `backend/api/routes/agent_tools.py` with the 4 dedicated endpoints, the `/tools/query` endpoint with dynamic query builder, and register in `backend/main.py`.
6. **TTS Hardening**: Add timeout and disconnect resilience in `backend/api/routes/tts.py`.
7. **Comprehensive Test Suite**: Expand `backend/tests/` with database CRUD, transaction queries, agent tool endpoints, and persistence lifecycle tests using an async in-memory fixture.

---

## 5. Verification Method

To independently verify the observations and conclusions in this report:

1. **Inspect Missing Files**:
   - Confirm `backend/core/database.py` does not exist:
     ```powershell
     Test-Path "backend/core/database.py"  # Returns False
     ```
   - Confirm `backend/models/` does not exist:
     ```powershell
     Test-Path "backend/models"  # Returns False
     ```
   - Confirm `backend/api/routes/agent_tools.py` does not exist:
     ```powershell
     Test-Path "backend/api/routes/agent_tools.py"  # Returns False
     ```
2. **Inspect Existing In-Memory Implementation**:
   - View line 17 of `backend/api/routes/investigations.py` to confirm in-memory dictionary `INVESTIGATION_CASES`.
   - View `backend/requirements.txt` to confirm lack of SQLAlchemy and database drivers.
3. **Review Detailed Technical Document**:
   - Inspect `.agents/explorer_survey_1/analysis.md` for the full technical breakdown, ER diagram, and implementation proposals.
