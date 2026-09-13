# Documentation Agent Routing Index

> [!CAUTION]
> **Instructions for AI Agents:**
> **DO NOT read all documentation files in `doc/`!**
> Loading the full documentation tree will saturate your context window, degrade your reasoning performance, and waste tokens.
> Consult the **Quick Task Dispatcher** and **Keyword Map** below to identify the **exact single file** relevant to your specific task, and read only that file.

---

## 1. Quick Task Dispatcher

Find the exact single documentation file needed for common engineering and maintenance workflows:

| If your task involves... | Primary Target File | Scope & Summary | Do NOT Read |
| :--- | :--- | :--- | :--- |
| **Global system architecture, end-to-end 6-stage lifecycle, or tech stack overview** | [`doc/README.md`](./README.md) | High-level system topology, architectural evolution, and cross-cutting concerns. | Detailed component or algorithm docs |
| **Multi-container orchestration, docker-compose, or external service topologies** | [`doc/architecture/README.md`](./architecture/README.md) | Docker service layout, networking, external TigerData and n8n connections. | Individual component files or Python algorithms |
| **Unified SSE communication contract (`thought` and `verdict` schemas), or n8n webhook payload** | [`doc/architecture/README.md`](./architecture/README.md) | Exact JSON payloads, streaming headers, and proxy contracts. | Frontend styling or database schema files |
| **FastAPI routing, `/investigations/upload`, `/stream`, `/tts/synthesize`, or app lifecycle** | [`doc/backend/README.md`](./backend/README.md) | Route handlers, request validation, Pydantic settings, and pytest suite. | Next.js components or React Flow docs |
| **Connecting backend to TigerData PostgreSQL via SQLAlchemy and pgvector** | [`doc/backend/README.md`](./backend/README.md) | Connection pool design, SQLAlchemy models, migration roadmap, and vector search. | Frontend UI docs or Docker Compose files |
| **Read-only Agent Tools (`/api/v1/tools/*`), dynamic AST validation, or `tool_registry.py`** | [`doc/backend/README.md`](./backend/README.md) | Read-only agent inspection endpoints, AST expression compiler, and SQL safety tests. | Frontend styling or AMLSim schema files |
| **Polars data ingestion, column alias resolution, or CSV cleansing** | [`doc/backend/README.md`](./backend/README.md) | `read_amlsim_csv()` implementation, column mapping, and Polars filtering. | UI styling or legal jurisprudence docs |
| **NetworkX graph building, cycle detection, or pass-through account algorithms** | [`doc/backend/README.md`](./backend/README.md) | Mathematical graph algorithms, `MAX_CYCLE_LENGTH`, and pruning telemetry. | Frontend components or audio synthesis code |
| **ElevenLabs TTS streaming proxy, API key shielding, or silent MP3 fallback** | [`doc/backend/README.md`](./backend/README.md) | Audio streaming proxy endpoint, chunked transfer, and offline fallback frame. | Frontend UI layout or database models |
| **Running backend automated test suites (121 tests across 13 modules)** | [`doc/backend/README.md`](./backend/README.md) | Pytest commands, test database isolation, pipeline validation, and tool fixtures. | Frontend React components |
| **Case File Viewer (`/investigate`): rendering, validating, or exporting the judged case file JSON** | [`doc/frontend/README.md`](./frontend/README.md) | §10: source→normalize→validate→derive→render pipeline, `submission_schema.json` contract + extensions, Mermaid money-trail diagrams, Print/HTML/Markdown/JSON export. | Backend Python code or database models |
| **Data Estate page (`/investigate/data`): SQLite/CSV/CFDI-XML/JSON ingestion in the browser** | [`doc/frontend/README.md`](./frontend/README.md) | §11: `sql.js` WASM, per-format parsers, estate-wide validation, checking exhibits against the estate, `estate.db` export. | Backend Python code or the seeder doc below |
| **Next.js workspace UI generally, or the deprecated multi-agent simulation (`/investigate/simulation`)** | [`doc/frontend/README.md`](./frontend/README.md) | App Router layout, component/hook responsibility matrix, legacy simulation vs. live SSE modes. | Backend Python code or database models |
| **Frontend streaming hooks (`useInvestigationStream` or `useAudioStream`)** | [`doc/frontend/README.md`](./frontend/README.md) | `EventSource` lifecycle, Blob URL audio synthesis, and abort signaling. | Graph pruning math or Docker configs |
| **Fixing missing `frontend/lib/utils.ts` / `formatCurrencyMXN` build error** | [`doc/frontend/README.md`](./frontend/README.md) | Section 8.1 edge cases identifying the missing utility and exact solution. | Backend code or AMLSim schemas |
| **Implementing the interactive AML Money Trail Visualizer with `@xyflow/react`** | [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md) | React Flow 12+ setup, `@dagrejs/dagre` layout engine, custom nodes & edges. | Backend algorithms or legal compliance docs |
| **IBM AMLSim benchmark dataset schema, column formats, or synthetic sample** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Transaction schema fields, aliases, and `sample_amlsim.csv` patterns. | Frontend components or Dockerfiles |
| **Forensic Data Estate Seeder (`estate_schema.sql`), multi-dataset batch generation, or ground truth** | [`doc/data-and-compliance/data_estate_seeder.md`](./data-and-compliance/data_estate_seeder.md) | 8-table SQLite generation, 5 forensic scheme injections, decoys, config guide, and `validate_format.py`. | Frontend components or audio proxy |
| **Deterministic graph pruning mathematical formulas and noise reduction proof** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Bounded cycle equations, flow retention ratios, and smurfing logic. | REST endpoints or React hooks |
| **Mexican legal AML compliance (Art. 69-B CFF EFOS/EDOS, NIFs, UIF/GAFI ROI)** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Mexican tax/AML statutes, operational materiality, and forensic defense proofs. | Frontend styling or API routing boilerplate |
| **Global system topology, multi-tier data flow, or repository sitemap** | [`doc/README.md`](./README.md) | High-level system topology, architectural evolution, and master documentation tree. | Individual component files or Python test suites |
| **Docker Compose, container topology, service boundaries, or SSE contracts** | [`doc/architecture/README.md`](./architecture/README.md) | Docker service layout, networking, external TigerData/n8n/ElevenLabs service boundaries, and SSE streaming JSON contracts. | Low-level Python algorithm math or CSS styling |
| **Backend REST & SSE routes, app factory, or CLI entrypoint** | [`doc/backend/api/README.md`](./backend/api/README.md) | FastAPI app factory, routes (`/investigations`, `/estates`, `/tools`, `/tts`), SSE stream handling, and `backend/cli.py`. | UI components or database ORM models |
| **Polars ingestion, NetworkX graph pruning, or 5 deterministic fraud detectors** | [`doc/backend/graph-pruning/README.md`](./backend/graph-pruning/README.md) | Polars CSV ingestion, graph cycle detection ($k \le 5$), pass-through mule filter ($\ge 90\% \le 48\text{h}$), and the 5 contest detectors. | Frontend React components or ElevenLabs routes |
| **Data estate SQLite connector, exhibit builder, or 2% peso reconciliation** | [`doc/backend/estate-exhibits/README.md`](./backend/estate-exhibits/README.md) | `estate_connector.py`, `exhibit_builder.py`, mathematical 2% per-table peso reconciliation, and `case_file_generator.py`. | Frontend styling or Docker Compose configs |
| **Dynamic agent tools, AST SQL queries, or sequential n8n LLM enrichment** | [`doc/backend/orchestration-tools/README.md`](./backend/orchestration-tools/README.md) | `tool_registry.py` (AST safe query, column whitelist) and `n8n_enrichment.py` (adversarial challenge and judicial verdict loop). | Low-level Polars parsing or React UI hooks |
| **SQLAlchemy 2.0 ORM models, TigerData pgvector, config, or PII masking** | [`doc/backend/core-data/README.md`](./backend/core-data/README.md) | Database connection pooling, pgvector HNSW legal embeddings, Pydantic schemas, BaseSettings config, and PII masking. | Graph pruning math or frontend components |
| **Running backend tests, debugging pytest failures, or mock strategies** | [`doc/backend/tests/README.md`](./backend/tests/README.md) | 160 automated tests across 24 test suites in `backend/tests/`, mock fixtures (n8n, ElevenLabs, SQLite), and test commands. | Frontend build files or legal statutes |
| **Case File Viewer (`/investigate`): rendering, Mermaid SVG, or multi-format export** | [`doc/frontend/case-file-viewer/README.md`](./frontend/case-file-viewer/README.md) | 5-section dossier, finding sections, Mermaid money trails, exhibits table, adversarial review, and Print/HTML/Markdown/JSON export. | Backend Python services or Data Estate WASM code |
| **Data Estate page (`/investigate/data`): in-browser `sql.js` WASM engine** | [`doc/frontend/data-estate/README.md`](./frontend/data-estate/README.md) | In-browser SQLite WASM workspace, DB/CSV/XML/JSON ingestion, schema validation against `estate_schema.sql`, and audit stream modal. | Backend Python code or case file export logic |
| **Frontend streaming hooks, multi-agent tracks, or ElevenLabs audio player** | [`doc/frontend/agent-orchestration-and-stream/README.md`](./frontend/agent-orchestration-and-stream/README.md) | `useInvestigationStream`, `AudioPlayer`, `useAudioStream`, specialist tracks (`AgentSwimlanes`, `VerdictCard`), and legacy simulation. | Graph algorithm formulas or database ORM models |
| **Next.js layout, landing page, session state provider, or forensic theme tokens** | [`doc/frontend/core-shell-and-shared/README.md`](./frontend/core-shell-and-shared/README.md) | Root layout, landing page (`/`), `InvestigateSessionProvider`, top navigation bar, file upload, dark theme tokens, and `lib/utils.ts`. | Forensic fraud schemes or backend test files |
| **Data Estate schema (`estate_schema.sql`), CFDI 4.0, or Mexican tax/AML law** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | 8-table estate schema, CFDI 4.0 electronic invoicing, 5 fraud schemes, Mexican tax/AML compliance (Art. 69-B, NIF A-2, UIF/GAFI). | Frontend UI component styling or API routing |
| **Generating synthetic financial estates or seeding test databases** | [`doc/data-and-compliance/data_estate_seeder.md`](./data-and-compliance/data_estate_seeder.md) | Seeder architecture, generation parameters, config file reference, and database schema setup. | Frontend hooks or Docker Compose configs |
| **Running evaluation benchmarks, offline audit CLI, or validating submissions** | [`doc/evaluation-and-tooling/README.md`](./evaluation-and-tooling/README.md) | Multi-seed benchmark harness (`eval_harness.py`), estate generator, `run_audit.py` CLI, format validator, and judging scoring rules. | Frontend UI styling or ElevenLabs routes |

---

## 2. Segment Catalog & Keyword Map

Scan this catalog to match domain concepts to their home directory:
Scan this catalog to match domain concepts to their exact documentation file:

### [`doc/architecture/README.md`](./architecture/README.md)
- **Keywords**: `architecture`, `topology`, `docker-compose`, `sse-contracts`, `n8n-integration`, `tigerdata`, `end-to-end`, `event-schemas`, `agent-tools-topology`
- **Read When**: Designing cross-service integrations, configuring container environments, reviewing SSE event contracts, or updating communication boundaries between FastAPI, Next.js, TigerData, and n8n.
- **Skip When**: Modifying specific React UI components, tuning Python graph algorithms, or writing database migrations.
### System & Architecture
- **[`doc/README.md`](./README.md)**
  - **Keywords**: `master-hub`, `overview`, `architecture-tree`, `cross-cutting`, `quickstart`
  - **Read When**: Needing a global overview of the platform, cross-cutting concerns, or repository directory layout.
  - **Skip When**: Working on a specific single component, hook, endpoint, or test suite.
- **[`doc/architecture/README.md`](./architecture/README.md)**
  - **Keywords**: `architecture`, `topology`, `docker-compose`, `sse-contracts`, `n8n-integration`, `tigerdata`
  - **Read When**: Inspecting multi-service Docker topology, reviewing SSE event schemas, or configuring cloud service boundaries.
  - **Skip When**: Writing isolated React UI components or tuning Python graph algorithms.

### [`doc/backend/README.md`](./backend/README.md)
- **Keywords**: `fastapi`, `polars`, `networkx`, `sse-streaming`, `elevenlabs`, `tigerdata-sqlalchemy`, `pgvector`, `agent-tools`, `tool-registry`, `pytest`, `httpx`
- **Read When**: Developing backend API routes, improving Polars ingestion speed, tuning NetworkX pruning, implementing SQLAlchemy models for TigerData, testing agent inspection tools, or updating the ElevenLabs voice proxy.
- **Skip When**: Editing Next.js JSX/TSX components, styling with Tailwind, or reading Mexican statutory law texts.
### Backend (`doc/backend/`)
- **[`doc/backend/README.md`](./backend/README.md)**
  - **Keywords**: `backend-hub`, `services-index`, `pipeline-flows`, `tech-stack`
  - **Read When**: Navigating backend subsystems or understanding how the dual processing pipelines connect.
- **[`doc/backend/api/README.md`](./backend/api/README.md)**
  - **Keywords**: `fastapi`, `routes`, `sse-streaming`, `cli`, `tts-proxy`, `investigations-endpoint`
  - **Read When**: Modifying REST/SSE route handlers, request validation, upload endpoints, or CLI commands.
- **[`doc/backend/graph-pruning/README.md`](./backend/graph-pruning/README.md)**
  - **Keywords**: `polars`, `networkx`, `graph-pruning`, `cycle-detection`, `passthrough-mules`, `fraud-detectors`
  - **Read When**: Implementing or debugging Polars tabular ingestion, NetworkX cycle math, or the 5 fraud detectors.
- **[`doc/backend/estate-exhibits/README.md`](./backend/estate-exhibits/README.md)**
  - **Keywords**: `estate-connector`, `exhibit-builder`, `peso-reconciliation`, `case-file-generator`, `submission-schema`
  - **Read When**: Working with SQLite estate extraction, building documentary exhibits, checking 2% reconciliation, or generating case files.
- **[`doc/backend/orchestration-tools/README.md`](./backend/orchestration-tools/README.md)**
  - **Keywords**: `tool-registry`, `dynamic-query`, `ast-validation`, `n8n-enrichment`, `adversarial-review`, `judicial-verdict`
  - **Read When**: Updating agent tools, AST SQL security whitelists, sequential LLM review loops, or judicial verdicts.
- **[`doc/backend/core-data/README.md`](./backend/core-data/README.md)**
  - **Keywords**: `sqlalchemy`, `pgvector`, `hnsw-index`, `pydantic-schemas`, `config-settings`, `pii-masking`
  - **Read When**: Updating database models, pgvector legal search, Pydantic schemas, settings, or PII masking rules.
- **[`doc/backend/tests/README.md`](./backend/tests/README.md)**
  - **Keywords**: `pytest`, `test-suites`, `test-catalog`, `mocks`, `challenge-milestones`, `e2e-testing`
  - **Read When**: Running tests, investigating test failures, or writing new unit/integration/e2e test suites.

### [`doc/frontend/README.md`](./frontend/README.md)
- **Keywords**: `nextjs`, `react`, `tailwindcss`, `sse-streaming`, `audio-streaming`, `components`, `hooks`, `types`, `investigate-workspace`, `multi-file-upload`, `simulation-mode`
- **Read When**: Modifying the web dashboard, adding UI components, handling SSE connection state in React, managing audio playback, configuring multi-file upload, or resolving frontend build errors.
- **Skip When**: Writing Python backend logic, tuning graph pruning algorithms, or designing database schemas.
- **Sub-module**:
  - [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md) - Complete design blueprint for the `@xyflow/react` AML Money Trail interactive graph visualizer.
### Frontend (`doc/frontend/`)
- **[`doc/frontend/README.md`](./frontend/README.md)**
  - **Keywords**: `frontend-hub`, `client-architecture`, `app-router`, `workspaces`, `session-provider`
  - **Read When**: Navigating frontend UI subsystems or understanding component layout and session state sharing.
- **[`doc/frontend/case-file-viewer/README.md`](./frontend/case-file-viewer/README.md)**
  - **Keywords**: `case-file-viewer`, `dossier`, `money-trail`, `mermaid-svg`, `exhibits-schedule`, `export-toolbar`
  - **Read When**: Developing, styling, or debugging the Case File Viewer at `/investigate` or its export facilities.
- **[`doc/frontend/data-estate/README.md`](./frontend/data-estate/README.md)**
  - **Keywords**: `data-estate`, `sql.js`, `wasm-sqlite`, `cfdi-xml`, `schema-validation`, `audit-modal`
  - **Read When**: Working on client-side Data Estate ingestion at `/investigate/data`, WASM SQLite, or audit stream modal.
- **[`doc/frontend/agent-orchestration-and-stream/README.md`](./frontend/agent-orchestration-and-stream/README.md)**
  - **Keywords**: `sse-stream`, `elevenlabs-voice`, `audio-player`, `agent-swimlanes`, `verdict-card`, `simulation-mode`
  - **Read When**: Consuming real-time SSE streams, managing ElevenLabs audio playback, or inspecting multi-agent UI tracks.
- **[`doc/frontend/core-shell-and-shared/README.md`](./frontend/core-shell-and-shared/README.md)**
  - **Keywords**: `app-shell`, `landing-page`, `navigation-bar`, `investigate-session`, `design-tokens`, `shared-utils`
  - **Read When**: Modifying root layouts, top navigation bar, dark theme tokens, or shared utilities (`formatCurrencyMXN`).

### [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md)
- **Keywords**: `react-flow`, `xyflow`, `dagre`, `graph-visualizer`, `custom-nodes`, `custom-edges`, `money-trail`
- **Read When**: Implementing or enhancing the interactive graph visualizer, custom bank account nodes, animated transaction edges, or Dagre layout calculation.
- **Skip When**: Working on anything outside the interactive graph canvas component.
### Data, Compliance & Evaluation
- **[`doc/data-and-compliance/README.md`](./data-and-compliance/README.md)**
  - **Keywords**: `estate-schema`, `cfdi-4.0`, `fraud-schemes`, `mexican-aml`, `cff-69b`, `amlsim`
  - **Read When**: Reviewing the 8-table relational estate contract, CFDI 4.0 metadata, fraud scheme definitions, or Mexican tax law.
- **[`doc/data-and-compliance/data_estate_seeder.md`](./data-and-compliance/data_estate_seeder.md)**
  - **Keywords**: `data-seeder`, `synthetic-generation`, `sqlite-seeding`, `seeder-config`
  - **Read When**: Generating synthetic financial estates or configuring the database seeder tool.
- **[`doc/evaluation-and-tooling/README.md`](./evaluation-and-tooling/README.md)**
  - **Keywords**: `eval-harness`, `run-audit`, `validate-format`, `multi-seed-benchmark`, `ground-truth-isolation`
  - **Read When**: Running multi-seed benchmark evaluations, using the offline audit CLI, or checking competition judging rules.

### [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md)
- **Keywords**: `amlsim`, `deterministic_filter`, `graph_pruning`, `cff_69b`, `efos_edos`, `uif_gafi`, `pgvector`, `materialidad`, `complexity-proofs`
- **Read When**: Understanding or generating AMLSim synthetic datasets, analyzing graph pruning math (cycles and passthrough ratios), studying algorithmic proofs, or structuring legal forensic audit reports under Mexican law (CFF Art. 69-B, NIF A-2, UIF ROI).
- **Skip When**: Writing frontend React components, styling CSS, or adjusting FastAPI routing boilerplate.

---

## 3. Recommended Progressive Retrieval Flow for AI Agents
## 3. Recommended Progressive Retrieval Flow for Agents

To optimize efficiency and avoid context degradation, follow this sequential retrieval procedure:

```mermaid
flowchart TD
    Start([Agent Assigned Task]) --> Step1[1. Read doc/index.md - Quick Task Dispatcher]
    Step1 --> Step2[2. Read ONLY the single targeted documentation file]
    Step2 --> Decision{Task fully covered?}
    Decision -- Yes --> Execute[Execute code changes / review]
    Decision -- Needs specific sub-topic --> Step3[3. Follow link to targeted blueprint e.g. react-flow-blueprint.md]
    Decision -- Needs global cross-cutting context --> Step4[4. Consult doc/README.md for system-level context]
    Step3 --> Execute
    Step4 --> Execute
```

1. **Step 1**: Consult `doc/index.md` (this file) to look up your task in the Quick Task Dispatcher.
2. **Step 2**: Open and read **only** the designated primary target file.
3. **Step 3**: If your task involves the interactive graph visualizer, proceed directly to `doc/frontend/react-flow-blueprint.md`.
4. **Step 4**: Consult `doc/README.md` **only** if you require cross-cutting architectural standards, environment variable lists, or deployment instructions.

1. **Step 1**: Read `doc/index.md` (this file) to identify the single targeted document for your assigned task.
2. **Step 2**: Open and read **only** that specific document (e.g. `doc/backend/api/README.md` for adding an endpoint).
3. **Step 3**: Only escalate to parent hubs (`doc/backend/README.md` or `doc/README.md`) if your task requires cross-cutting architectural context.
4. **Step 4**: Never bulk-read all documents in `doc/` — keep your context window lean and focused.
