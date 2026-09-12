# Milestone 1 Handoff Report: Database Layer & Legal Precedents

**From**: `spec_miner_m1_1`  
**To**: `orchestrator_1` / `worker_m1_1`  
**Date**: 2026-09-12T09:07:00Z  
**Subject**: Authoritative Specification for Models, Database Layer, and Mexican AML Jurisprudence  
**Target Files**: `backend/models/forensic.py`, `backend/core/database.py`, `backend/core/config.py`, `backend/requirements.txt`  
**Full Analysis Path**: `c:\Users\maxan\OneDrive\Documentos\Repositories\HackMTY 2026\Infosys\Polar\.agents\spec_miner_m1_1\analysis.md`

---

## 1. Observation
1. **Original Request & Project Plan Requirements**:
   - In `ORIGINAL_REQUEST.md` (lines 14-23), Section R1 specifies:
     > "Implement the database architecture in `backend/core/database.py` and `backend/models/forensic.py` using async SQLAlchemy 2.0:
     > - Connect to TigerData PostgreSQL using `DATABASE_URL` (e.g., `postgresql+psycopg://...` or `postgresql+asyncpg://...`) with SSL enforced (`sslmode=require`) and connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`).
     > - Implement the target relational and vector models: `InvestigationCase`, `TransactionRecord`, `LegalArticleVector`."
   - In `.agents/orchestrator_1/PROJECT.md` (lines 90-119), exact interface contracts for the 3 SQLAlchemy models are defined with UUID primary keys, JSONB columns, foreign key cascade options, and HNSW cosine vector index `m=16, ef_construction=64`.
   - In `doc/data-and-compliance/README.md` (lines 247-290, 296-315), the legal compliance framework is detailed, specifying:
     - CFF Art. 69-B: Inexistencia de operaciones, distinction between EFOS ("factureras") and EDOS ("deductoras"), 15 business days rebuttal period (extendable by 10), and 30 business days EDOS regularization period.
     - NIF A-2: Postulado básico de sustancia económica, Supreme Court tesis 2a./J. 78/2019, and the Tríada Probatoria Forense (contratos con fecha cierta / NOM-151, entregables verificables y contemporáneos, trazabilidad financiera).
     - UIF & GAFI: Reporte de Operación Inusual (ROI) within 24 to 48 hours, Reporte de Operación Relevante (ROR) for cash transactions $\ge \$7,500$ USD, and Artículo 115 LIC account freezing via Lista de Personas Bloqueadas (LPB).
     - Target SQL schema for vector search using `pgvector` with HNSW index `vector_cosine_ops`.
2. **Current Codebase State**:
   - `backend/models/` directory does not yet exist.
   - `backend/core/database.py` does not yet exist.
   - `backend/core/config.py` lines 7-52 define `Settings` without database connection parameters (`DATABASE_URL`, pool attributes).
   - `backend/requirements.txt` lines 1-11 define FastAPI, Polars, NetworkX, but lack SQLAlchemy, asyncpg, psycopg, pgvector, and aiosqlite.
   - Existing pipeline test `backend/tests/test_pipeline.py` currently tests the in-memory investigation endpoint and ElevenLabs mock.

---

## 2. Logic Chain
1. **Model Architecture**:
   - `InvestigationCase` requires storing rich forensic results from NetworkX pruning (topological metrics, subgraphs with nodes/edges, and detected cycle/passthrough patterns) as well as the SSE-generated final verdict. Mapping these to JSONB (`JSON().with_variant(JSONB, "postgresql")`) allows flexible schema storage without requiring schema alterations for new graph metrics.
   - `TransactionRecord` requires relational linkage with `ForeignKey("investigation_cases.id", ondelete="CASCADE")` and indexing on `origin`, `destination`, and `is_suspicious`. This enables the upcoming n8n agent tools (`/api/v1/tools/transactions`, `/api/v1/tools/entities`) to execute targeted SQL queries with sub-millisecond index scans.
   - `LegalArticleVector` requires an HNSW index on `embedding` (`Vector(1536)`). By configuring `postgresql_using="hnsw"`, `postgresql_with={"m": 16, "ef_construction": 64}`, and `postgresql_ops={"embedding": "vector_cosine_ops"}`, pgvector will execute fast cosine approximate nearest neighbor searches for RAG queries.
2. **Dialect Compatibility for Testing**:
   - Fast automated testing relies on in-memory SQLite (`sqlite+aiosqlite:///:memory:`). However, SQLite does not understand PostgreSQL's `JSONB` or `VECTOR` data types.
   - Adding SQLAlchemy `@compiles(Vector, "sqlite")` returning `"TEXT"` and `@compiles(JSONB, "sqlite")` returning `"JSON"` guarantees zero syntax errors during test execution without altering production PostgreSQL DDL.
3. **Database Engine & Connection Pool**:
   - Remote TigerData PostgreSQL requires SSL (`sslmode=require`).
   - For `asyncpg`, URL parameters with `sslmode=require` are incompatible with standard parsing; asyncpg requires `connect_args={"ssl": "require"}`. Normalizing the connection URL dynamically in `normalize_database_url` solves both `postgresql+asyncpg` and `postgresql+psycopg` drivers.
   - Pool parameters (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`) ensure that connection drops from cloud timeouts are transparently recycled before executing queries.
4. **Seed Knowledge Integrity**:
   - The 6 legal precedents discovered (CFF 69-B, NIF A-2, UIF ROI, UIF ROR, LIC 115, CPF 400 Bis) contain complete statutory texts, evidentiary requirements, and compliance timelines.
   - Pre-generating unit-normalized 1536-dimensional embeddings deterministically from SHA-256 text hashes ensures that vector cosine similarity functions reliably during test runs and offline demo modes without requiring third-party API keys.

---

## 3. Caveats
1. `Vector` embedding dimension is specified as 1536 to match OpenAI `text-embedding-3-small` and standard vector standards. If Google Gemini `text-embedding-004` (768 dimensions) is selected later, the vector column dimension must be updated in tandem.
2. Running tests on SQLite validates relational CRUD, relationships, cascade deletes, and JSON storage, but pgvector HNSW index operations require a live PostgreSQL instance with `pgvector` enabled. In SQLite, the tool will fall back gracefully to keyword/ILIKE matching.

---

## 4. Conclusion
1. All required specifications for `backend/models/forensic.py` (`InvestigationCase`, `TransactionRecord`, `LegalArticleVector`), `backend/core/database.py` (async engine, pooling, SSL enforcement, `get_db()`, `init_db()`), `backend/core/config.py`, and `backend/requirements.txt` are fully documented in `analysis.md`.
2. Authoritative legal precedent texts and a deterministic unit-normalized embedding generator are prepared and ready for direct copy-paste implementation by Worker M1.
3. Worker M1 can proceed immediately with implementation.

---

## 5. Verification Method
1. **Inspect Analysis Report**:
   - Read `.agents/spec_miner_m1_1/analysis.md` to verify model schemas, column definitions, index definitions, and legal seed texts.
2. **Worker Implementation Verification**:
   - Once implemented by Worker M1:
     - Install updated requirements: `pip install -r backend/requirements.txt`
     - Run unit tests: `pytest backend/tests/test_database.py`
     - Verify engine initialization with SSL normalization.
     - Verify CRUD operations on `investigation_cases`, `transactions`, and `legal_knowledge_vectors`.
     - Verify cascade delete when parent case is deleted.
     - Verify that seed precedents are loaded and accessible.
