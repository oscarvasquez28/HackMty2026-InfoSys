# Handoff Report: Integration, Database, Agent Tools, and Testing Architecture

**Agent**: `explorer_survey_2`  
**Working Directory**: `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_survey_2`  
**Handoff Type**: Hard (Investigation & Survey Complete)  
**Date**: 2026-09-12  

---

## 1. Observation

Direct observations from the current codebase and project specification:

1. **In-Memory Case Persistence**:
   - In `backend/api/routes/investigations.py`, line 17:
     ```python
     # In-memory case storage (in production, backed by PostgreSQL / Redis)
     INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}
     ```
   - In `backend/api/routes/investigations.py`, lines 58-59:
     ```python
     INVESTIGATION_CASES[case_id] = case_record
     ```
   - No relational or vector database operations occur during dataset upload or stream generation.

2. **Missing Database Core & Models**:
   - `backend/core/database.py` does not exist.
   - `backend/models/` directory does not exist.
   - `backend/api/routes/agent_tools.py` does not exist.

3. **Incomplete Router Registration**:
   - In `backend/main.py`, lines 38-41:
     ```python
     # Router Registration
     app.include_router(investigations_router, prefix=settings.API_V1_STR)
     app.include_router(tts_router, prefix=settings.API_V1_STR)
     ```
   - `agent_tools_router` is neither imported nor included.

4. **Missing Database Drivers in Dependencies**:
   - In `backend/requirements.txt`, lines 1-11:
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
   - `SQLAlchemy`, `asyncpg`, `psycopg`, `pgvector`, `greenlet`, and `aiosqlite` are absent.

5. **Configuration Variables State**:
   - In `backend/core/config.py`, lines 7-52:
     Contains `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT`, `DEBUG`, `BACKEND_CORS_ORIGINS`, `N8N_WEBHOOK_URL`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`, `MAX_CYCLE_LENGTH`, `PASS_THROUGH_RATIO_THRESHOLD`, and `PASS_THROUGH_WINDOW_HOURS`.
     Missing `DATABASE_URL` and connection pool settings (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_PRE_PING`, `DB_POOL_RECYCLE`, `DB_SSL_REQUIRE`).
   - In `backend/.env.example`, lines 1-20:
     Missing `DATABASE_URL`.

6. **Target Contract & Architecture Specifications**:
   - `ORIGINAL_REQUEST.md`, lines 14-54: Mandates TigerData PostgreSQL with `pgvector`, SSL (`sslmode=require`), connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`), persistence of `InvestigationCase`, `TransactionRecord`, and `LegalArticleVector`, dedicated tool endpoints (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`), and dynamic query builder (`/query`).
   - `doc/backend/README.md`, lines 162-296: Outlines target models and session management blueprint.

---

## 2. Logic Chain

From the direct observations above:

1. **Persistence Gap (Observation 1 & 2 $\to$ Architecture Impact)**:
   Because cases are stored in process-local dictionary `INVESTIGATION_CASES`, restarting the backend or deploying multiple worker processes results in immediate state loss. Implementing `backend/core/database.py` with async SQLAlchemy 2.0 and `backend/models/forensic.py` is essential to satisfy R1 and R2.

2. **Driver Compatibility & SSL Normalization (Observation 4, 5, 6 $\to$ Driver Selection)**:
   - TigerData mandates SSL (`sslmode=require`).
   - `asyncpg` is the optimal high-throughput async PostgreSQL driver for FastAPI, but expects `ssl="require"` or `ssl=True` rather than libpq-style `sslmode=require` unless translated.
   - `psycopg` (psycopg 3) natively supports `sslmode=require`.
   - The connection engine factory must parse `DATABASE_URL` and normalize connection arguments so both `postgresql+asyncpg` and `postgresql+psycopg` function without configuration errors.
   - Adding `sqlalchemy[asyncio]`, `asyncpg`, `psycopg[binary]`, `pgvector`, `greenlet`, and `aiosqlite` to `backend/requirements.txt` is required.

3. **Database Dependency Injection & Missing Config Error (Observation 5 $\to$ Fault Tolerance)**:
   - If `DATABASE_URL` is empty, attempting database operations should fail gracefully with HTTP 503 ("Database connection is not configured").
   - `get_db()` must yield an `AsyncSession` with automatic rollback on exception and cleanup in `finally`.

4. **Agent Tools & Scalable Query Engine (Observation 2, 3, 6 $\to$ Router Architecture)**:
   - `backend/api/routes/agent_tools.py` must be created and registered in `backend/main.py`.
   - Dedicated endpoints (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`) must accept structured filters and query PostgreSQL/JSONB.
   - The dynamic query builder (`/query`) must use an extensible handler registry (`ToolRegistry`), enforcing column whitelisting, parameterized SQL generation, and mandatory `case_id` scoping to prevent SQL injection and cross-case leaks.

5. **Test Suite Independence & SQLite Compatibility (Observation 4 $\to$ Testing Strategy)**:
   - Automated tests must run without requiring live external TigerData credentials.
   - In-memory SQLite (`sqlite+aiosqlite:///:memory:`) can simulate the async database.
   - Because SQLite does not natively support `Vector(1536)`, registering `@compiles(Vector, "sqlite")` returning `"TEXT"` allows schema generation to succeed without error.
   - FastAPI's `app.dependency_overrides[get_db]` allows swapping to the in-memory SQLite session during tests.

---

## 3. Caveats

1. **TigerData Network Connectivity**:
   - The backend will run locally or in containers; live connectivity to TigerData depends on external network access and valid credentials in `.env`.
   - Offline tests must not depend on live TigerData network availability.
2. **pgvector Native Indexing in SQLite**:
   - SQLite cannot execute native vector cosine distance queries (`<=>`). During unit tests on SQLite, vector queries must be validated via text fallback, mocked embeddings, or unit testing vector math in Python.
3. **ElevenLabs Upstream Dependability**:
   - Tests must default to verifying the synthetic MPEG silence fallback (`X-Audio-Source: synthetic-fallback-mode`) to avoid exhausting ElevenLabs API quotas or failing during network disruption.
4. **Scope Constraint**:
   - As an Explorer, this report is strictly read-only. No source files outside `.agents/` have been modified.

---

## 4. Conclusion

1. **Database Architecture**:
   - Engine: Async SQLAlchemy 2.0 supporting `postgresql+asyncpg` and `postgresql+psycopg`.
   - Pooling: `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`.
   - SSL: Enforce `ssl="require"` for TigerData.
   - Models: `InvestigationCase` (JSONB for topology/metrics/verdict), `TransactionRecord` (relational), `LegalArticleVector` (`Vector(1536)` with HNSW index).
2. **Environment & Dependencies**:
   - Add `DATABASE_URL` and pool settings to `backend/core/config.py` and `backend/.env.example`.
   - Update `backend/requirements.txt` with async SQLAlchemy, drivers, and pgvector.
3. **n8n Agent Tools**:
   - Implement `backend/api/routes/agent_tools.py` with 4 dedicated endpoints and 1 dynamic `/query` endpoint backed by `ToolRegistry`.
4. **Testing Architecture**:
   - Use `sqlite+aiosqlite:///:memory:` with `@compiles(Vector, "sqlite")` and `dependency_overrides[get_db]`.
   - Test SSE thought streaming + DB verdict persistence, CSV alias and edge cases, and ElevenLabs offline fallback.

---

## 5. Verification Method

To independently verify this investigation and the upcoming implementation:

1. **Inspect Target Files**:
   - Inspect `backend/core/config.py`, `backend/requirements.txt`, and `backend/main.py`.
   - Inspect analysis details in `.agents/explorer_survey_2/analysis.md`.
2. **Test Command (Once Implemented)**:
   ```bash
   # From workspace root
   set PYTHONPATH=.
   pytest backend/tests/ -v
   ```
3. **Invalidation Conditions**:
   - If `asyncpg` throws `TypeError: connect() got an unexpected keyword argument 'sslmode'`, the SSL translation logic must be adjusted in `backend/core/database.py`.
   - If SQLite tests fail with `CompileError: (sqlite) Vector`, verify that `@compiles(Vector, "sqlite")` is registered before table creation.
   - If n8n agent queries allow arbitrary SQL strings, the dynamic query builder must be checked for strict column whitelisting and parameterized compilation.
