# Technical Analysis & Implementation Specification: Milestone 1
## Database Engine, Connection Pooling & Session Lifecycle

**Module**: `backend/core/database.py`, `backend/models/forensic.py`, `backend/core/config.py`  
**Milestone**: M1 (TigerData PostgreSQL & pgvector Database Layer)  
**Author**: Explorer Agent M1  
**Status**: SPECIFICATION COMPLETE  

---

## 1. Executive Summary & Problem Boundary

### 1.1 Objective
Design and specify the production-grade database persistence layer for the Forensic Auditor Python Backend. The system must transition from the temporary in-memory state dictionary (`INVESTIGATION_CASES: Dict[str, Dict[str, Any]]`) to a resilient, asynchronous PostgreSQL layer hosted on TigerData PostgreSQL 16 with the `pgvector` extension, while maintaining zero-friction developer testing through SQLite mock compatibility.

### 1.2 Boundary & Scope
- **In-Scope**:
  - Exact specification for `backend/core/database.py` (engine creation, connection pooling, driver URL normalization, SSL query translation, transactional sessionmaker, `get_db()` dependency generator, and lifecycle hooks `init_db()` / `close_db()`).
  - Target SQLAlchemy 2.0 declarative models in `backend/models/forensic.py` (`InvestigationCase`, `TransactionRecord`, `LegalArticleVector`) including indexes, relationships, and Mexican AML jurisprudence seed data.
  - Configuration extensions in `backend/core/config.py` and package additions in `backend/requirements.txt`.
  - SQLite mock compatibility layer using SQLAlchemy `@compiles` hooks to enable fast unit testing without an external PostgreSQL dependency.
  - Lifespan integration in `backend/main.py`.
- **Out-of-Scope (Deferred to Downstream Milestones)**:
  - Modifying the route endpoints in `backend/api/routes/investigations.py` (Milestone 2).
  - Building dynamic query builders and n8n tool endpoints in `backend/api/routes/agent_tools.py` (Milestone 3).
  - Hardening ElevenLabs TTS proxy (Milestone 4).
  - Writing end-to-end integration tests (Milestone 5).

---

## 2. Current State vs. Target State Analysis

| Dimension | Current State (`backend/`) | Target State (Milestone 1) |
| :--- | :--- | :--- |
| **Persistence Engine** | Ephemeral process-local dictionary (`INVESTIGATION_CASES` in `api/routes/investigations.py`). | Asynchronous PostgreSQL 16 engine via SQLAlchemy 2.0 (`create_async_engine`). |
| **Driver & Protocol** | None (pure in-memory). | Asynchronous driver support: primary `postgresql+asyncpg`, fallback `postgresql+psycopg` (psycopg 3), plus `sqlite+aiosqlite` for test runs. |
| **Connection Pooling** | N/A | `QueuePool` with `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`. |
| **SSL Enforcement** | N/A | Strict SSL translation: `sslmode=require` query parameters translated safely to asyncpg connection arguments (`connect_args={"ssl": "require"}`). |
| **Session Lifecycle** | None (direct dictionary mutations). | `get_db()` async generator yielding managed `AsyncSession` with atomic `commit()`, `rollback()` on exceptions, and guaranteed `close()`. |
| **Vector Storage** | None. | `LegalArticleVector` table with pgvector `Vector(1536)` and HNSW cosine index (`m=16, ef_construction=64`). |
| **Schema Lifecycle** | Manual / None. | Automatic initialization via `init_db()` (creates extensions `vector` and `uuid-ossp`, compiles tables, seeds jurisprudence) and `close_db()` (pool disposal). |
| **Test Environment** | In-memory synthetic dicts in `tests/test_pipeline.py`. | Seamless test execution against `sqlite+aiosqlite:///:memory:` via `@compiles(Vector, "sqlite")` and `StaticPool`. |

---

## 3. Database Engine & Driver Normalization Specification (`backend/core/database.py`)

### 3.1 Driver URL Normalization & SSL Translation

#### The Async Driver Pitfall
In production, database connection strings are often provided via environment variables as:
- `postgres://...` (legacy Heroku / Supabase default)
- `postgresql://...` (standard libpq default)
- `postgresql+asyncpg://...` (SQLAlchemy asyncpg)
- `postgresql+psycopg://...` (SQLAlchemy psycopg3)

When using `create_async_engine`:
1. Passing `postgres://` or `postgresql://` causes SQLAlchemy to attempt to load the synchronous `psycopg2` driver, raising `sqlalchemy.exc.ArgumentError: The new_engine function only supports async drivers`.
2. Furthermore, if a PostgreSQL connection string contains `?sslmode=require`:
   - `psycopg` (psycopg 3) natively understands `sslmode=require` via libpq.
   - `asyncpg` does **not** use libpq and does **not** accept `sslmode` as a connection argument. If `sslmode=require` is left in the query string of an asyncpg URL, SQLAlchemy passes URL query parameters directly to `asyncpg.connect(**kwargs)`, which immediately raises:
     ```text
     TypeError: connect() got an unexpected keyword argument 'sslmode'
     ```
   - In asyncpg, SSL must be specified via `connect_args={"ssl": "require"}` (or `ssl=True` / `ssl.SSLContext`), and `sslmode` **must be stripped** from the URL query string.

#### Normalization Algorithm
The normalization function `normalize_database_url(raw_url: str)` must execute the following sequence:

```python
import urllib.parse
from typing import Dict, Any, Tuple

def normalize_database_url(raw_url: str) -> Tuple[str, Dict[str, Any]]:
    """Normalizes database connection URLs and translates driver-specific parameters.
    
    1. Trims whitespace and validates non-empty string.
    2. Preserves SQLite URLs untouched (e.g., sqlite+aiosqlite:///:memory:).
    3. Converts legacy 'postgres://' or 'postgresql://' schemes to 'postgresql+asyncpg://'.
    4. Handles asyncpg vs psycopg SSL parameter translation:
       - For asyncpg: extracts 'sslmode', removes it from the query string,
         and sets connect_args['ssl'] accordingly.
       - For psycopg: preserves 'sslmode' in the query string.
    
    Returns:
        Tuple[str, Dict[str, Any]]: (normalized_url, connect_args)
    """
    if not raw_url or not raw_url.strip():
        raise ValueError("DATABASE_URL must not be empty.")
    
    url = raw_url.strip()
    
    # SQLite bypass (for testing)
    if url.startswith("sqlite"):
        return url, {"check_same_thread": False}
    
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    connect_args: Dict[str, Any] = {}
    
    # Normalize scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme not in ("postgresql+asyncpg", "postgresql+psycopg"):
        if "postgres" in scheme:
            scheme = "postgresql+asyncpg"
            
    # Extract query parameters
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    
    # Driver-specific SSL handling
    if "asyncpg" in scheme:
        ssl_val = query_params.pop("sslmode", None)
        if ssl_val:
            mode = ssl_val[0].lower()
            if mode in ("require", "prefer", "verify-ca", "verify-full"):
                connect_args["ssl"] = mode
            elif mode in ("disable", "allow", "false", "0"):
                connect_args["ssl"] = False
            else:
                connect_args["ssl"] = mode
        
        # Re-encode query parameters without 'sslmode'
        flat_params = [(k, v) for k, vals in query_params.items() for v in vals]
        new_query = urllib.parse.urlencode(flat_params)
        parsed = parsed._replace(scheme=scheme, query=new_query)
    else:
        parsed = parsed._replace(scheme=scheme)
        
    return parsed.geturl(), connect_args
```

### 3.2 Password Masking for Logging & Exceptions
To adhere to forensic security standards, raw database connection strings containing sensitive credentials must never appear in logs or exception messages:

```python
def sanitize_database_url(url: str) -> str:
    """Masks database password in connection string for secure logging."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return parsed._replace(netloc=netloc).geturl()
        return url
    except Exception:
        return "<sanitized-database-url>"
```

### 3.3 Connection Pooling & Engine Configuration

Per Requirement R1 and PROJECT.md:
- `pool_size = 20`: Baseline persistent connection pool size.
- `max_overflow = 10`: Burst connection buffer allowing up to 30 concurrent connections during peak forensic ingestion bursts.
- `pool_pre_ping = True`: Executes a transparent test (`SELECT 1`) on connection checkout. If a remote connection was dropped (e.g. TigerData idle timeout or network flap), the pool silently recycles it, eliminating `ConnectionResetError`.
- `pool_recycle = 3600`: Forcefully recycles connections every 60 minutes to prevent backend driver state drift or server-side memory leaks.
- `echo = settings.DEBUG`: Verbose SQL logging in development, disabled in production.

#### Handling SQLite Dynamic Engine Adaptations
When running in automated test environments (`sqlite+aiosqlite:///:memory:`):
- Standard `QueuePool` arguments (`pool_size`, `max_overflow`, `pool_recycle`) are unsupported by SQLite.
- SQLite in-memory databases discard tables upon connection close unless `StaticPool` is configured.
- The engine factory dynamically selects the pool class:
  ```python
  from sqlalchemy.pool import StaticPool, QueuePool

  if normalized_url.startswith("sqlite"):
      engine_kwargs = {
          "poolclass": StaticPool,
          "connect_args": connect_args,
      }
  else:
      engine_kwargs = {
          "poolclass": QueuePool,
          "pool_size": settings.DB_POOL_SIZE,
          "max_overflow": settings.DB_MAX_OVERFLOW,
          "pool_pre_ping": settings.DB_POOL_PRE_PING,
          "pool_recycle": settings.DB_POOL_RECYCLE,
          "connect_args": connect_args,
      }
  ```

### 3.4 Async Sessionmaker Configuration
```python
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)
```
**Rationale for `expire_on_commit=False`**:  
In asynchronous SQLAlchemy, accessing attributes on an expired ORM instance triggers an implicit lazy-load query. Because async execution cannot perform implicit I/O outside of an active `await` call, this produces the fatal error:
`sqlalchemy.exc.MissingGreenlet: await_only() can only be called within the greenlet_spawn context`. Setting `expire_on_commit=False` keeps committed instances in memory with their attribute values accessible for API serialization.

### 3.5 Dependency Injection: `get_db()`
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession with managed transaction lifecycle.
    
    - Automatically commits if the request handler succeeds.
    - Safely rolls back changes if an exception occurs.
    - Always closes and returns the connection to the pool.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database sessionmaker is uninitialized. Ensure DATABASE_URL is properly configured."
        )
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

### 3.6 Database Lifecycle Hooks: `init_db()` and `close_db()`

#### `init_db()`
Executed during application startup in `backend/main.py`:
1. Resolves and normalizes `DATABASE_URL`. If empty, emits an informative warning or raises a descriptive error depending on environment.
2. Checks PostgreSQL dialect. If dialect is `postgresql`:
   - Runs `CREATE EXTENSION IF NOT EXISTS vector;`
   - Runs `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
3. If dialect is SQLite, skips extension commands to avoid syntax errors.
4. Executes `await conn.run_sync(Base.metadata.create_all)` to create all tables and indexes.
5. Invokes jurisprudence seed routine (`seed_legal_knowledge(session)`) to populate Mexican AML legal articles if the table is empty.

#### `close_db()`
Executed during application shutdown in `backend/main.py`:
- Calls `await engine.dispose()`, cleanly closing all open sockets and releasing connection pool resources.

---

## 4. Target Relational & Vector Models (`backend/models/forensic.py`)

### 4.1 Base and Universal Type Compatibility
To support both PostgreSQL and SQLite:
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, DateTime, Boolean, Text, ForeignKey, func, Index, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB

# Polymorphic type mappings: JSONB on PostgreSQL, JSON on SQLite
JSONType = JSON().with_variant(PG_JSONB, "postgresql")

class Base(DeclarativeBase):
    pass
```

### 4.2 Model Definitions

#### 1. `InvestigationCase`
Represents an AML forensic investigation case originating from an uploaded CSV file.
```python
class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for the investigation case",
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Forensic Analysis Artifacts (JSONB in Postgres, JSON in SQLite)
    ingestion_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    subgraph: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    patterns: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    verdict: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)

    # Cascade relationship to TransactionRecord
    transactions: Mapped[List["TransactionRecord"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
```

#### 2. `TransactionRecord`
Stores individual transactions associated with a case, indexed for rapid agent tool querying.
```python
class TransactionRecord(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)

    case: Mapped["InvestigationCase"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_case_suspicious", "case_id", "is_suspicious"),
        Index("idx_transactions_origin_dest", "origin", "destination"),
    )
```

#### 3. `LegalArticleVector`
Stores Mexican tax and anti-money laundering legal statutes for semantic vector search by AI agents.
```python
class LegalArticleVector(Base):
    __tablename__ = "legal_knowledge_vectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    article_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    regulatory_body: Mapped[str] = mapped_column(String(32), default="SAT", nullable=False)
    precedent_type: Mapped[str] = mapped_column(String(64), default="Jurisprudencia", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_legal_vectors_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
```

---

## 5. Mexican AML Jurisprudence Seed Data

To fulfill Requirement R1 and enable vector similarity retrieval for Milestone 3, the following 6 legal statutes must be seeded during `init_db()`:

| # | Article Code | Regulatory Body | Precedent Type | Summary of Legal Rule |
|---|---|---|---|---|
| 1 | `CFF-Art-69B` | SAT / SCJN | Jurisprudencia 2a./J. 78/2019 | **Presunción de Inexistencia de Operaciones (EFOS / EDOS)**: Falta de infraestructura, personal o activos para prestar servicios. Exige acreditación de *materialidad* mediante la tríada probatoria: contratos con fecha cierta, entregables tangibles verificables y trazabilidad financiera de flujos bancarios continuos sin retornos circulares. |
| 2 | `LFPIORPI-Art-17` | UIF / SHCP | Ley Federal Anti-Lavado | **Actividades Vulnerables**: Identificación de clientes y reporte de operaciones en blindaje, traslado de valores, metales preciosos, tarjetas de prepago, y activos virtuales. |
| 3 | `LFPIORPI-Art-18` | UIF / SHCP | Obligaciones de Cumplimiento | **Custodia y Reporte**: Custodia obligatoria de expedientes de identificación por 5 años. Presentación de avisos de operaciones vulnerables a más tardar el día 17 del mes inmediato siguiente a la realización del acto. Prohibición expresa de alertamiento (*tipping-off*). |
| 4 | `CFF-Art-108-109` | SAT / Procuraduría Fiscal | Tipificación Penal | **Defraudación Fiscal y Delitos Equiparables**: Utilización de esquemas fraudulentos, deducciones falsas y transferencias sin sustancia económica para ocultar el origen ilícito o evadir contribuciones. |
| 5 | `UIF-DCG-LIC-115` | UIF / CNBV | Disposiciones de Carácter General | **Reporte de Operaciones Inusuales (ROI)**: Envío obligatorio de ROI en un plazo máximo de 24 a 48 horas al detectar divergencia en el perfil transaccional, fraccionamiento intencional (smurfing/pitufeo), o cuentas puente de dispersión inmediata. |
| 6 | `CINIF-NIF-A2` | CINIF / SAT | Postulado Contable | **Postulado de Sustancia Económica**: Prevalencia de la realidad económica y financiera sobre la forma jurídica o instrumental en las transacciones comerciales y contables. |

*Note*: In initial seeding, `embedding` is populated with a synthetic unit vector `[0.0] * 1536` with a leading `1.0` or deterministic normalized seed, allowing queries to run immediately without requiring external embedding API keys during boot.

---

## 6. SQLite Test Mock Compatibility & Resilience Hooks

### 6.1 Compiles Hooks
In testing environments (`sqlite+aiosqlite:///:memory:`):
1. SQLite does not have native support for `vector(1536)` or `jsonb`.
2. Attempting to emit `CREATE TABLE` containing `Vector(1536)` produces an error unless a compiler hook is registered:
   ```python
   from sqlalchemy.ext.compiler import compiles
   from pgvector.sqlalchemy import Vector
   from sqlalchemy.dialects.postgresql import JSONB

   @compiles(Vector, "sqlite")
   def compile_vector_sqlite(type_, compiler, **kw):
       return "TEXT"

   @compiles(JSONB, "sqlite")
   def compile_jsonb_sqlite(type_, compiler, **kw):
       return "JSON"
   ```
3. These hooks compile `Vector` as `TEXT` and `JSONB` as `JSON` on SQLite, permitting `Base.metadata.create_all` to execute cleanly without dialect syntax failures.

### 6.2 `pgvector` Import Fallback Stub
If `pgvector` is not installed in a minimal developer environment, models must not fail on import:
```python
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType
    class Vector(UserDefinedType):  # type: ignore
        def __init__(self, dim: int = 1536):
            self.dim = dim
        def get_col_spec(self, **kw):
            return f"vector({self.dim})"
```

### 6.3 Vector Query Fallback on SQLite
In SQLite tests where the pgvector `<=>` (cosine distance) operator does not exist:
The tool router (Milestone 3) will execute a fallback text search:
```python
if session.bind.dialect.name == "sqlite":
    stmt = select(LegalArticleVector).where(
        LegalArticleVector.content.ilike(f"%{query_text}%")
    ).limit(limit)
```

---

## 7. Configuration & Environment Blueprint

### 7.1 `backend/core/config.py` Additions
```python
    # Database Configuration (TigerData PostgreSQL + pgvector)
    DATABASE_URL: str = ""
    POSTGRES_USER: str = "forensic_user"
    POSTGRES_PASSWORD: str = "forensic_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "forensic_audit_db"
    POSTGRES_SSL_MODE: str = "require"

    # Connection Pool Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    def get_effective_database_url(self) -> str:
        """Returns DATABASE_URL if configured, otherwise assembles from POSTGRES_* attributes."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={self.POSTGRES_SSL_MODE}"
        )
```

### 7.2 `backend/requirements.txt` Additions
```text
sqlalchemy[asyncio]>=2.0.28
asyncpg>=0.29.0
psycopg[binary]>=3.1.18
pgvector>=0.2.5
aiosqlite>=0.20.0
```

### 7.3 `backend/main.py` Lifespan Integration
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print(f"🚀 [Forensic Auditor API] Initialized successfully in {settings.ENVIRONMENT} mode.")
    try:
        from backend.core.database import init_db
        await init_db()
        print("✅ [Database] PostgreSQL schema and extensions initialized successfully.")
    except Exception as exc:
        print(f"⚠️ [Database] Skipped/deferred schema initialization: {exc}")
    yield
    # Teardown / Cleanup
    print("🛑 [Forensic Auditor API] Shutting down.")
    try:
        from backend.core.database import close_db
        await close_db()
        print("✅ [Database] Database connection pool disposed.")
    except Exception as exc:
        print(f"⚠️ [Database] Error during database shutdown: {exc}")
```

---

## 8. Complete Proposed Code Blueprint: `backend/core/database.py`

```python
"""
Database Engine, Connection Pooling & Session Lifecycle Module
Forensic Auditor AML Engine - TigerData PostgreSQL & pgvector Layer
"""

import logging
import urllib.parse
from typing import AsyncGenerator, Dict, Any, Tuple, Optional

from sqlalchemy import text, JSON
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType
    class Vector(UserDefinedType):  # type: ignore
        def __init__(self, dim: int = 1536):
            self.dim = dim
        def get_col_spec(self, **kw):
            return f"vector({self.dim})"

from backend.core.config import settings

logger = logging.getLogger("forensic_auditor.database")

# ---------------------------------------------------------------------------
# Declarative Base & SQLite Compiler Compatibility Hooks
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass

@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# URL Normalization & Sanitization
# ---------------------------------------------------------------------------

def normalize_database_url(raw_url: str) -> Tuple[str, Dict[str, Any]]:
    """Normalizes database URLs, translating driver schemes and SSL parameters."""
    if not raw_url or not raw_url.strip():
        raise ValueError("DATABASE_URL must not be empty.")
    
    url = raw_url.strip()
    if url.startswith("sqlite"):
        return url, {"check_same_thread": False}
    
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    connect_args: Dict[str, Any] = {}
    
    # Scheme normalization
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme not in ("postgresql+asyncpg", "postgresql+psycopg"):
        if "postgres" in scheme:
            scheme = "postgresql+asyncpg"
            
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    
    # Driver-specific SSL parameter translation
    if "asyncpg" in scheme:
        ssl_val = query_params.pop("sslmode", None)
        if ssl_val:
            mode = ssl_val[0].lower()
            if mode in ("require", "prefer", "verify-ca", "verify-full"):
                connect_args["ssl"] = mode
            elif mode in ("disable", "allow", "false", "0"):
                connect_args["ssl"] = False
            else:
                connect_args["ssl"] = mode
        
        flat_params = [(k, v) for k, vals in query_params.items() for v in vals]
        new_query = urllib.parse.urlencode(flat_params)
        parsed = parsed._replace(scheme=scheme, query=new_query)
    else:
        parsed = parsed._replace(scheme=scheme)
        
    return parsed.geturl(), connect_args


def sanitize_database_url(url: str) -> str:
    """Masks database password in connection string for safe diagnostic output."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return parsed._replace(netloc=netloc).geturl()
        return url
    except Exception:
        return "<sanitized-database-url>"


# ---------------------------------------------------------------------------
# Engine & Sessionmaker Creation
# ---------------------------------------------------------------------------

engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def create_engine_and_sessionmaker(url: Optional[str] = None) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Creates an AsyncEngine and configured sessionmaker from configuration."""
    raw_url = url or getattr(settings, "get_effective_database_url", lambda: getattr(settings, "DATABASE_URL", ""))()
    if not raw_url or not raw_url.strip():
        raise RuntimeError(
            "Database configuration error: DATABASE_URL is not set. "
            "Please provide a valid PostgreSQL connection string in .env or environment variables."
        )
    
    normalized_url, connect_args = normalize_database_url(raw_url)
    sanitized = sanitize_database_url(normalized_url)
    logger.info(f"Initializing Async SQLAlchemy engine targeting: {sanitized}")
    
    if normalized_url.startswith("sqlite"):
        new_engine = create_async_engine(
            normalized_url,
            echo=getattr(settings, "DB_ECHO", False),
            poolclass=StaticPool,
            connect_args=connect_args,
        )
    else:
        new_engine = create_async_engine(
            normalized_url,
            echo=getattr(settings, "DB_ECHO", False),
            poolclass=QueuePool,
            pool_size=getattr(settings, "DB_POOL_SIZE", 20),
            max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 10),
            pool_pre_ping=getattr(settings, "DB_POOL_PRE_PING", True),
            pool_recycle=getattr(settings, "DB_POOL_RECYCLE", 3600),
            connect_args=connect_args,
        )
        
    session_factory = async_sessionmaker(
        bind=new_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return new_engine, session_factory


# Initialize module-level engine and sessionmaker if DATABASE_URL is available
try:
    effective_url = getattr(settings, "get_effective_database_url", lambda: getattr(settings, "DATABASE_URL", ""))()
    if effective_url and effective_url.strip():
        engine, AsyncSessionLocal = create_engine_and_sessionmaker(effective_url)
except Exception as e:
    logger.warning(f"Database module-level engine initialization deferred: {e}")


# ---------------------------------------------------------------------------
# Dependency Injection & Lifecycle
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession with managed transaction lifecycle."""
    global AsyncSessionLocal, engine
    if AsyncSessionLocal is None:
        try:
            engine, AsyncSessionLocal = create_engine_and_sessionmaker()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize database session: {exc}. Ensure DATABASE_URL is properly configured."
            ) from exc

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initializes extensions, creates all tables, and seeds initial jurisprudence."""
    global engine, AsyncSessionLocal
    if engine is None:
        engine, AsyncSessionLocal = create_engine_and_sessionmaker()

    # Import models so Base.metadata is fully populated
    import backend.models.forensic  # noqa: F401

    sanitized = sanitize_database_url(str(engine.url))
    logger.info(f"Connecting to database to initialize schema: {sanitized}")

    try:
        async with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            await conn.run_sync(Base.metadata.create_all)
            
        # Seed legal jurisprudence data
        if AsyncSessionLocal is not None:
            async with AsyncSessionLocal() as session:
                from backend.models.forensic import seed_legal_knowledge
                await seed_legal_knowledge(session)
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        raise RuntimeError(
            f"Failed to initialize database at '{sanitized}'. Verify host connectivity, "
            f"credentials, and pgvector extension availability. Error: {exc}"
        ) from exc


async def close_db() -> None:
    """Disposes the async engine and terminates connection pool."""
    global engine
    if engine is not None:
        await engine.dispose()
        logger.info("Database engine disposed successfully.")
```

---

## 9. Verification & Invalidation Conditions

### 9.1 Verification Checklist for Builder
1. **URL Normalization Tests**:
   - `postgresql://user:pass@host:5432/db?sslmode=require` $\rightarrow$ `postgresql+asyncpg://user:pass@host:5432/db` with `connect_args={'ssl': 'require'}`.
   - `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` $\rightarrow$ preserves query parameter.
   - `sqlite+aiosqlite:///:memory:` $\rightarrow$ preserved untouched with `check_same_thread=False`.
2. **Session Lifecycle Verification**:
   - Successful route commit verification.
   - Exception rollback verification (no dirty state leaks).
   - `session.close()` invocation verified via connection pool return.
3. **Schema & Model Verification**:
   - `Base.metadata.create_all` creates `investigation_cases`, `transactions`, and `legal_knowledge_vectors`.
   - Seed function inserts 6 Mexican AML articles without duplicates (`ON CONFLICT DO NOTHING` or check existing count).
4. **SQLite Test Mock Verification**:
   - Running `pytest` against an in-memory SQLite URL with `@compiles` hook succeeds with 0 errors.

### 9.2 Invalidation Conditions
- Any attempt to pass `sslmode=require` in the query string of an `asyncpg` URL will cause an immediate `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
- Omitting `expire_on_commit=False` in `async_sessionmaker` will cause `MissingGreenlet` exceptions upon accessing entity attributes after commit.
- Omitting `StaticPool` on SQLite in-memory tests will cause tables created in `init_db` to vanish in subsequent queries.
