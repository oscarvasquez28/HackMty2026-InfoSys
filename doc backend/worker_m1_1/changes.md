# Milestone 1 Code Changes Report

**Agent**: `worker_m1_1`  
**Milestone**: Milestone 1 (TigerData PostgreSQL & pgvector Database Layer)  
**Date**: 2026-09-12  

---

## 1. Summary of Modifications

### 1.1 `backend/requirements.txt`
- **Added**:
  - `sqlalchemy[asyncio]>=2.0.28`
  - `asyncpg>=0.29.0`
  - `psycopg[binary]>=3.1.18`
  - `pgvector>=0.2.5`
  - `greenlet>=3.0.3`
  - `aiosqlite>=0.20.0`
- **Purpose**: Enables modern asynchronous database access for PostgreSQL, pgvector embedding storage, and local async SQLite test support.

### 1.2 `backend/core/config.py`
- **Updated Imports**: Added `Optional` to `typing` imports.
- **Added Settings Attributes**:
  - `DATABASE_URL: Optional[str] = None`
  - `DB_POOL_SIZE: int = 20`
  - `DB_MAX_OVERFLOW: int = 10`
  - `DB_POOL_PRE_PING: bool = True`
  - `DB_POOL_RECYCLE: int = 3600`
  - `DB_SSL_REQUIRE: bool = True`
  - `DB_ECHO: bool = False`
- **Added Validator**: `assemble_database_url` converts whitespace-only strings to `None` to prevent malformed connection attempts.

### 1.3 `backend/models/forensic.py` (New File)
- **Base**: `class Base(AsyncAttrs, DeclarativeBase): pass`
- **SQLite Dialect Compilers**:
  - `@compiles(Vector, "sqlite")`: maps pgvector `Vector` to `TEXT` for SQLite execution.
  - `@compiles(JSONB, "sqlite")`: maps PostgreSQL `JSONB` to `JSON` for SQLite execution.
  - Cross-dialect `JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")`.
- **Model `InvestigationCase`**:
  - UUID primary key (`default=uuid.uuid4`).
  - `filename`: `String(255)`.
  - `status`: `String(50)`, default `"PENDING"`.
  - `created_at` and `updated_at`: `DateTime(timezone=True)`.
  - JSONB fields: `ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`.
  - Relationship `transactions` with `cascade="all, delete-orphan", passive_deletes=True`.
- **Model `TransactionRecord`**:
  - UUID primary key (`default=uuid.uuid4`).
  - `case_id`: foreign key referencing `investigation_cases.id` with `ondelete="CASCADE"`, indexed.
  - `origin`, `destination`: `String(100)`, indexed.
  - `amount`: `Numeric(18, 2)`.
  - `timestamp`: `DateTime(timezone=True)`.
  - `is_suspicious`: `Boolean`, default `False`, indexed.
  - `reasons`: `JSONB` list of strings.
  - Relationship `case`.
- **Model `LegalArticleVector`**:
  - UUID primary key (`default=uuid.uuid4`).
  - `article_code`: `String(50)`, unique, indexed.
  - `law_name`: `String(100)`.
  - `content`: `Text`.
  - `embedding`: `Vector(1536)`.
  - Table Args: HNSW cosine index (`idx_legal_vectors_hnsw`) with `m=16, ef_construction=64`, and `postgresql_ops={"embedding": "vector_cosine_ops"}`.
- **Deterministic Embedding Generator**: `generate_deterministic_embedding(text: str, dim: int = 1536) -> List[float]` producing unit-normalized (L2 norm = 1.0) reproducible 1536-dim vectors from text hash.
- **Mexican AML Jurisprudence Precedents**: Encoded 6 authoritative legal texts:
  1. `CFF-ART-69B`: Inexistencia de operaciones, EFOS vs EDOS, 15 days rebuttal, 30 days EDOS regularisation.
  2. `NIF-A2-MATERIALIDAD`: Sustancia económica, Tesis SCJN 2a./J. 78/2019, Tríada Probatoria Forense (Fecha cierta NOM-151, Entregables verificables, Trazabilidad financiera).
  3. `UIF-ROI-24H`: Reporte de Operación Inusual, 24-48 horas, pass-through accounts, circular flow, smurfing, tipping-off prohibition.
  4. `UIF-ROR-7500USD`: Reporte de Operación Relevante, umbral $7,500 USD, fraccionamiento y reclasificación a ROI.
  5. `LIC-ART-115-BLOQUEO`: Lista de Personas Bloqueadas (LPB), inmovilización de fondos, estándar 2a./J. 46/2018 (colaboración internacional).
  6. `CPF-ART-400BIS`: Delito de Operaciones con Recursos de Procedencia Ilícita (Lavado de Dinero), 5 a 15 años de prisión, presunción de ilicitud, concurso con delitos fiscales (Art 108 CFF).
- **Seed Helper**: `seed_legal_knowledge(session: AsyncSession)` providing idempotent upsert of precedents.

### 1.4 `backend/models/__init__.py` (New File)
- Exports `Base`, `InvestigationCase`, `TransactionRecord`, `LegalArticleVector`, `SEED_LEGAL_PRECEDENTS`, `generate_deterministic_embedding`, and `seed_legal_knowledge`.

### 1.5 `backend/core/database.py` (New File)
- `normalize_database_url(raw_url: str) -> Tuple[str, Dict[str, Any]]`:
  - Normalizes `postgres://` or `postgresql://` to `postgresql+asyncpg://` or `postgresql+psycopg://`.
  - Translates `sslmode=require` query param to `connect_args={"ssl": "require"}` for asyncpg.
  - Preserves SQLite memory and file URLs.
- `sanitize_database_url(url: str) -> str`:
  - Masks password strings with `****` to prevent credential exposure in logs.
- `create_engine_and_sessionmaker(database_url: str, echo: Optional[bool] = None)`:
  - Produces `(AsyncEngine, async_sessionmaker[AsyncSession])`.
  - Configures `StaticPool` and enables `PRAGMA foreign_keys=ON;` for SQLite.
  - Configures production connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`) for PostgreSQL.
- `get_engine() -> AsyncEngine`: Singleton accessor.
- `get_session_factory() -> async_sessionmaker[AsyncSession]`: Factory accessor (`expire_on_commit=False`).
- `get_db() -> AsyncGenerator[AsyncSession, None]`: FastAPI dependency yielding transactional session with commit/rollback/close.
- `init_db(engine: Optional[AsyncEngine] = None)`:
  - Skips gracefully if `DATABASE_URL` is empty.
  - Executes `CREATE EXTENSION IF NOT EXISTS vector;` if PostgreSQL.
  - Runs `Base.metadata.create_all`.
  - Runs `seed_legal_knowledge`.
- `close_db()`: Disposes of engine connection pool.

### 1.6 `backend/main.py`
- Updated FastAPI `lifespan` context manager:
  - Startup: Calls `await init_db()`, catching any connection exceptions defensively.
  - Teardown: Calls `await close_db()`, disposing of pool cleanly.

### 1.7 `backend/tests/test_database.py` (New File)
- Added 7 comprehensive unit tests:
  1. `test_database_url_normalization`
  2. `test_sanitize_database_url`
  3. `test_settings_database_configuration`
  4. `test_deterministic_embedding_generator`
  5. `test_sqlite_model_crud_and_cascade_delete`
  6. `test_legal_knowledge_seeding_and_idempotency`
  7. `test_init_db_lifecycle`
