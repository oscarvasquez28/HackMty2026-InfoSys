# Original User Request

## Initial Request — 2026-09-12T08:59:28Z

# Complete Forensic Auditor Python Backend with TigerData PostgreSQL & Scalable n8n Agent Tools

Working directory: c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY 2026/Infosys/Polar
Integrity mode: demo

Complete the production-grade Python FastAPI backend for the Forensic Auditor platform following the architecture and contracts specified in `doc/architecture` and `doc/backend`. Connect strictly to remote TigerData PostgreSQL with `pgvector` via async SQLAlchemy, update the ingestion and SSE streaming pipelines for database persistence, and implement a scalable query interface and dynamic tool registry for n8n AI agents.

## Requirements

### R1. TigerData PostgreSQL & pgvector Database Layer
Implement the database architecture in `backend/core/database.py` and `backend/models/forensic.py` using async SQLAlchemy 2.0:
- Connect to TigerData PostgreSQL using `DATABASE_URL` (e.g., `postgresql+psycopg://...` or `postgresql+asyncpg://...`) with SSL enforced (`sslmode=require`) and connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`).
- Implement the target relational and vector models:
  - `InvestigationCase`: UUID primary key, filename, status, timestamps, JSONB fields for ingestion metadata, metrics, subgraph, patterns, and verdict.
  - `TransactionRecord`: relational rows linked to `InvestigationCase` with origin, destination, amount, timestamp, is_suspicious flag, and reasons.
  - `LegalArticleVector`: knowledge base table with article code, law name, textual content, and `Vector(1536)` (or Gemini-compatible dimension) with HNSW indexing for Mexican AML / CFF 69-B jurisprudence.
- Provide database lifecycle hooks (automatic schema/extension initialization and graceful dependency injection via `get_db()`).
- Update `backend/requirements.txt` and `backend/core/config.py` with necessary database drivers and settings.

### R2. Investigation Lifecycle & Persistent Case Management
Update and expand the investigation endpoints in `backend/api/routes/investigations.py`:
- `POST /api/v1/investigations/upload`: ingest CSV via Polars, run deterministic graph pruning via NetworkX, insert the case record and associated transaction records into TigerData PostgreSQL, and return HTTP 201 with case ID, metrics, subgraph, and patterns.
- `GET /api/v1/investigations`: paginated list of stored investigation cases with status, timestamps, and summary metrics.
- `GET /api/v1/investigations/{case_id}`: retrieve stored case details, topological metrics, and isolated subgraph from PostgreSQL.
- `GET /api/v1/investigations/{case_id}/stream`: read case data from PostgreSQL, dispatch webhook payload to `N8N_WEBHOOK_URL` if configured (with automatic fallback to simulated 6-phase reasoning), stream SSE `thought` events and terminal `verdict` event, and update the case verdict and completion status in PostgreSQL upon stream completion.

### R3. Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents
Create an extensible, versioned agent tool router in `backend/api/routes/agent_tools.py` (registered in `backend/main.py`) to support current and future n8n AI agent tools without requiring backend schema alterations:
- **Dedicated Tool Endpoints**:
  - `POST /api/v1/tools/transactions`: query transactions filtered by `case_id`, origin/destination accounts, min/max amounts, time window, and `is_suspicious` flag.
  - `POST /api/v1/tools/entities`: profile financial entities/nodes (in/out volumes, counterparty degree, assigned risk scores and reasons).
  - `POST /api/v1/tools/patterns`: retrieve detected elementary cycles and rapid pass-through mule account metrics for a case.
  - `POST /api/v1/tools/legal-precedents`: vector similarity search against `legal_knowledge_vectors` using cosine similarity to retrieve matching Mexican AML statutes (CFF Art. 69-B, LFPIORPI, UIF guidelines).
- **Dynamic Tool Registry & Query Builder**:
  - `POST /api/v1/tools/query`: dynamic, composable query endpoint accepting structured JSON criteria (entity target, field filters, sort, limit) that safely builds and executes queries against case data.
  - Extensible tool handler registry pattern allowing new agent tool query definitions to be registered with minimal configuration.

### R4. Speech Synthesis Proxy & Security
Harden `backend/api/routes/tts.py`:
- Proxy audio synthesis to ElevenLabs API streaming endpoint (`audio/mpeg`), shielding `ELEVENLABS_API_KEY`.
- Maintain the synthetic silent MP3 fallback generator for offline resilience when credentials are absent.

### R5. Verification & Comprehensive Test Suite
Update and expand `backend/tests/` to provide rigorous automated verification:
- Verify database connection management and model CRUD operations.
- Test CSV ingestion, pruning calculation, and relational persistence.
- Test all dedicated and dynamic n8n agent tool query endpoints with varied query parameters.
- Test SSE thought streaming and verdict updates.
- Test TTS synthesis proxy and fallback audio output.

## Acceptance Criteria

### Database Layer
- [ ] SQLAlchemy async engine initializes with SSL (`sslmode=require`) and connection pooling.
- [ ] Database models (`investigation_cases`, `transactions`, `legal_knowledge_vectors`) defined and mapped with appropriate types (UUID, JSONB, Vector).
- [ ] Database dependency `get_db` yields managed transactional async sessions.
- [ ] Missing database configuration produces clear, informative errors.

### Investigation & Persistence
- [ ] `POST /api/v1/investigations/upload` persists case record and all individual transactions in PostgreSQL.
- [ ] `GET /api/v1/investigations` returns paginated case history.
- [ ] `GET /api/v1/investigations/{case_id}` returns full case record and subgraph from PostgreSQL.
- [ ] `GET /api/v1/investigations/{case_id}/stream` streams SSE events and saves the final verdict into PostgreSQL.

### n8n Agent Tool Endpoints
- [ ] `POST /api/v1/tools/transactions` filters transactions by case, account, amount, and suspicion.
- [ ] `POST /api/v1/tools/entities` returns detailed inflows, outflows, and risk tags for queried accounts.
- [ ] `POST /api/v1/tools/patterns` returns detected cycles and pass-through accounts.
- [ ] `POST /api/v1/tools/legal-precedents` executes vector similarity search against legal precedents.
- [ ] `POST /api/v1/tools/query` safely executes structured composable filter queries.

### Audio & System Quality
- [ ] `POST /api/v1/tts/synthesize` streams MP3 audio or silent MPEG fallback frame.
- [ ] `GET /health` returns status healthy.
- [ ] All automated tests in `backend/tests/` pass cleanly without unhandled exceptions.

