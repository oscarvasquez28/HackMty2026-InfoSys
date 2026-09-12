# Project: Forensic Auditor Python Backend

## Architecture
The Forensic Auditor platform provides a high-performance Python FastAPI backend for AML transaction analysis, graph topological pruning, regulatory compliance matching against Mexican tax/AML jurisprudence (CFF 69-B, NIF A-2, UIF), and real-time reasoning streaming for AI agents.

### Core Modules & Data Flow:
1. **Configuration & Dependencies (`backend/core/config.py`, `backend/requirements.txt`)**:
   - Pydantic Settings loading environment variables (`DATABASE_URL`, `N8N_WEBHOOK_URL`, `ELEVENLABS_API_KEY`, etc.).
   - Async PostgreSQL drivers (`asyncpg`, `psycopg[binary]`), SQLAlchemy 2.0 async, `pgvector`, and `aiosqlite` for test environments.
2. **Database Layer (`backend/core/database.py`, `backend/models/forensic.py`)**:
   - Async SQLAlchemy 2.0 engine connected to TigerData PostgreSQL with SSL (`sslmode=require`) and connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`).
   - Driver URL normalization for both `postgresql+asyncpg` and `postgresql+psycopg`.
   - Models:
     - `InvestigationCase`: UUID PK, filename, status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), timestamps, JSONB fields (`ingestion_metadata`, `metrics`, `subgraph`, `patterns`, `verdict`).
     - `TransactionRecord`: UUID PK, `case_id` FK (indexed), `origin`, `destination`, `amount` (Numeric(18,2)), `timestamp`, `is_suspicious` (Boolean), `reasons` (JSONB).
     - `LegalArticleVector`: UUID PK, `article_code`, `law_name`, `content` (Text), `embedding` (Vector(1536) with HNSW cosine index `m=16, ef_construction=64`).
   - Dependency: `get_db()` yielding managed `AsyncSession`. Lifespan events `init_db()` and `close_db()`.
3. **Ingestion & Persistence (`backend/services/ingestion.py`, `backend/services/deterministic_filter.py`, `backend/api/routes/investigations.py`)**:
   - `POST /api/v1/investigations/upload`: Polars parses AMLSim CSV, NetworkX prunes benign edges and extracts cycles / passthrough mules, inserts `InvestigationCase` and bulk-inserts `TransactionRecord` rows into PostgreSQL, returns HTTP 201.
   - `GET /api/v1/investigations`: Paginated case list with filtering, sorting, and summary metrics.
   - `GET /api/v1/investigations/{case_id}`: Retrieves stored case record, metrics, and subgraph.
   - `GET /api/v1/investigations/{case_id}/stream`: SSE streaming (`thought` events and terminal `verdict`), dispatches to `N8N_WEBHOOK_URL` if configured, fallback to deterministic 6-phase reasoning simulation, persists final verdict and updates case status to `COMPLETED` in PostgreSQL upon completion.
4. **Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents (`backend/api/routes/agent_tools.py`)**:
   - Dedicated Endpoints:
     - `POST /api/v1/tools/transactions`: Filters transactions by `case_id`, origin/destination accounts, amount bounds, time window, and suspicion flag.
     - `POST /api/v1/tools/entities`: Analyzes entity nodes (inflow, outflow, net volume, counterparty degrees, assigned risk scores and reasons).
     - `POST /api/v1/tools/patterns`: Retrieves elementary cycles and passthrough mule metrics for a case.
     - `POST /api/v1/tools/legal-precedents`: Vector similarity search against `legal_knowledge_vectors` using cosine similarity (pgvector `<=>` operator) with fallback keyword search.
   - Dynamic Composable Query Builder:
     - `POST /api/v1/tools/query`: Composable query endpoint accepting entity target, field filters (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`), sorting, limit, and offset.
     - Extensible `ToolRegistry` pattern allowing dynamic registration of new tool queries without modifying database schema, enforcing column whitelisting, parameterized SQL generation, and mandatory `case_id` scoping to prevent SQL injection.
5. **Speech Synthesis Proxy & Security (`backend/api/routes/tts.py`)**:
   - `POST /api/v1/tts/synthesize`: Proxies ElevenLabs API streaming `audio/mpeg` shielding `ELEVENLABS_API_KEY`, with valid 320-byte synthetic silent MPEG frame fallback for offline resilience.
6. **Testing & Verification Suite (`backend/tests/`)**:
   - Comprehensive test suite covering database engine/session, model CRUD, ingestion & persistence, paginated listing, case retrieval, SSE stream persistence, all dedicated & dynamic agent tools, and TTS proxy.
   - Zero-regression test fixture using `sqlite+aiosqlite:///:memory:` with `@compiles(Vector, "sqlite")` hook and FastAPI `dependency_overrides[get_db]`.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Async SQLAlchemy 2.0 Engine & Pooling | Connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`) | M1 | ORIGINAL_REQUEST §R1 |
| 2 | SSL Enforcement & Driver Normalization | Enforce `sslmode=require` / `ssl="require"` supporting `postgresql+asyncpg` and `postgresql+psycopg` | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Database Models Definition | `InvestigationCase`, `TransactionRecord`, `LegalArticleVector` with UUID, JSONB, Vector(1536) | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Vector HNSW Indexing & Seed Data | HNSW cosine index `m=16, ef_construction=64` and seed Mexican AML jurisprudence (CFF 69-B, NIF A-2, UIF) | M1 | ORIGINAL_REQUEST §R1, doc/data-and-compliance |
| 5 | Dependency Injection & Lifecycle Hooks | `get_db()` async session generator, `init_db()`, `close_db()`, graceful error if unconfigured | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Settings & Requirements Update | Add SQLAlchemy, asyncpg, psycopg, pgvector, aiosqlite, and config attributes | M1 | ORIGINAL_REQUEST §R1 |
| 7 | Persistent Upload Endpoint | `POST /investigations/upload` persisting `InvestigationCase` and all `TransactionRecord` rows | M2 | ORIGINAL_REQUEST §R2 |
| 8 | Paginated Investigations Listing | `GET /investigations` with `page`, `page_size`, status, timestamps, summary metrics | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Case Detail Retrieval Endpoint | `GET /investigations/{case_id}` returning case metadata, topological metrics, and subgraph | M2 | ORIGINAL_REQUEST §R2 |
| 10 | SSE Thought Stream & Verdict Persistence | `GET /investigations/{case_id}/stream` streaming SSE thought/verdict and saving verdict to PostgreSQL | M2 | ORIGINAL_REQUEST §R2 |
| 11 | n8n Webhook Integration & Fallback | Webhook dispatch to `N8N_WEBHOOK_URL` with deterministic 6-phase reasoning simulation fallback | M2 | ORIGINAL_REQUEST §R2 |
| 12 | Transactions Agent Tool | `POST /tools/transactions` filtering by case, accounts, amounts, date range, suspicion flag | M3 | ORIGINAL_REQUEST §R3 |
| 13 | Entities Profiling Tool | `POST /tools/entities` profiling counterparty degree, inflow, outflow, risk scores | M3 | ORIGINAL_REQUEST §R3 |
| 14 | Patterns Extraction Tool | `POST /tools/patterns` retrieving detected elementary cycles and rapid passthrough metrics | M3 | ORIGINAL_REQUEST §R3 |
| 15 | Legal Precedents Similarity Tool | `POST /tools/legal-precedents` vector similarity search against Mexican AML statutes | M3 | ORIGINAL_REQUEST §R3 |
| 16 | Dynamic Composable Query Endpoint | `POST /tools/query` executing structured filter criteria safely with column whitelisting | M3 | ORIGINAL_REQUEST §R3 |
| 17 | Extensible Tool Registry | `ToolRegistry` pattern allowing registration of new agent tool queries with zero schema changes | M3 | ORIGINAL_REQUEST §R3 |
| 18 | Speech Synthesis Proxy Hardening | `POST /tts/synthesize` streaming ElevenLabs audio shielding API key, with timeout/disconnect resilience | M4 | ORIGINAL_REQUEST §R4 |
| 19 | Synthetic Silent MP3 Fallback | Offline resilient fallback emitting 320-byte MPEG frames with `X-Audio-Source` header | M4 | ORIGINAL_REQUEST §R4 |
| 20 | Database Layer Tests | Unit tests for engine connection, pooling, session rollback, and model CRUD operations | M5 | ORIGINAL_REQUEST §R5 |
| 21 | Investigation Persistence Tests | Tests for CSV upload persistence, pagination, detail retrieval, and stream verdict save | M5 | ORIGINAL_REQUEST §R5 |
| 22 | Agent Tools Query Tests | Tests for all 4 dedicated tool endpoints and dynamic composable query builder | M5 | ORIGINAL_REQUEST §R5 |
| 23 | TTS Proxy & Fallback Tests | Tests for synthesis proxy streaming and synthetic fallback mode | M5 | ORIGINAL_REQUEST §R5 |
| 24 | E2E Forensic Pipeline Verification | Full end-to-end test verifying upload -> DB -> tools -> stream -> verdict persistence | M5 | ORIGINAL_REQUEST §R5 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: TigerData PostgreSQL & pgvector Database Layer | Requirements, config, database engine, models, seed data, get_db | none | DONE |
| 2 | M2: Investigation Lifecycle & Persistent Case Management | Upload persistence, GET list, GET by ID, SSE stream + DB verdict save | M1 | DONE |
| 3 | M3: Scalable Query Interface & Dynamic Tool Registry for n8n | Dedicated tools (/transactions, /entities, /patterns, /legal-precedents), /query, registry | M1, M2 | DONE |
| 4 | M4: Speech Synthesis Proxy & Security Hardening | TTS endpoint hardening, timeout/disconnect resilience, silent MPEG fallback | none | DONE |
| 5 | M5: E2E Verification & Test Suite Hardening | Comprehensive automated test suite across all modules, 100% pytest pass | M1, M2, M3, M4 | DONE |

---

## Interface Contracts
### database ↔ api routes
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]: ...
async def init_db() -> None: ...
async def close_db() -> None: ...
```

### Models
```python
class InvestigationCase(Base):
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    ingestion_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    subgraph: Mapped[dict] = mapped_column(JSONB, default=dict)
    patterns: Mapped[dict] = mapped_column(JSONB, default=dict)
    verdict: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

class TransactionRecord(Base):
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(100), index=True)
    destination: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)

class LegalArticleVector(Base):
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    article_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    law_name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
```

### Agent Tool Router & Registry
```python
class ToolRegistry:
    def register(self, target: str, handler_callable): ...
    async def execute_query(self, target: str, criteria: QueryCriteria, db: AsyncSession) -> Dict[str, Any]: ...
```

---

## Code Layout
- `backend/requirements.txt`: Dependencies specification.
- `backend/core/config.py`: Settings definition with database attributes.
- `backend/core/database.py`: Async engine, sessionmaker, `get_db()`, `init_db()`.
- `backend/models/forensic.py`: Declarative models for cases, transactions, legal vectors, and seed data.
- `backend/api/routes/investigations.py`: Persistent upload, listing, retrieval, and SSE streaming.
- `backend/api/routes/agent_tools.py`: Dedicated tool endpoints and dynamic query registry.
- `backend/api/routes/tts.py`: Speech synthesis proxy and synthetic silent MP3 generator.
- `backend/main.py`: FastAPI application setup, router inclusions, and lifespan management.
- `backend/tests/conftest.py`: Test configuration, async SQLite engine fixture, dependency overrides.
- `backend/tests/test_database.py`: Database engine and model unit tests.
- `backend/tests/test_investigations.py`: Ingestion, persistence, pagination, and SSE streaming tests.
- `backend/tests/test_agent_tools.py`: Dedicated tools and dynamic query registry tests.
- `backend/tests/test_tts.py`: TTS proxy and fallback tests.
- `backend/tests/test_pipeline.py`: Comprehensive end-to-end forensic pipeline test.
