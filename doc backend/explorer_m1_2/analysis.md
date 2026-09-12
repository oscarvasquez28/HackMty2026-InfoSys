# Milestone 1 Technical Analysis: Configuration, Dependencies & Lifespan Integration

**Author**: Explorer Subagent `explorer_m1_2`  
**Working Directory**: `.agents/explorer_m1_2`  
**Milestone**: M1 — Configuration, Dependencies & Lifespan Integration  
**Date**: 2026-09-12  

---

## 1. Executive Summary & Scope

Milestone 1 establishes the production-grade async persistence layer for the Forensic Auditor backend connecting to TigerData PostgreSQL with `pgvector`. This subagent investigation specifically addresses the foundation layer:
1. **Dependency Specification (`backend/requirements.txt`)**: Declaring async SQLAlchemy 2.0, PostgreSQL drivers (`asyncpg`, `psycopg[binary]`), vector support (`pgvector`), async coroutine runtime (`greenlet`), and isolated test driver (`aiosqlite`).
2. **Typed Application Settings (`backend/core/config.py`)**: Adding database connection string (`DATABASE_URL`), connection pooling limits (`DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=10`), connection health pre-ping (`DB_POOL_PRE_PING=True`), connection recycle timeout (`DB_POOL_RECYCLE=3600`), and SSL enforcement flag (`DB_SSL_REQUIRE=True`).
3. **Application Lifespan Context Manager (`backend/main.py`)**: Wiring database startup (`init_db()`) and shutdown (`close_db()`) lifecycle hooks into FastAPI's `lifespan` manager, wrapped in defensive exception handlers so that missing database configurations or offline test environments do not crash the service.

---

## 2. Current State Assessment

### 2.1 Dependency Inventory (`backend/requirements.txt`)
Currently contains 10 baseline packages (lines 1–10):
```txt
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
*Gap Identified*: Lacks any database ORM or driver dependencies. Attempting to use SQLAlchemy, connect to TigerData PostgreSQL, or run vector queries fails with `ModuleNotFoundError`.

### 2.2 Application Settings (`backend/core/config.py`)
Lines 1–55 define `Settings(BaseSettings)` with CORS origins, external integrations (`N8N_WEBHOOK_URL`, `ELEVENLABS_*`), and graph pruning thresholds (`MAX_CYCLE_LENGTH`, `PASS_THROUGH_*`).
*Gap Identified*: No database attributes exist on `Settings`. Downstream modules cannot load `DATABASE_URL` from `.env` or container environment variables, nor can they configure connection pool parameters dynamically.

### 2.3 Application Lifespan (`backend/main.py`)
Lines 10–17 define a stub lifespan context manager:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print(f"🚀 [Forensic Auditor API] Initialized successfully in {settings.ENVIRONMENT} mode.")
    yield
    # Teardown / Cleanup
    print("🛑 [Forensic Auditor API] Shutting down.")
```
*Gap Identified*: Neither `init_db()` nor `close_db()` is called. Consequently:
- Schema and tables are not initialized on application start.
- Vector extensions (`CREATE EXTENSION IF NOT EXISTS vector`) are not ensured.
- Connection pools are not gracefully disposed on application termination, risking leaked socket connections on TigerData PostgreSQL.
- Crucially, if lifespan is implemented naively without defensive error catching, tests using `httpx.ASGITransport(app=app)` without a configured PostgreSQL instance will crash on startup.

---

## 3. Detailed Specifications & Proposed Diffs

### 3.1 `backend/requirements.txt`

#### Required Additions
| Package | Version Constraint | Justification |
| :--- | :--- | :--- |
| `sqlalchemy[asyncio]` | `>=2.0.28` | Core ORM and async engine interface (`AsyncEngine`, `AsyncSession`, `async_sessionmaker`, mapped models). |
| `asyncpg` | `>=0.29.0` | High-performance asynchronous PostgreSQL driver for Python. |
| `psycopg[binary]` | `>=3.1.18` | Official PostgreSQL 3 driver with pre-compiled C binaries supporting async connections and broad TLS/SSL options. |
| `pgvector` | `>=0.2.5` | Native PostgreSQL vector extension integration for SQLAlchemy, providing the `Vector(1536)` column type and similarity operators (`<=>`). |
| `greenlet` | `>=3.0.3` | Required runtime dependency for SQLAlchemy's async extension to enable coroutine-based execution of ORM operations. |
| `aiosqlite` | `>=0.20.0` | Async SQLite driver enabling zero-dependency, ultra-fast in-memory test suites (`sqlite+aiosqlite:///:memory:`). |

#### Proposed Content (`backend/requirements.txt`)
```txt
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
sqlalchemy[asyncio]>=2.0.28
asyncpg>=0.29.0
psycopg[binary]>=3.1.18
pgvector>=0.2.5
greenlet>=3.0.3
aiosqlite>=0.20.0
```

#### Unified Diff
```diff
--- a/backend/requirements.txt
+++ b/backend/requirements.txt
@@ -8,3 +8,9 @@
 pytest>=8.0.0
 pytest-asyncio>=0.23.0
 python-multipart>=0.0.9
+sqlalchemy[asyncio]>=2.0.28
+asyncpg>=0.29.0
+psycopg[binary]>=3.1.18
+pgvector>=0.2.5
+greenlet>=3.0.3
+aiosqlite>=0.20.0
```

---

### 3.2 `backend/core/config.py`

#### Required Additions
1. Import `Optional` from `typing`:
   ```python
   from typing import List, Optional, Union
   ```
2. Add typed database configuration attributes to `Settings`:
   ```python
       # Database Configuration (TigerData PostgreSQL + pgvector)
       DATABASE_URL: Optional[str] = None
       DB_POOL_SIZE: int = 20
       DB_MAX_OVERFLOW: int = 10
       DB_POOL_PRE_PING: bool = True
       DB_POOL_RECYCLE: int = 3600
       DB_SSL_REQUIRE: bool = True
   ```
3. Add a field validator for `DATABASE_URL` to sanitize blank strings (`""` or `"  "`) to `None`, preventing invalid connection string errors when `.env` contains an empty key:
   ```python
       @field_validator("DATABASE_URL", mode="before")
       @classmethod
       def assemble_database_url(cls, v: Optional[str]) -> Optional[str]:
           if isinstance(v, str):
               v_stripped = v.strip()
               return v_stripped if v_stripped else None
           return v
   ```

#### Proposed Full Content (`backend/core/config.py`)
```python
import json
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Forensic Auditor AML Engine"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS origins
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # Database Configuration (TigerData PostgreSQL + pgvector)
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE: int = 3600
    DB_SSL_REQUIRE: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return v

    # External Integrations
    N8N_WEBHOOK_URL: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Default Voice ID (Rachel)
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"

    # Algorithmic Graph Thresholds
    MAX_CYCLE_LENGTH: int = 5
    PASS_THROUGH_RATIO_THRESHOLD: float = 0.90
    PASS_THROUGH_WINDOW_HOURS: float = 48.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
```

#### Unified Diff
```diff
--- a/backend/core/config.py
+++ b/backend/core/config.py
@@ -1,5 +1,5 @@
 import json
-from typing import List, Union
+from typing import List, Optional, Union
 from pydantic import field_validator
 from pydantic_settings import BaseSettings, SettingsConfigDict
 
@@ -34,6 +34,22 @@
         return ["*"]
 
+    # Database Configuration (TigerData PostgreSQL + pgvector)
+    DATABASE_URL: Optional[str] = None
+    DB_POOL_SIZE: int = 20
+    DB_MAX_OVERFLOW: int = 10
+    DB_POOL_PRE_PING: bool = True
+    DB_POOL_RECYCLE: int = 3600
+    DB_SSL_REQUIRE: bool = True
+
+    @field_validator("DATABASE_URL", mode="before")
+    @classmethod
+    def assemble_database_url(cls, v: Optional[str]) -> Optional[str]:
+        if isinstance(v, str):
+            v_stripped = v.strip()
+            return v_stripped if v_stripped else None
+        return v
+
     # External Integrations
     N8N_WEBHOOK_URL: str = ""
     ELEVENLABS_API_KEY: str = ""
```

---

### 3.3 `backend/main.py`

#### Required Additions
1. Safe import of `init_db` and `close_db` from `backend.core.database`. Using a `try...except ImportError:` block ensures that if `main.py` is loaded before `backend/core/database.py` is created or in minimal sub-environments, it does not fail on import.
2. Lifespan startup hook:
   - Call `await init_db()` when `init_db` is available.
   - Guard with `try...except Exception as exc:` to catch and log operational connection failures (e.g. host unreachable, missing credentials) as warnings, enabling offline/demo mode and local integration tests to run without aborting the process.
3. Lifespan teardown hook:
   - Call `await close_db()` when `close_db` is available.
   - Guard with `try...except Exception as exc:` to cleanly catch pool cleanup errors.
4. Keep the `/health` endpoint and CORS configurations untouched to maintain 100% test compatibility.

#### Proposed Full Content (`backend/main.py`)
```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.api.routes.investigations import router as investigations_router
from backend.api.routes.tts import router as tts_router

logger = logging.getLogger(__name__)

# Safe import of database lifecycle hooks
try:
    from backend.core.database import init_db, close_db
except ImportError:
    init_db = None  # type: ignore
    close_db = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print(f"🚀 [Forensic Auditor API] Initialized successfully in {settings.ENVIRONMENT} mode.")
    
    # Initialize Database if hooks are available
    if init_db is not None:
        try:
            await init_db()
            print("📦 [Database] Database initialization completed successfully.")
        except Exception as exc:
            print(f"⚠️ [Database] Startup connection warning: {exc}. Running without active DB connection.")
            logger.warning("Database startup initialization failed: %s", exc)
    else:
        print("ℹ️ [Database] Database lifecycle hooks not yet loaded.")

    yield

    # Teardown / Cleanup
    if close_db is not None:
        try:
            await close_db()
            print("🛑 [Database] Database connections closed cleanly.")
        except Exception as exc:
            print(f"⚠️ [Database] Shutdown warning: {exc}")
            logger.warning("Database close_db error: %s", exc)

    print("🛑 [Forensic Auditor API] Shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="High-performance Forensic AML Engine with deterministic graph pruning, SSE thoughts streaming, and ElevenLabs TTS proxy.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(investigations_router, prefix=settings.API_V1_STR)
app.include_router(tts_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestrators and monitoring."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
```

#### Unified Diff
```diff
--- a/backend/main.py
+++ b/backend/main.py
@@ -1,18 +1,45 @@
+import logging
 from contextlib import asynccontextmanager
 from fastapi import FastAPI
 from fastapi.middleware.cors import CORSMiddleware
 
 from backend.core.config import settings
 from backend.api.routes.investigations import router as investigations_router
 from backend.api.routes.tts import router as tts_router
 
+logger = logging.getLogger(__name__)
+
+# Safe import of database lifecycle hooks
+try:
+    from backend.core.database import init_db, close_db
+except ImportError:
+    init_db = None  # type: ignore
+    close_db = None  # type: ignore
+
 
 @asynccontextmanager
 async def lifespan(app: FastAPI):
     # Startup initialization
     print(f"🚀 [Forensic Auditor API] Initialized successfully in {settings.ENVIRONMENT} mode.")
+    
+    # Initialize Database if hooks are available
+    if init_db is not None:
+        try:
+            await init_db()
+            print("📦 [Database] Database initialization completed successfully.")
+        except Exception as exc:
+            print(f"⚠️ [Database] Startup connection warning: {exc}. Running without active DB connection.")
+            logger.warning("Database startup initialization failed: %s", exc)
+    else:
+        print("ℹ️ [Database] Database lifecycle hooks not yet loaded.")
+
     yield
+
     # Teardown / Cleanup
+    if close_db is not None:
+        try:
+            await close_db()
+            print("🛑 [Database] Database connections closed cleanly.")
+        except Exception as exc:
+            print(f"⚠️ [Database] Shutdown warning: {exc}")
+            logger.warning("Database close_db error: %s", exc)
+
     print("🛑 [Forensic Auditor API] Shutting down.")
```

---

## 4. Cross-Module Architectural Interactions

```
                +---------------------------------------+
                |           .env / Environment          |
                |  DATABASE_URL=postgresql+psycopg://...|
                +-------------------+-------------------+
                                    |
                                    v
                +---------------------------------------+
                |        backend/core/config.py         |
                | - DATABASE_URL: Optional[str]         |
                | - DB_POOL_SIZE: int = 20              |
                | - DB_MAX_OVERFLOW: int = 10           |
                | - DB_POOL_PRE_PING: bool = True       |
                | - DB_POOL_RECYCLE: int = 3600         |
                | - DB_SSL_REQUIRE: bool = True         |
                +-------------------+-------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-------------------------------+               +-------------------------------+
|    backend/core/database.py   |               |        backend/main.py        |
| - create_async_engine(...)    | <-----------> | - lifespan(app):              |
| - AsyncSessionLocal           | (init_db,     |   * await init_db()           |
| - async def init_db()         |  close_db)    |   * yield                     |
| - async def close_db()        |               |   * await close_db()          |
| - async def get_db()          |               +-------------------------------+
+---------------+---------------+
                |
                v
+-------------------------------+
|  backend/models/forensic.py   |
| - InvestigationCase           |
| - TransactionRecord           |
| - LegalArticleVector          |
+-------------------------------+
```

### 4.1 Interface Contract with `backend/core/database.py`
`backend/core/database.py` (being investigated by peer `explorer_m1_1`) relies on the settings exposed by `backend/core/config.py`:
- `settings.DATABASE_URL`: Primary connection URI.
- `settings.DB_POOL_SIZE`, `settings.DB_MAX_OVERFLOW`, `settings.DB_POOL_PRE_PING`, `settings.DB_POOL_RECYCLE`: Used as kwargs in `create_async_engine()`.
- `settings.DB_SSL_REQUIRE`: Used to ensure TLS encryption. When driver is `asyncpg`, this is passed via `connect_args={"ssl": "require"}`. When driver is `psycopg`, this is passed via URL query parameter `?sslmode=require`.

### 4.2 Error Boundary & Offline/Test Resilience
In automated test suites (`backend/tests/test_pipeline.py`) or offline CI environments:
- If `DATABASE_URL` is omitted, `settings.DATABASE_URL` evaluates to `None`.
- `init_db()` should check `if not settings.DATABASE_URL: return`.
- Even if `init_db()` raises an operational connection exception (e.g. DNS failure contacting remote TigerData), `lifespan` in `backend/main.py` catches `Exception as exc`, logs a descriptive warning, and continues startup.
- This ensures that non-database endpoints (`/health`, synthetic pipeline tests, `/tts/synthesize`) remain completely operational without requiring a live remote database cluster.

---

## 5. Verification Protocol

The builder agent and test runner can verify these changes using the following automated commands:

1. **Syntax and Static Compilation**:
   ```bash
   python -m py_compile backend/core/config.py backend/main.py
   ```
   *Expected Output*: Exit code 0, no syntax errors.

2. **Configuration Settings Verification**:
   ```bash
   python -c "from backend.core.config import settings; print(f'DB_POOL_SIZE={settings.DB_POOL_SIZE}, SSL={settings.DB_SSL_REQUIRE}, URL={settings.DATABASE_URL}')"
   ```
   *Expected Output*: `DB_POOL_SIZE=20, SSL=True, URL=None` (or configured value).

3. **Sanitization Validator Verification**:
   ```bash
   python -c "from backend.core.config import Settings; s = Settings(DATABASE_URL='   '); assert s.DATABASE_URL is None; print('Validator passed')"
   ```
   *Expected Output*: `Validator passed`.

4. **Lifespan Startup & Teardown Execution (Graceful Fallback)**:
   ```bash
   python -c "import asyncio; from backend.main import app, lifespan; asyncio.run((lambda: [lifespan(app).__aenter__(), lifespan(app).__aexit__(None, None, None)][0])())"
   ```
   *Expected Output*: Displays startup banner, initialization log, and cleanly completes teardown without unhandled exceptions.

5. **Existing Pipeline Test Regression Check**:
   ```bash
   pytest backend/tests/test_pipeline.py -v
   ```
   *Expected Output*: All tests in `test_pipeline.py` pass cleanly.
