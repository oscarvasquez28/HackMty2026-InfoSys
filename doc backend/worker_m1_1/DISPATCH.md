## 2026-09-12T09:07:09Z

You are Worker M1 implementing Milestone 1 (TigerData PostgreSQL & pgvector Database Layer) in the Forensic Auditor Python Backend project.

Your Working Directory: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\worker_m1_1
Workspace Root: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar
Original Request: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\ORIGINAL_REQUEST.md
Project Plan: c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\orchestrator_1\PROJECT.md

Exclusive Write Ownership:
- `backend/requirements.txt`
- `backend/core/config.py`
- `backend/core/database.py`
- `backend/models/__init__.py`
- `backend/models/forensic.py`
- `backend/main.py` (lifespan section)

Authoritative Reference Reports:
Read before implementing:
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\spec_miner_m1_1\handoff.md`
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m1_1\handoff.md`
- `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\explorer_m1_2\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks:
1. Initialize `.agents/worker_m1_1` with BRIEFING.md and progress.md.
2. Update `backend/requirements.txt`:
   Add `sqlalchemy[asyncio]>=2.0.28`, `asyncpg>=0.29.0`, `psycopg[binary]>=3.1.18`, `pgvector>=0.2.5`, `greenlet>=3.0.3`, `aiosqlite>=0.20.0`.
3. Update `backend/core/config.py`:
   Add `DATABASE_URL: Optional[str] = None`, `DB_POOL_SIZE: int = 20`, `DB_MAX_OVERFLOW: int = 10`, `DB_POOL_PRE_PING: bool = True`, `DB_POOL_RECYCLE: int = 3600`, `DB_SSL_REQUIRE: bool = True`, with any required validators.
4. Implement `backend/models/forensic.py` and `backend/models/__init__.py`:
   - Declarative `Base = declarative_base()` or `class Base(AsyncAttrs, DeclarativeBase): pass`.
   - SQLite compilation hooks: `@compiles(Vector, "sqlite")` and `@compiles(JSONB, "sqlite")`.
   - `InvestigationCase`: UUID PK, filename, status ("PENDING"), created_at/updated_at, JSONB fields (`ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`).
   - `TransactionRecord`: UUID PK, `case_id` FK with CASCADE and index, origin, destination, amount (Numeric(18,2)), timestamp (timezone-aware), is_suspicious (bool), reasons (JSONB).
   - `LegalArticleVector`: UUID PK, `article_code` (unique, indexed), `law_name`, `content` (Text), `embedding` (Vector(1536) with HNSW cosine index `m=16, ef_construction=64`).
   - Mexican AML jurisprudence seed data (CFF 69-B EFOS/EDOS, NIF A-2 economic substance & evidentiary triad, UIF ROI/ROR/Art 115 LIC).
5. Implement `backend/core/database.py`:
   - URL scheme normalization (`postgres://` / `postgresql://` -> `postgresql+asyncpg://` or `postgresql+psycopg://`).
   - SSL handling: translate `sslmode=require` to `connect_args={"ssl": "require"}` for asyncpg.
   - Connection pool settings (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`), and `StaticPool` for SQLite memory.
   - `async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)`.
   - `get_db()` async generator yielding `AsyncSession` with transactional try/commit/rollback/close.
   - Lifecycle hooks: `init_db()` and `close_db()`.
6. Update `backend/main.py`:
   - In `lifespan(app: FastAPI)`, call `await init_db()` on startup and `await close_db()` on shutdown, catching connection errors defensively so offline environments continue running.
7. Verification:
   - Run python import / validation commands or smoke tests using `run_command` to verify module importability and syntax.
8. Document all changes in `changes.md` and complete a structured handoff in `handoff.md`.
9. Send a message to the orchestrator upon completion.
