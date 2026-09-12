# Handoff Report: Milestone 3 Agent Tools API Contracts & Schemas

## 1. Observation
- **User Request Requirements (`ORIGINAL_REQUEST.md` lines 31-41)**:
  > "R3. Scalable Query Interface & Dynamic Tool Registry for n8n AI Agents
  > Create an extensible, versioned agent tool router in `backend/api/routes/agent_tools.py` (registered in `backend/main.py`) to support current and future n8n AI agent tools without requiring backend schema alterations:
  > - **Dedicated Tool Endpoints**:
  >   - `POST /api/v1/tools/transactions`: query transactions filtered by `case_id`, origin/destination accounts, min/max amounts, time window, and `is_suspicious` flag.
  >   - `POST /api/v1/tools/entities`: profile financial entities/nodes (in/out volumes, counterparty degree, assigned risk scores and reasons).
  >   - `POST /api/v1/tools/patterns`: retrieve detected elementary cycles and rapid pass-through mule account metrics for a case.
  >   - `POST /api/v1/tools/legal-precedents`: vector similarity search against `legal_knowledge_vectors` using cosine similarity to retrieve matching Mexican AML statutes (CFF Art. 69-B, LFPIORPI, UIF guidelines).
  > - **Dynamic Tool Registry & Query Builder**:
  >   - `POST /api/v1/tools/query`: dynamic, composable query endpoint accepting structured JSON criteria (entity target, field filters, sort, limit) that safely builds and executes queries against case data.
  >   - Extensible tool handler registry pattern allowing new agent tool query definitions to be registered with minimal configuration."

- **Existing Backend Database Models (`backend/models/forensic.py` lines 53-150)**:
  - `InvestigationCase`: Stores `id` (UUID), `filename`, `status`, `ingestion_metadata` (JSONB), `metrics` (JSONB), `subgraph` (JSONB containing `nodes` and `edges`), `patterns` (JSONB containing `cycles` and `passthrough_accounts`), and `verdict` (JSONB).
  - `TransactionRecord`: Stores `id` (UUID), `case_id` (UUID FK), `origin` (String(100)), `destination` (String(100)), `amount` (Numeric(18,2)), `timestamp` (DateTime), `is_suspicious` (Boolean), `reasons` (JSONB).
  - `LegalArticleVector`: Stores `id` (UUID), `article_code` (String(50)), `law_name` (String(100)), `content` (Text), `embedding` (Vector(1536)).
  - Helper `generate_deterministic_embedding(text: str, dim: int = 1536)` generates unit-normalized vectors for pgvector cosine distance (`<=>`).

- **Existing Investigation Schemas (`backend/schemas/investigation.py` lines 26-96)**:
  - `GraphNode`: `id`, `total_in`, `total_out`, `in_degree`, `out_degree`, `reasons`, `risk_score`.
  - `CyclePattern`: `path`, `length`, `estimated_volume`.
  - `PassthroughAccountPattern`: `account`, `total_in`, `total_out`, `ratio`, `time_delta_hours`.

- **Current State of Milestone 3 Files**:
  - `backend/schemas/agent_tools.py` does NOT exist yet.
  - `backend/api/routes/agent_tools.py` does NOT exist yet.
  - `backend/main.py` has not yet included the agent tools router.

## 2. Logic Chain
1. *Observation 1 (R3 requirements & models)* dictates that five agent tool capabilities are needed: `transactions`, `entities`, `patterns`, `legal-precedents`, and dynamic `query`.
2. *Observation 2 (Pydantic v2 conventions)* requires strict type annotations, alias resolution, model validation rules, and schema separation into `backend/schemas/agent_tools.py`.
3. For `transactions`: Transactions in `TransactionRecord` are relational rows linked to `case_id`. Querying requires mandatory `case_id` scoping with optional filters (`origin`, `destination`, `min_amount`, `max_amount`, `start_time`, `end_time`, `is_suspicious`) and pagination (`limit`, `offset`). Cross-field validations (`min_amount <= max_amount`, `start_time <= end_time`) prevent logically inverted queries.
4. For `entities`: Nodes are stored in `InvestigationCase.subgraph['nodes']`. Agents may query a single entity by `entity_id` or query all entities in the case. Net flow must be computed as `total_inflow - total_outflow`. Counterparty degree, risk score, and risk flags must be exposed.
5. For `patterns`: Graph patterns are stored in `InvestigationCase.patterns['cycles']` and `['passthrough_accounts']`. Filtering by pattern type (`all`, `cycles`, `passthrough_mules`), hop lengths, and volumes allows agents to focus reasoning on specific typologies.
6. For `legal-precedents`: Vector search operates on `LegalArticleVector`. It accepts natural language `query_text` and optional 1536-dimensional `query_vector`. Dimension must be strictly validated to be 1536. It computes cosine similarity using either pgvector `<=>` operator (where `similarity = 1 - distance`) or normalized dot product in fallback mode.
7. For `dynamic query`: To prevent SQL injection and unauthorized schema traversal, the query builder must enforce a strict whitelist (`TARGET_FIELD_WHITELISTS`) and generate parameterized SQLAlchemy AST clauses rather than raw string queries. For non-relational targets (subgraph nodes, patterns), an in-memory evaluator filters the stored JSON structures.
8. Therefore, defining the complete Pydantic schemas in `backend/schemas/agent_tools.py` with comprehensive validators, aliases, and enums creates the foundational contract for Milestone 3 implementation.

## 3. Caveats
- **Offline / Test Mode Resilience**: Tests run in an isolated in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) where pgvector operators (`<=>`) are compiled to text. The vector search implementation must handle both real PostgreSQL pgvector distance queries and in-memory cosine similarity fallback.
- **Timestamp Types**: Timestamps in transaction records are stored as `datetime` objects in PostgreSQL, but may originate as numeric floats (AMLSim steps) in raw CSVs. The schemas accept both `datetime` and ISO strings/floats via validators.

## 4. Conclusion
The API contracts and Pydantic schemas for Milestone 3 have been fully formulated and documented in `.agents/spec_miner_m3_1/analysis.md`. The design fulfills all R3 requirements:
- Dedicated models: `TransactionQueryRequest/Response`, `EntityProfileRequest/Response`, `PatternQueryRequest/Response`, `LegalPrecedentQueryRequest/Response`.
- Dynamic models: `QueryFilter`, `DynamicQueryRequest/Response`, `ToolRegistry` pattern with column whitelisting.
- Ready for implementation in `backend/schemas/agent_tools.py` and `backend/api/routes/agent_tools.py`.

## 5. Verification Method
1. **Schema Syntax & Import Verification**:
   Once implemented in `backend/schemas/agent_tools.py`, verify via Python interpreter:
   ```powershell
   python -c "from backend.schemas.agent_tools import TransactionQueryRequest, EntityProfileRequest, PatternQueryRequest, LegalPrecedentQueryRequest, DynamicQueryRequest; print('Schemas imported successfully')"
   ```
2. **Automated Unit Tests**:
   Run the pytest test suite to confirm zero regressions:
   ```powershell
   pytest backend/tests/ -v
   ```
3. **Invalidation Conditions**:
   - If any schema fails Pydantic v2 validation.
   - If dynamic query permits unwhitelisted fields or non-parameterized SQL injection.
   - If vector search accepts vectors with dimensions other than 1536.
