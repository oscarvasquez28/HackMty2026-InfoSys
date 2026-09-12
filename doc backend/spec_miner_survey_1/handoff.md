# Handoff Report - Forensic Auditor Backend Authoritative Specification Survey

## 1. Observation
1. **Repository Layout & Existing Codebase**:
   - `ORIGINAL_REQUEST.md`: Contains functional requirements R1 (TigerData PostgreSQL & pgvector), R2 (Investigation Lifecycle & Persistent Case Management), R3 (Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents), R4 (Speech Synthesis Proxy & Security), and R5 (Verification & Comprehensive Test Suite), with 14 explicit acceptance criteria across lines 55–80.
   - `backend/core/config.py`: Defines `Settings` class using `pydantic_settings.BaseSettings` with fields `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`, `DEBUG`, `BACKEND_CORS_ORIGINS`, `N8N_WEBHOOK_URL`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`, `MAX_CYCLE_LENGTH`, `PASS_THROUGH_RATIO_THRESHOLD`, `PASS_THROUGH_WINDOW_HOURS`. Lines 14–33 implement `assemble_cors_origins` validator supporting comma-separated strings or JSON arrays.
   - `backend/requirements.txt`: Currently lists:
     ```
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
     Observed: `sqlalchemy`, `pgvector`, and PostgreSQL async drivers (`psycopg[binary]` or `asyncpg`) are currently absent from `backend/requirements.txt`.
   - `backend/main.py`: Sets up FastAPI instance, CORS middleware, includes `investigations_router` and `tts_router` with prefix `settings.API_V1_STR` (`/api/v1`), and exposes `GET /health` returning `{"status": "healthy", "project": ..., "environment": ...}`.
   - `backend/api/routes/investigations.py`:
     - Line 17 defines ephemeral in-memory storage: `INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}`.
     - `POST /api/v1/investigations/upload`: Validates `.csv` suffix, parses with Polars `read_amlsim_csv(content)`, applies `apply_deterministic_filter(df)`, allocates `uuid.uuid4()`, stores in `INVESTIGATION_CASES`, and returns status 201 with `case_id`, `metrics`, `subgraph`, and `patterns`.
     - `GET /api/v1/investigations/{case_id}/stream`: Returns `StreamingResponse` using `generate_n8n_or_simulated_stream`. Posts to `N8N_WEBHOOK_URL` if configured with 10.0s timeout; on failure/absence, generates 6 sequential `thought` events and a final `verdict` event. Currently lacks endpoints for `GET /api/v1/investigations` (paginated list) and `GET /api/v1/investigations/{case_id}` (detail retrieval), and does not persist final verdict to a database.
   - `backend/api/routes/tts.py`:
     - Implements `POST /api/v1/tts/synthesize` with `SynthesizeRequest(text, voice_id, model_id)`.
     - Lines 24–30 generate fallback silent MPEG-1 Layer 3 frames when `ELEVENLABS_API_KEY` is empty or starts with `your_`.
     - Lines 33–65 proxy audio streaming from `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream` with header `xi-api-key`.
   - `backend/services/ingestion.py`:
     - Lines 7–12 define canonical column mapping `COLUMN_ALIASES` for `origin`, `destination`, `amount`, and `timestamp`.
     - Lines 28–102 define `read_amlsim_csv` using Polars with automatic sequential timestamp generation if missing, filtering `origin.is_not_null() & destination.is_not_null() & amount.is_not_null() & (amount > 0)`.
   - `backend/services/deterministic_filter.py`:
     - Lines 7–50 construct a NetworkX `DiGraph` tracking in/out flow sums and timestamps.
     - Lines 53–88 implement `detect_closed_cycles` bounding cycle length between 2 and `max_cycle_length`.
     - Lines 90–137 implement `detect_passthrough_accounts` checking `min(in, out) / max(in, out) >= 0.90` within `window_hours <= 48.0`.
     - Lines 139–260 implement `apply_deterministic_filter` pruning benign edges and scoring node risk: 0.80 (cycle), 0.70 (passthrough), 1.00 (both).
   - `doc/architecture/README.md`:
     - Sections 3.2, 4.1, 4.2, 4.3 detail the 6-stage lifecycle, container topology, SSE JSON schemas, and external TigerData/n8n constraints.
   - `doc/backend/README.md`:
     - Section 4.1 specifies the target SQLAlchemy async engine layer (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`) and the exact model definitions for `InvestigationCase`, `TransactionRecord`, and `LegalArticleVector`.
   - `doc/data-and-compliance/README.md`:
     - Section 5.1 details CFF Art. 69-B, distinguishing EFOS ("factureras") and EDOS (deductors), and procedural timelines (15 days presuntos, 30 days EDOS).
     - Section 5.2 details NIF A-2 economic substance and the evidentiary triad (certified public deeds with fecha cierta, verifiable deliverables, continuous financial flow).
     - Section 5.3 details UIF Reporte de Operación Inusual (ROI, 24–48h limit), Reporte de Operación Relevante (ROR, >$7,500 USD), and account freezing under Art. 115 LIC.
     - Section 5.4 details pgvector HNSW index configuration `USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)` for `legal_knowledge_vectors` with `Vector(1536)`.
   - `backend/tests/test_pipeline.py`:
     - Contains `test_complete_forensic_pipeline` and `test_tts_synthesize_proxy` using `httpx.ASGITransport` and synthetic CSV test fixtures.

## 2. Logic Chain
1. **From In-Memory to TigerData Relational Persistence**:
   - Observation: Currently `INVESTIGATION_CASES` in `backend/api/routes/investigations.py:17` stores cases in an in-memory Python dictionary.
   - Deduction: Restarting the container or adding worker processes drops all investigation data.
   - Requirement: R1 and `doc/backend/README.md` §4.1 mandate creating `backend/core/database.py` and `backend/models/forensic.py` using SQLAlchemy 2.0 async engine with SSL mode `sslmode=require` and connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`).
   - Inference: Case creation in `/upload` must write both an `InvestigationCase` record and bulk-insert `TransactionRecord` entities. Upon SSE stream completion, `/stream` must update `InvestigationCase.verdict` and `status="COMPLETED"`.
2. **From Hardcoded Stubs to Dynamic Agent Tools Router**:
   - Observation: `ORIGINAL_REQUEST.md` R3 requires an extensible, versioned agent tool router in `backend/api/routes/agent_tools.py` with 4 dedicated tool endpoints (`/tools/transactions`, `/tools/entities`, `/tools/patterns`, `/tools/legal-precedents`) and 1 dynamic composable query endpoint (`/tools/query`).
   - Deduction: n8n AI agents require granular, structured endpoints to inspect specific subgraphs, filter transactions, profile counterparties, and retrieve legal precedents without loading entire monolithic case JSONs.
   - Inference: A dynamic query builder and tool handler registry pattern allows registering query targets dynamically (e.g. transactions, cases, entities, precedents) supporting arbitrary filter combinations (`eq`, `gte`, `lte`, `like`, `in`) with pagination and sorting.
3. **From Regulatory Text to Vector Similarity Search**:
   - Observation: `doc/data-and-compliance/README.md` §5.4 and `ORIGINAL_REQUEST.md` R1 specify `legal_knowledge_vectors` with 1536-dimensional embeddings and HNSW cosine index.
   - Deduction: Mexican tax and AML jurisprudence (CFF Art. 69-B, NIF A-2, UIF guidelines) must be queryable via cosine distance (`<=>`) using pgvector.
   - Inference: `POST /api/v1/tools/legal-precedents` should accept query embeddings or query text and return ranked statutory articles with similarity scores.
4. **From Edge Case Identification to System Resilience**:
   - Observation: The system must handle unconfigured databases, missing ElevenLabs API keys, unconfigured n8n endpoints, malformed CSV uploads, and disconnected SSE clients without crashing.
   - Deduction: All external integration points have defined fallback strategies (e.g. synthetic silent MP3 frames, simulated 6-phase reasoning steps, clear diagnostic DB connection exceptions, Polars validation error mappings).
   - Inference: The backend design is fully resilient and supports offline demo mode while maintaining production readiness.

## 3. Caveats
1. Remote TigerData Database Connectivity: In demo mode or offline environments without active external network access, connecting to the live TigerData host requires valid credentials (`DATABASE_URL`). If not configured, the backend must fail gracefully or support a fallback local SQLite/Postgres configuration for unit tests.
2. Vector Embeddings Dimension: The specification specifies 1536 dimensions (matching OpenAI `text-embedding-3-small` / Gemini standard embeddings). When populating `legal_knowledge_vectors`, vector dimensions must strictly match the model dimension (1536).
3. Client Disconnect Handling: When an SSE client closes its connection, FastAPI's generator cancellation must be caught cleanly so database status is not left in an inconsistent state.

## 4. Conclusion
The authoritative specification for the Forensic Auditor Python Backend is comprehensive, rigorous, and clearly partitioned into five discrete pillars:
1. **Core Database & Models**: `backend/core/database.py` and `backend/models/forensic.py` with async SQLAlchemy 2.0, SSL connection pooling, `investigation_cases`, `transactions`, and `legal_knowledge_vectors` (pgvector 1536 HNSW).
2. **Investigation Lifecycle**: Persistent case creation in `/upload`, paginated history in `GET /investigations`, case retrieval in `GET /investigations/{case_id}`, and persistent verdict updates upon completion of `GET /investigations/{case_id}/stream`.
3. **Agent Tools Registry**: `backend/api/routes/agent_tools.py` exposing 4 dedicated tool endpoints (`transactions`, `entities`, `patterns`, `legal-precedents`) and a composable `/tools/query` dynamic builder with extensible registry.
4. **Security & Speech Proxy**: Shielded ElevenLabs TTS streaming proxy in `backend/api/routes/tts.py` with synthetic silent MP3 frame fallback.
5. **Comprehensive Automated Verification**: Unit and integration test suite in `backend/tests/` covering database CRUD, ingestion, graph metrics, tool queries, SSE streaming, and TTS fallbacks.

All requirements R1–R5, acceptance criteria, schema models, API payloads, mathematical formulas, and legal articles have been documented in detail in `analysis.md`.

## 5. Verification Method
To independently verify the discoveries documented in this report:
1. Inspect `analysis.md` in `.agents/spec_miner_survey_1/analysis.md` for complete specification tables, endpoint contracts, and edge cases.
2. Inspect `ORIGINAL_REQUEST.md` to cross-reference requirements R1–R5 against the mined feature matrix.
3. Review `doc/architecture/README.md` and `doc/backend/README.md` to verify SQLAlchemy pool settings, database models, and SSE event schemas.
4. Review `doc/data-and-compliance/README.md` to verify CFF 69-B, NIF A-2, UIF requirements, and pgvector HNSW indexing parameters.
5. Execute the project test suite once implemented:
   ```powershell
   $env:PYTHONPATH="."
   pytest backend/tests/ -v
   ```
   *Invalidation Conditions*: Any deviation from the contract payloads in `doc/architecture/README.md`, failure of `pytest backend/tests/`, or unhandled exceptions when `DATABASE_URL`, `N8N_WEBHOOK_URL`, or `ELEVENLABS_API_KEY` are unset.
