# Forensic Auditor Backend: Integration, Dependencies, Database, and Testing Analysis

**Agent**: `explorer_survey_2`  
**Date**: 2026-09-12  
**Scope**: TigerData PostgreSQL, SSL, async drivers, pgvector, environment variables, n8n agent tools & dynamic query builder, and testing architecture.

---

## 1. Executive Summary

The Forensic Auditor AML Engine requires upgrading from an in-memory dictionary store (`INVESTIGATION_CASES` in `backend/api/routes/investigations.py:17`) to an enterprise-grade async persistence layer backed by **TigerData PostgreSQL 16 with `pgvector`**, while exposing an extensible suite of **n8n AI Agent Tools** and hardening the test suite.

This report delivers the technical specifications, architectural decisions, contract schemas, and testing strategies required for implementation across:
1. **TigerData PostgreSQL Connection & Driver Architecture**: Choosing between `postgresql+asyncpg` and `postgresql+psycopg`, configuring mandatory SSL (`sslmode=require`), connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`), `pgvector` 1536-dimensional HNSW index, and graceful `get_db` lifecycle handling.
2. **Environment Variable Configuration**: Complete audit across `.env`, `backend/core/config.py`, and test environments.
3. **n8n Agent Tools & Dynamic Query Builder**: Complete endpoint contracts for `/transactions`, `/entities`, `/patterns`, `/legal-precedents`, and the composable `/query` builder with an extensible handler registry.
4. **Testing Architecture**: Zero-regression strategy for testing async DB operations on SQLite (`sqlite+aiosqlite:///:memory:`) using custom SQLAlchemy `@compiles(Vector, "sqlite")` type compilation, SSE thought/verdict streaming, CSV ingestion edge cases, and ElevenLabs audio fallback.

---

## 2. Database Connection Architecture & Requirements

### 2.1 TigerData PostgreSQL & SSL Enforcement

TigerData is a remote managed PostgreSQL 16 service. Connecting over the public internet or container networks requires mandatory Transport Layer Security (TLS/SSL).

- **SSL Requirement**: `sslmode=require` must be enforced to prevent unencrypted transmissions of sensitive AML financial transactions and cases.
- **Connection URI Format**:
  ```text
  postgresql+asyncpg://<username>:<password>@<tigerdata-host>:5432/<database>?ssl=require
  ```
  or for psycopg:
  ```text
  postgresql+psycopg://<username>:<password>@<tigerdata-host>:5432/<database>?sslmode=require
  ```

### 2.2 Async Driver Comparison: `asyncpg` vs `psycopg` (psycopg 3)

SQLAlchemy 2.0 supports two primary async PostgreSQL drivers:

| Feature / Criteria | `asyncpg` (`postgresql+asyncpg`) | `psycopg` 3 (`postgresql+psycopg`) |
|---|---|---|
| **Underlying Engine** | Native Cython async protocol implementation (no `libpq`) | Native `libpq` C/Python bindings (`psycopg-c`) |
| **Throughput & Speed** | Highest raw throughput (2x-3x in benchmarks) | High throughput, close to asyncpg |
| **SSL Parameter Support** | Requires `connect_args={"ssl": "require"}` or URL `?ssl=require` (older versions rejected `sslmode` keyword) | Fully honors libpq connection parameters including `?sslmode=require` |
| **pgvector Compatibility** | Supported via `pgvector.asyncpg` and `pgvector.sqlalchemy` | Supported via `pgvector.psycopg` and `pgvector.sqlalchemy` |
| **Type Normalization** | Strict on type casting (requires exact PostgreSQL types) | Flexible type conversions matching standard libpq |
| **FastAPI Ecosystem** | De facto standard driver for async FastAPI + SQLAlchemy | Growing standard; official Postgres driver |

#### Recommendation
Support **both** drivers seamlessly by building the engine factory to parse `DATABASE_URL`. Default to `postgresql+asyncpg` for maximum asynchronous event loop performance.
To handle `sslmode=require` across both drivers without runtime errors, implement SSL parameter translation in `backend/core/database.py`:
```python
def get_connect_args(url: str) -> dict:
    connect_args = {}
    if "asyncpg" in url:
        # asyncpg accepts ssl="require" or SSLContext
        if "sslmode=require" in url or "ssl=require" in url or settings.DB_SSL_REQUIRE:
            connect_args["ssl"] = "require"
    elif "psycopg" in url:
        if settings.DB_SSL_REQUIRE:
            connect_args["sslmode"] = "require"
    return connect_args
```

### 2.3 Connection Pooling Parameters

Cloud PostgreSQL connections to TigerData can be terminated by cloud firewalls or network timeouts during idle periods. Connection pooling must be configured in `create_async_engine`:

- `pool_size = 20`: Base pool of persistent database connections per worker process.
- `max_overflow = 10`: Burst buffer allowing up to 30 concurrent connections during high-throughput ingestion spikes.
- `pool_pre_ping = True`: Executes a lightweight `SELECT 1` ping before handing a checked-out connection to the application. This eliminates `ConnectionResetError` / `server closed the connection unexpectedly`.
- `pool_recycle = 3600`: Recycles connections older than 1 hour to release stale socket allocations.

> **Testing Divergence**: When testing against in-memory SQLite (`sqlite+aiosqlite:///:memory:`), SQLite does not support `pool_size` or `max_overflow`. The engine factory must conditionally use `StaticPool` or `NullPool` when `url.startswith("sqlite")`.

### 2.4 pgvector Extension & Relational Schema Design

The TigerData instance must run with the `pgvector` extension enabled:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

#### Schema Specifications (`backend/models/forensic.py`)

1. **`InvestigationCase` (`investigation_cases`)**:
   - `id`: `UUID` (PK, default `uuid.uuid4`).
   - `filename`: `String(255)` (name of uploaded CSV).
   - `status`: `String(50)` (e.g., `"PROCESSED"`, `"IN_REVIEW"`, `"COMPLETED"`, `"FAILED"`).
   - `created_at`: `DateTime(timezone=True)`.
   - `updated_at`: `DateTime(timezone=True)`.
   - `ingestion_metadata`: `JSONB` (summary records, total volume, unique accounts).
   - `metrics`: `JSONB` (total nodes/edges, pruned counts, efficiency pct, suspicious volume).
   - `subgraph`: `JSONB` (pruned suspicious nodes and edges).
   - `patterns`: `JSONB` (detected cycles and pass-through mule accounts).
   - `verdict`: `JSONB` (final legal recommendation, risk score, confidence, audit text). Nullable until stream completes.
   - Relationship: `transactions` -> list of `TransactionRecord` (cascade `"all, delete-orphan"`).

2. **`TransactionRecord` (`transactions`)**:
   - `id`: `Integer` (PK, autoincrement) or `BigInteger`.
   - `case_id`: `UUID` (FK to `investigation_cases.id`, `ondelete="CASCADE"`, indexed).
   - `origin`: `String(128)` (indexed).
   - `destination`: `String(128)` (indexed).
   - `amount`: `Float` (indexed).
   - `timestamp`: `Float` (indexed).
   - `is_suspicious`: `Boolean` (default `False`, indexed).
   - `reasons`: `JSONB` (e.g., `["CYCLE_STEP"]`, `["PASSTHROUGH_BRIDGE"]`).

3. **`LegalArticleVector` (`legal_knowledge_vectors`)**:
   - `id`: `Integer` (PK, autoincrement).
   - `article_code`: `String(64)` (e.g., `"CFF-69B"`, `"LFPIORPI-ART-17"`).
   - `law_name`: `String(255)` (e.g., `"Código Fiscal de la Federación Art. 69-B"`).
   - `content`: `Text` (full jurisprudence text).
   - `embedding`: `Vector(1536)` (vector embedding for cosine similarity).
   - Index: HNSW index on `embedding` with cosine distance operator:
     ```python
     Index(
         "ix_legal_knowledge_vectors_embedding_hnsw",
         "embedding",
         postgresql_using="hnsw",
         postgresql_with={"m": 16, "ef_construction": 64},
         postgresql_ops={"embedding": "vector_cosine_ops"}
     )
     ```

### 2.5 Database Session Management (`get_db`)

FastAPI dependency in `backend/core/database.py`:
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured. Set DATABASE_URL in .env to connect to TigerData PostgreSQL."
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

---

## 3. Environment Variable Audit & Configuration Mapping

### 3.1 Environment Variable Matrix

The following environment variables must be defined across `.env`, parsed by `backend/core/config.py`, and handled during testing:

| Variable | Type | Default | Required In | Purpose |
|---|---|---|---|---|
| `PROJECT_NAME` | `str` | `"Forensic Auditor AML Engine"` | All | OpenAPI title & system identity |
| `API_V1_STR` | `str` | `"/api/v1"` | All | URL prefix for V1 routers |
| `ENVIRONMENT` | `str` | `"development"` | All | Environment mode (`development`, `production`, `test`) |
| `DEBUG` | `bool` | `True` | Dev | Verbose error logging & Swagger docs |
| `BACKEND_CORS_ORIGINS` | `Union[List[str], str]` | `["http://localhost:3000", ...]` | All | Frontend CORS whitelist |
| `DATABASE_URL` | `Optional[str]` | `None` | Prod/TigerData | Primary SQLAlchemy async connection string |
| `DB_POOL_SIZE` | `int` | `20` | Prod/TigerData | Connection pool base size |
| `DB_MAX_OVERFLOW` | `int` | `10` | Prod/TigerData | Connection pool overflow capacity |
| `DB_POOL_PRE_PING` | `bool` | `True` | Prod/TigerData | Pre-ping validation before checkout |
| `DB_POOL_RECYCLE` | `int` | `3600` | Prod/TigerData | Connection recycle interval in seconds |
| `DB_SSL_REQUIRE` | `bool` | `True` | Prod/TigerData | Forces SSL parameter on connections |
| `N8N_WEBHOOK_URL` | `str` | `""` | Optional | External n8n agent reasoning webhook |
| `ELEVENLABS_API_KEY` | `str` | `""` | Optional | Speech synthesis API key (silent MP3 fallback if absent) |
| `ELEVENLABS_VOICE_ID` | `str` | `"21m00Tcm4TlvDq8ikWAM"` | Optional | Rachel voice ID |
| `ELEVENLABS_MODEL_ID` | `str` | `"eleven_multilingual_v2"` | Optional | Multilingual voice model |
| `MAX_CYCLE_LENGTH` | `int` | `5` | All | Upper limit on cycle path length for graph filter |
| `PASS_THROUGH_RATIO_THRESHOLD` | `float` | `0.90` | All | Mule retention ratio threshold ($\ge 90\%$) |
| `PASS_THROUGH_WINDOW_HOURS` | `float` | `48.0` | All | Mule temporal velocity window |

### 3.2 Required Updates to `backend/core/config.py`

`backend/core/config.py` currently lacks database settings. The following fields must be added:
```python
# Database Settings
DATABASE_URL: Optional[str] = None
DB_POOL_SIZE: int = 20
DB_MAX_OVERFLOW: int = 10
DB_POOL_PRE_PING: bool = True
DB_POOL_RECYCLE: int = 3600
DB_SSL_REQUIRE: bool = False
```

### 3.3 Dependencies to Add to `backend/requirements.txt`

The current `requirements.txt` contains only 11 packages (no SQLAlchemy or DB drivers). The following dependencies are required:
```text
sqlalchemy[asyncio]>=2.0.28
asyncpg>=0.29.0
psycopg[binary]>=3.1.18
pgvector>=0.2.5
greenlet>=3.0.3
aiosqlite>=0.20.0
```

---

## 4. n8n Agent Tools Requirements & Dynamic Query Builder Architecture

Requirement R3 specifies creating a versioned agent tool router at `backend/api/routes/agent_tools.py` mounted at `/api/v1/tools` in `backend/main.py`.

### 4.1 Dedicated Tool Endpoints & Contracts

#### 1. `POST /api/v1/tools/transactions`
- **Purpose**: Filter case transactions by origin, destination, account, amount range, time window, and suspicion flag.
- **Request Payload**:
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "origin": "ACC_A",
    "destination": "ACC_B",
    "account": "ACC_B",
    "min_amount": 10000.0,
    "max_amount": 500000.0,
    "start_time": 0.0,
    "end_time": 100.0,
    "is_suspicious": true,
    "limit": 50,
    "offset": 0
  }
  ```
- **Response Payload**: `200 OK`
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "total_count": 1,
    "limit": 50,
    "offset": 0,
    "transactions": [
      {
        "id": 1,
        "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
        "origin": "ACC_A",
        "destination": "ACC_B",
        "amount": 150000.0,
        "timestamp": 1.0,
        "is_suspicious": true,
        "reasons": ["CYCLE_STEP"]
      }
    ]
  }
  ```

#### 2. `POST /api/v1/tools/entities`
- **Purpose**: Retrieve topological entity profiles (volumes, in/out degrees, assigned risk scores, reasons).
- **Request Payload**:
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "account_ids": ["ACC_A", "MULE_01"],
    "min_risk_score": 0.7,
    "limit": 50,
    "offset": 0
  }
  ```
- **Response Payload**: `200 OK`
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "total_count": 2,
    "entities": [
      {
        "id": "ACC_A",
        "total_in": 145000.0,
        "total_out": 150000.0,
        "in_degree": 1,
        "out_degree": 1,
        "reasons": ["CIRCULAR_FLOW_CYCLE"],
        "risk_score": 0.8
      }
    ]
  }
  ```

#### 3. `POST /api/v1/tools/patterns`
- **Purpose**: Retrieve detected elementary cycles and rapid pass-through mule account metrics.
- **Request Payload**:
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
    "pattern_type": "all",
    "min_cycle_length": 2,
    "max_cycle_length": 5,
    "min_volume": 100000.0,
    "account": "ACC_A"
  }
  ```
- **Response Payload**: `200 OK`
  ```json
  {
    "case_id": "8f3b204e-2895-4680-bc90-9ceba694e207",
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
    },
    "summary": {
      "cycles_count": 1,
      "passthrough_count": 1
    }
  }
  ```

#### 4. `POST /api/v1/tools/legal-precedents`
- **Purpose**: Cosine similarity vector search against `legal_knowledge_vectors` using `pgvector` with text fallback.
- **Request Payload**:
  ```json
  {
    "query_text": "operaciones simuladas y empresas fantasma articulo 69 b",
    "query_vector": [0.012, -0.045, ...],
    "law_name": "CFF Art. 69-B",
    "top_k": 5,
    "min_similarity": 0.70
  }
  ```
- **Response Payload**: `200 OK`
  ```json
  {
    "total_count": 1,
    "precedents": [
      {
        "article_code": "CFF-69B",
        "law_name": "Código Fiscal de la Federación - Artículo 69-B",
        "content": "Las autoridades fiscales presumirán la inexistencia de las operaciones amparadas...",
        "similarity": 0.895
      }
    ]
  }
  ```

### 4.2 Dynamic Query Builder & Extensible Handler Registry Pattern

#### Endpoint: `POST /api/v1/tools/query`

Allows external n8n AI agents to compose structured JSON queries without requiring schema modifications.

#### Request Schema:
```python
class QueryFilter(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "like"]
    value: Any

class QuerySort(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"

class DynamicQueryRequest(BaseModel):
    case_id: uuid.UUID
    target: Literal["transactions", "entities", "cycles", "passthrough"]
    filters: List[QueryFilter] = []
    sort: Optional[QuerySort] = None
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
```

#### Registry Architecture:
```python
class BaseToolHandler(ABC):
    @abstractmethod
    async def execute(self, session: AsyncSession, request: DynamicQueryRequest) -> Dict[str, Any]:
        pass

class ToolRegistry:
    _handlers: Dict[str, BaseToolHandler] = {}

    @classmethod
    def register(cls, target: str):
        def decorator(handler_cls):
            cls._handlers[target] = handler_cls()
            return handler_cls
        return decorator

    @classmethod
    def get_handler(cls, target: str) -> BaseToolHandler:
        if target not in cls._handlers:
            raise ValueError(f"Target '{target}' is not supported. Valid targets: {list(cls._handlers.keys())}")
        return cls._handlers[target]
```

#### SQL Injection Defense:
1. **Target Whitelisting**: Handlers are registered only for approved targets (`transactions`, `entities`, `cycles`, `passthrough`).
2. **Column Whitelisting**: For relational tables (`transactions`), allowed filter columns are strictly whitelisted: `{"id", "origin", "destination", "amount", "timestamp", "is_suspicious"}`.
3. **Mandatory Case Scoping**: Every query strictly enforces `case_id == request.case_id`, preventing cross-tenant or cross-case data leakage.
4. **Parameterized Compilation**: Dynamic conditions are translated directly to SQLAlchemy binary expressions (`Column == value`, `Column >= value`, etc.) — zero string concatenation.

---

## 5. Comprehensive Testing Strategy

### 5.1 Testing Async Database Operations with SQLite & Mocking

Testing async SQLAlchemy operations locally without requiring a live TigerData cluster:
- **Test Engine**: `sqlite+aiosqlite:///:memory:` with `StaticPool` and `connect_args={"check_same_thread": False}`.
- **pgvector SQLite Incompatibility Workaround**: SQLite does not support `Vector(1536)`. If tables are created via `Base.metadata.create_all`, SQLAlchemy raises a `CompileError`.
  **Solution**: Register a custom compiler hook for SQLite in test setup:
  ```python
  from sqlalchemy.ext.compiler import compiles
  from pgvector.sqlalchemy import Vector

  @compiles(Vector, "sqlite")
  def compile_vector_sqlite(type_, compiler, **kw):
      return "TEXT"
  ```
  This allows SQLite to create tables containing `Vector` columns as standard `TEXT` fields.
- **Dependency Override**:
  Use `app.dependency_overrides[get_db] = override_get_db` in test fixtures so the FastAPI routes transparently use the in-memory test database.

### 5.2 Testing SSE Streaming & Verdict Persistence

1. Upload CSV to generate `case_id`.
2. Connect to `GET /api/v1/investigations/{case_id}/stream` using `httpx.AsyncClient` with `client.stream("GET", ...)`.
3. Parse and assert at least 5 `thought` events.
4. Parse and assert the terminal `verdict` event.
5. **Critical Persistence Verification**: Query the database for `InvestigationCase` with `case_id`:
   - Assert `case.status == "COMPLETED"`.
   - Assert `case.verdict is not None`.
   - Assert `case.verdict["confidence_score"] > 0.8`.

### 5.3 Testing CSV Ingestion & Edge Cases

Test suite additions:
1. **Standard Flow**: Valid AMLSim format with cycles and mules $\to$ HTTP 201, verify rows in `transactions` table.
2. **Alias Resolution**: CSV using `nameOrig`, `nameDest`, `monto`, `step` $\to$ parsed correctly.
3. **Missing Columns**: CSV lacking amount or origin column $\to$ HTTP 422 Unprocessable Entity.
4. **Empty File**: Empty CSV bytes $\to$ HTTP 422.
5. **File Extension Filter**: Non-CSV file uploaded (`malicious.exe` or `report.pdf`) $\to$ HTTP 400 Bad Request.
6. **Zero/Negative Amounts**: Filtered out cleanly.

### 5.4 Testing ElevenLabs Fallback

1. Set `settings.ELEVENLABS_API_KEY = ""` or `"your_api_key_here"`.
2. POST `/api/v1/tts/synthesize` with `{"text": "Dictamen forense"}`.
3. Assert HTTP 200.
4. Assert `Content-Type: audio/mpeg`.
5. Assert header `X-Audio-Source: synthetic-fallback-mode`.
6. Assert body length $\ge 320$ bytes and begins with MPEG sync byte `b"\xff\xfb"`.
7. Test upstream error handling by mocking ElevenLabs with HTTP 500 $\to$ verify route returns HTTP 502 Bad Gateway.

---

## 6. Implementation Action Plan

1. **`backend/requirements.txt`**: Add `sqlalchemy[asyncio]`, `asyncpg`, `psycopg[binary]`, `pgvector`, `greenlet`, `aiosqlite`.
2. **`backend/core/config.py`**: Add database configuration parameters and connection pooling settings.
3. **`backend/core/database.py`**: Implement async engine with connection pooling, SSL translation, `Base`, and `get_db()`.
4. **`backend/models/forensic.py`**: Define `InvestigationCase`, `TransactionRecord`, and `LegalArticleVector`.
5. **`backend/api/routes/investigations.py`**: Refactor `/upload` and `/{case_id}/stream` to use `get_db()` and persist cases, transactions, and verdicts. Implement `GET /` and `GET /{case_id}`.
6. **`backend/api/routes/agent_tools.py`**: Implement dedicated endpoints (`/transactions`, `/entities`, `/patterns`, `/legal-precedents`) and dynamic query handler registry (`/query`).
7. **`backend/main.py`**: Register `agent_tools_router` and database lifespan startup hook.
8. **`backend/tests/`**: Implement full integration tests covering database CRUD, dynamic query tools, SSE streaming persistence, and TTS fallback.
