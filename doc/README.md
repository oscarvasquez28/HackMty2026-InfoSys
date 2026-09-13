# Forensic Auditor: Master Architecture & Documentation Hub
# Polar Forensic Auditor: Master Architecture & Documentation Hub

[Agent Navigation & Context Index](./index.md) | [Architecture](./architecture/README.md) | [Backend](./backend/README.md) | [Frontend](./frontend/README.md) | [Data & Compliance](./data-and-compliance/README.md)
[Agent Routing Index](./index.md) | [Architecture](./architecture/README.md) | [Backend](./backend/README.md) | [Frontend](./frontend/README.md) | [Data & Compliance](./data-and-compliance/README.md) | [Evaluation & Tooling](./evaluation-and-tooling/README.md)

---

## 1. Executive Summary & System Purpose

**Forensic Auditor** is an enterprise-grade financial intelligence platform designed for high-performance forensic analysis, deterministic anti-money laundering (AML) detection, and automated legal audit reasoning on large transaction graphs (such as the IBM AMLSim benchmark).
**Polar Forensic Auditor** is an enterprise-grade financial intelligence platform engineered for automated fraud detection, deterministic anti-money laundering (AML) graph pruning, and agentic forensic audit reasoning across corporate and transactional estates.

Financial crime networks utilize sophisticated obfuscation strategies—such as circular layering (*smurfing* / round-tripping) and high-velocity mule conduits (*passthrough accounts*)—to mask illicit money trails within millions of legitimate transactions. Traditional rule engines trigger severe false-positive alert fatigue, while naively feeding raw transaction logs into Large Language Models (LLMs) saturates context windows and induces hallucinations on graph structures.
Financial crime networks employ sophisticated obfuscation typologies—such as circular layering (*smurfing* / round-tripping), high-velocity mule conduits (*passthrough accounts*), phantom vendor invoicing, and kickback schemes—to bury illicit money trails within millions of legitimate transactions. Naively feeding raw transaction logs into Large Language Models (LLMs) saturates token context windows, incurs unsustainable API costs, and induces severe structural hallucinations.

Forensic Auditor resolves this through a multi-tier hybrid architecture:
1. **Deterministic Algorithmic Graph Pruning**: Ingests transaction ledgers via [Polars](https://pola.rs/) in sub-second time, constructs directed multigraphs with [NetworkX](https://networkx.org/), and isolates elementary cycles ($k \le 5$) and rapid passthrough flows ($\ge 90\%$ pass-through within $\Delta t \le 48\text{h}$). This deterministically eliminates **85% to 98% of computational noise** before touching any LLM.
2. **External Agentic Legal Reasoning & Tooling**: Exposes dedicated database inspection endpoints and dynamic query facilities (`/api/v1/tools/*`) to external ReAct agents (e.g. n8n with Google Gemini), backed by managed PostgreSQL on **TigerData** equipped with `pgvector` for semantic legal searches against Mexican fiscal and AML frameworks (Art. 69-B del CFF, NIFs, and UIF/GAFI typologies).
3. **Reactive Real-Time Forensic Console**: Streams turn-by-turn investigative reasoning and verdicts to a **Next.js 14 / React 18** dashboard (`/investigate`) via Server-Sent Events (SSE), renders an interactive money trail graph via **React Flow (`@xyflow/react`)**, and vocalizes the final judicial dictamen via an **ElevenLabs** streaming voice proxy.
Polar resolves this through an end-to-end, multi-tiered forensic architecture:

1. **Deterministic Graph Pruning & Fraud Detectors**: Ingests transaction ledgers via [Polars](https://pola.rs/) in sub-second time, constructs directed multigraphs with [NetworkX](https://networkx.org/), isolates elementary cycles ($k \le 5$) and rapid passthrough flows ($\ge 90\%$ turnover in $\le 48\text{h}$), and applies specialized rule engines for the 5 contest fraud schemes. This deterministically eliminates **85% to 98% of computational noise** before activating LLM reasoning.
2. **Sequential Agentic Reasoning & Adversarial Review**: Coordinates sequential ReAct agent loops via **n8n** (powered by Google Gemini) equipped with AST-safe dynamic SQL inspection tools (`/api/v1/tools/*`). Each detected finding undergoes automated adversarial challenge and judicial evaluation before inclusion in the final dossier.
3. **Institutional Case File Viewer & Export Engine**: Renders an official 5-section judged case file dossier on a Next.js 14 / React 18 client (`/investigate`), complete with in-browser SVG Mermaid money trail rendering, evidentiary exhibit schedules, 2% per-table arithmetic peso reconciliation, and four-way export (Print/PDF, standalone HTML, Markdown, JSON).
4. **Browser-Native WebAssembly Data Estate**: Parses SQLite `.db`, per-table CSVs, CFDI 4.0 XML, and JSON in-memory via `sql.js` WASM (`/investigate/data`), allowing cross-checking of exhibits with zero server-side data retention.
5. **Real-Time Streaming & Audio Narration**: Streams turn-by-turn investigative reasoning to the browser via Server-Sent Events (SSE) and vocalizes judicial verdicts through an ElevenLabs streaming voice proxy with synthetic silent MP3 fallback.

---

## 2. Prior Documentation & Architectural Evolution Synthesis

This documentation synthesizes the initial prototype base, production architecture, and recent multi-agent forensic additions:
This documentation integrates and formalizes the technical evolution of the Polar codebase:

| Architectural Dimension | Initial Base Prototype | Target Production Architecture | Documentation Location |
| Architectural Tier | Initial Prototype Base | Target Challenge Platform | Documented Location |
| :--- | :--- | :--- | :--- |
| **System Ingestion & Pruning** | In-memory CSV upload with Polars & NetworkX pruning in `backend/api/routes/investigations.py`. | High-speed Polars/NetworkX pipeline with multigraph aggregation, structured subgraph metadata, and database persistence. | [`doc/backend/README.md`](./backend/README.md) |
| **Database Persistence** | Ephemeral in-memory dictionary (`INVESTIGATION_CASES`). | Production PostgreSQL with `pgvector` hosted on **TigerData**, integrated via Async **SQLAlchemy 2.0** for connection pooling, transaction persistence, and vector similarity search. | [`doc/backend/README.md`](./backend/README.md) |
| **AI Orchestration & Agent Tools** | Webhook proxy stub in `investigations.py` with fallback 6-step thought generator. | Dedicated read-only investigative tool endpoints (`/api/v1/tools/*`) with dynamic AST validation, alongside n8n webhook proxying and SSE reasoning fallback. | [`doc/architecture/README.md`](./architecture/README.md) |
| **Frontend Workspace** | Metric cards, text-based ThoughtStream console, and VerdictCard. | Dual-mode forensic workspace (`/investigate`) featuring 1-5 multi-file upload, interactive `@xyflow/react` + Dagre graph canvas, and telemetry cards. | [`doc/frontend/README.md`](./frontend/README.md) |
| **Audio Synthesis** | Direct backend streaming proxy to ElevenLabs with silent MPEG frame fallback. | Hardened streaming proxy preserving key confidentiality and zero-downtime offline presentation fallback (`X-Audio-Source` header). | [`doc/backend/README.md`](./backend/README.md) |
| **Legal & Regulatory Alignment** | Basic GAFI risk metrics in code comments. | Formal Mexican tax & AML compliance engine (Art. 69-B CFF EFOS/EDOS, NIF A-2 materiality, UIF ROI reporting, and pgvector HNSW index). | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) |
| **Ingestion & Pruning** | In-memory CSV upload with simple cycle detection. | Dual-pipeline: High-speed Polars/NetworkX AMLSim pruning + 8-table relational Data Estate ingestion with 5 deterministic scheme detectors. | [`doc/backend/graph-pruning/`](./backend/graph-pruning/README.md) |
| **Corporate Estate Auditing** | AMLSim single-file transaction CSVs only. | Full corporate financial estates: SQLite, CSV, CFDI 4.0 XML with 2% per-table arithmetic peso reconciliation. | [`doc/data-and-compliance/`](./data-and-compliance/README.md) |
| **Agentic Enrichment** | 6-step static mock thought generator. | Sequential one-by-one LLM adversarial review with per-finding judicial verdicts, dynamic AST tool queries, and offline deterministic fallback. | [`doc/backend/orchestration-tools/`](./backend/orchestration-tools/README.md) |
| **Client Workspace** | Monolithic metric cards and legacy simulation. | Dual workspace: Case File Viewer (`/investigate`) conforming to `submission_schema.json` and in-browser WASM SQLite Data Estate (`/investigate/data`). | [`doc/frontend/`](./frontend/README.md) |
| **Evaluation & Benchmark** | Ad-hoc pytest assertions. | Multi-seed evaluation harness (`eval/eval_harness.py`), synthetic estate generator (`eval/estate_generator.py`), and offline CLI runner (`run_audit.py`). | [`doc/evaluation-and-tooling/`](./evaluation-and-tooling/README.md) |
| **Persistence & Legal Knowledge** | Ephemeral module dictionary. | Managed TigerData PostgreSQL 16 with `pgvector` HNSW index for Mexican legal precedents (Art. 69-B CFF, NIF A-2, UIF/GAFI). | [`doc/backend/core-data/`](./backend/core-data/README.md) |

---

## 3. High-Level System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientTier ["1. Frontend Web Client (Next.js 14 / React 18)"]
    subgraph ClientLayer ["1. Next.js 14 Forensic Frontend Client (http://localhost:3000)"]
        Landing["Landing Page (app/page.tsx)"]
        Workspace["Workspace (app/investigate/page.tsx)"]
        UploadComp["Multi-File Ingestion<br/>(1-5 CSV Upload)"]
        Console["ThoughtStream.tsx<br/>(Terminal SSE Stream)"]
        Verdict["VerdictCard.tsx<br/>(Dictamen & Metricas)"]
        AudioUI["AudioPlayer.tsx<br/>(Equalizer Playback)"]
        ReactFlow["GraphVisualizer.tsx<br/>(@xyflow/react + Dagre)"]
        AppBar["Navigation Bar (InvestigateAppBar.tsx)"]
        SessionStore["In-Tab State (InvestigateSessionProvider.tsx)"]
        
        subgraph ViewCaseFile ["Case File Dossier (/investigate)"]
            CF_Doc["CaseFileDocument (5 Sections)"]
            CF_Trail["Money Trail (Mermaid Inline SVG)"]
            CF_Exh["Exhibits Table (2% Reconciliation)"]
            CF_Adv["Adversarial Review Block"]
            CF_Exp["Export Toolbar (PDF/HTML/MD/JSON)"]
        end

        subgraph ViewEstate ["Data Estate Workspace (/investigate/data)"]
            DE_WASM["sql.js WASM SQLite Engine"]
            DE_Upload["Upload Zone (DB, CSV, XML, JSON)"]
            DE_Preview["Table Previews & Summary"]
            DE_Modal["Estate Audit Streaming Modal"]
        end

        AudioPlayer["ElevenLabs Voice Player (AudioPlayer.tsx)"]
    end

    subgraph BackendTier ["2. Backend Core API (FastAPI / Python 3.11+)"]
        API["FastAPI Routing Hub<br/>(backend/main.py)"]
        IngestService["Ingestion Engine<br/>(services/ingestion.py - Polars)"]
        FilterService["Deterministic Graph Filter<br/>(services/deterministic_filter.py - NetworkX)"]
        ToolRouter["Agent Tools Router<br/>(api/routes/agent_tools.py)"]
        SSEProxy["SSE Event Streaming Proxy<br/>(api/routes/investigations.py)"]
        TTSProxy["ElevenLabs Audio Proxy<br/>(api/routes/tts.py)"]
        SQLAlchemyClient["TigerData DB Client<br/>(SQLAlchemy 2.0 + pgvector)"]
    subgraph BackendLayer ["2. FastAPI Forensic Backend Service (http://localhost:8000)"]
        API_Hub["FastAPI Routing Hub (main.py)"]
        
        subgraph Endpoints ["REST & SSE Route Handlers"]
            EP_Inv["/api/v1/investigations/* (Upload & Stream)"]
            EP_Est["/api/v1/estates/* (Upload & Audit Stream)"]
            EP_Tool["/api/v1/tools/* (AST Dynamic DB Tools)"]
            EP_TTS["/api/v1/tts/synthesize (Voice Proxy)"]
        end

        subgraph DetectorsTier ["Deterministic Detection Engine"]
            PolarsIngest["Polars Columnar Ingestion"]
            NetXFilter["NetworkX Cycle & Mule Pruning"]
            SchemeDetectors["5 Fraud Scheme Detectors"]
        end

        subgraph EstateServices ["Evidence & Output Generation"]
            EstConn["Data Estate Connector"]
            ExhBuilder["Exhibit Builder & 2% Reconciler"]
            CaseGen["Case File Generator (JSON & MD)"]
        end

        subgraph AgentService ["Agentic Orchestration"]
            ToolReg["Tool Registry & AST Column Whitelisting"]
            N8NEnrich["Sequential Adversarial Review Loop"]
        end
    end

    subgraph ExternalServices ["3. External Managed & Partner Services"]
        TigerData[("TigerData Cloud<br/>(PostgreSQL 16 + pgvector)")]
        N8NWorkflow["External n8n Orchestrator<br/>(Gemini 1.5/2.5 Flash Agent)"]
    subgraph ExternalServices ["3. Managed Cloud & Orchestration Services"]
        TigerData[("TigerData Cloud PostgreSQL 16<br/>pgvector HNSW Legal Index")]
        N8NWorkflow["n8n Orchestrator<br/>(Gemini ReAct Agent)"]
        ElevenLabsAPI["ElevenLabs TTS API<br/>(eleven_multilingual_v2)"]
    end

    %% Flow connections
    UploadComp -->|1. POST /upload CSV| API
    API --> IngestService
    IngestService --> FilterService
    FilterService -->|2. Subgrafo Sospechoso| API
    API -->|3. Persist Case & Graph| SQLAlchemyClient
    SQLAlchemyClient <-->|SSL Connection Pool| TigerData
    %% Client Internal Flow
    Landing --> AppBar --> SessionStore
    SessionStore --> ViewCaseFile
    SessionStore --> ViewEstate
    DE_WASM -.->|Cross-Examine Exhibits| CF_Exh

    Workspace -->|4. GET /stream EventSource| SSEProxy
    SSEProxy -->|5. Webhook POST case_id| N8NWorkflow
    N8NWorkflow <-->|Read-Only Agent Tools /tools/*| ToolRouter
    ToolRouter <-->|AST Safe Queries & pgvector| SQLAlchemyClient
    N8NWorkflow -->|6. Stream Thoughts / Verdict| SSEProxy
    SSEProxy -->|SSE event: thought| Console
    SSEProxy -->|SSE event: verdict| Verdict
    API -->|Subgraph Nodes & Edges| ReactFlow
    %% Client-Backend Connections
    DE_Modal -->|POST multipart estate| EP_Est
    EP_Est -->|SSE audit thoughts & verdict| DE_Modal
    ViewCaseFile -->|POST /tts/synthesize| EP_TTS
    EP_TTS --> AudioPlayer

    Verdict --> AudioUI
    AudioUI -->|7. POST /tts/synthesize| TTSProxy
    TTSProxy -->|Proxy Streaming Audio| ElevenLabsAPI
    ElevenLabsAPI -->|audio/mpeg Stream| TTSProxy
    TTSProxy -->|Chunked Audio Stream| AudioUI
    %% Backend Flow
    API_Hub --> Endpoints
    EP_Inv --> PolarsIngest --> NetXFilter
    EP_Est --> EstConn --> SchemeDetectors --> ExhBuilder
    ExhBuilder --> N8NEnrich
    N8NEnrich <--> ToolReg
    N8NEnrich --> CaseGen

    %% External Connections
    ToolReg <--> TigerData
    N8NEnrich <--> N8NWorkflow
    EP_TTS <--> ElevenLabsAPI
```

---

## 4. Master Documentation Tree

The complete technical documentation is structured as follows:
Click any link below to navigate to the specialized documentation module:

```text
doc/
├── README.md                           # Master Architecture & Documentation Hub (This Document)
├── index.md                            # Mandatory AI Agent Routing Index (Prevents Context Exhaustion)
├── README.md                                    # Master Architecture & Hub (This Document)
├── index.md                                     # Mandatory AI Agent Routing Index
│
├── architecture/                       # Global Topology & Cross-Cutting Integration
│   └── README.md                       # 6-stage lifecycle, container topology, SSE JSON schemas, security
├── architecture/                                # System Topology & Integration
│   └── README.md                                # Multi-service layout, container topology, SSE contracts
│
├── backend/                            # FastAPI Core, Polars Ingestion & NetworkX Pruning
│   └── README.md                       # API reference, Polars alias mapper, cycle & passthrough math,
│                                       # SQLAlchemy TigerData blueprint, ElevenLabs proxy, pytest suite
├── backend/                                     # Backend Architecture Hub
│   ├── README.md                                # Service hub, request flows, tech stack
│   ├── api/README.md                            # FastAPI routes, SSE streaming, CLI runner
│   ├── graph-pruning/README.md                  # Polars ingestion, NetworkX graph math, 5 fraud detectors
│   ├── estate-exhibits/README.md                # SQLite connector, exhibit builder, 2% peso reconciliation
│   ├── orchestration-tools/README.md            # Dynamic agent tools, AST SQL queries, n8n enrichment
│   ├── core-data/README.md                      # SQLAlchemy models, TigerData pgvector, PII masking, config
│   └── tests/README.md                          # 160 tests across 24 suites, challenge milestones, e2e test
│
├── frontend/                           # Next.js 14 App Router & Reactive Streaming UI
│   ├── README.md                       # Component hierarchy, SSE event consumption, audio player lifecycle,
│   │                                   # state machine, types, and critical bug resolutions
│   └── react-flow-blueprint.md         # Full implementation design for @xyflow/react Money Trail Visualizer
├── frontend/                                    # Frontend Applications Hub
│   ├── README.md                                # Client architecture, workspaces, styling, session layout
│   ├── case-file-viewer/README.md               # Dossier viewer, Mermaid money trails, export engine
│   ├── data-estate/README.md                    # sql.js WASM workspace, schema validation, audit modal
│   ├── agent-orchestration-and-stream/README.md # SSE streaming hooks, multi-agent tracks, ElevenLabs audio
│   ├── core-shell-and-shared/README.md          # Next.js 14 layout, session provider, forensic design tokens
│   ├── case-file-plan.md                        # Historical case file implementation blueprint
│   ├── case-file-progress.md                    # Implementation roadmap & milestone checklist
│   └── react-flow-blueprint.md                  # Exploratory React Flow + Dagre canvas specification
│
└── data-and-compliance/                # Benchmark Schemas & Mexican AML Regulatory Framework
    └── README.md                       # IBM AMLSim CSV schema, deterministic graph pruning formulas,
                                        # Art. 69-B CFF (EFOS/EDOS), NIF A-2 materiality, UIF/GAFI standards
├── data-and-compliance/                         # Relational Schemas & Legal Standards
│   ├── README.md                                # 8-table estate schema, CFDI 4.0, 5 fraud schemes, Mexican law
│   └── data_estate_seeder.md                    # Synthetic estate generator specification
│
└── evaluation-and-tooling/                      # Benchmark & CLI Tooling
    └── README.md                                # Eval harness, seed benchmarks, offline audit CLI, format validator
```

### Module Quick Links
- **[System Architecture & Integration (`doc/architecture/README.md`)](./architecture/README.md)**: Detailed end-to-end dataflow, container orchestration with `docker-compose.yml`, unified SSE event schemas (`thought`, `verdict`), and multi-service topology.
- **[Backend Service & Analytics (`doc/backend/README.md`)](./backend/README.md)**: Polars ingestion mechanics, NetworkX deterministic pruning, public REST/SSE endpoints, testing patterns, and the SQLAlchemy connection blueprint to remote TigerData PostgreSQL with `pgvector`.
- **[Frontend Client Dashboard (`doc/frontend/README.md`)](./frontend/README.md)**: Next.js App Router architecture, UI component catalog, custom streaming hooks (`useInvestigationStream`, `useAudioStream`), and client-side considerations.
- **[React Flow Visualizer Blueprint (`doc/frontend/react-flow-blueprint.md`)](./frontend/react-flow-blueprint.md)**: Complete implementation guide for `@xyflow/react` and `@dagrejs/dagre` graph visualizer.
- **[Data Schemas & Forensic Compliance (`doc/data-and-compliance/README.md`)](./data-and-compliance/README.md)**: IBM AMLSim schema specs, graph mathematical invariants, and Mexican legal compliance framework (CFF Art. 69-B, NIFs, UIF/GAFI).
- **[AI Agent Routing Index (`doc/index.md`)](./index.md)**: Context-saving index designed specifically for future AI agents to identify single-file targets for specific coding tasks.

---

## 5. Cross-Cutting Concerns

### 5.1 Environment Configuration & Secret Management
All sensitive API credentials and integration endpoints are managed via environment variables and shielded from client exposure:
- `ELEVENLABS_API_KEY`: Kept strictly on the backend. The frontend communicates exclusively with the backend `/api/v1/tts/synthesize` proxy endpoint.
- `DATABASE_URL`: Connection string for the external TigerData PostgreSQL instance (`postgresql+asyncpg://...`), secured with SSL mode (`sslmode=require`).
- `N8N_WEBHOOK_URL`: Configurable webhook endpoint pointing to the external n8n ReAct agent runner. If unset or unreachable, the backend seamlessly activates high-fidelity local simulation fallback.
- `NEXT_PUBLIC_API_URL`: Configured on the frontend (`http://localhost:8000` in dev) to route API and SSE requests to FastAPI.
### 1. Data Privacy and PII Masking
- The backend features `backend/core/masking.py`, which sanitizes sensitive tax IDs (RFCs), bank account numbers (CLABE), and individual names before logging or sending data to external LLM providers.
- The frontend operates with zero server-side state on `/investigate/data`: files loaded into `sql.js` reside solely in browser memory and are wiped upon reload.

### 5.2 Error Handling & Resilient Fallbacks
- **Zero-Downtime Audio Playback**: If `ELEVENLABS_API_KEY` is not provided or fails, `backend/api/routes/tts.py` generates a valid minimal MPEG audio frame (silent MP3) with header `X-Audio-Source: synthetic-fallback-mode`, ensuring client audio players do not crash during offline demonstrations.
- **SSE Stream Resilience**: If the external n8n webhook is offline or times out, the backend gracefully catches the connection exception and yields the built-in 6-phase forensic reasoning steps, ensuring uninterrupted UI demonstrations.
- **Dynamic Column Aliasing**: The Polars ingestion engine handles irregular column naming across banking datasets without code modifications using canonical alias matching (`origin`, `nameorig`, `from_account`, etc.).
### 2. High-Fidelity Zero-Downtime Fallback Strategy
- **ElevenLabs Speech Synthesis**: If `ELEVENLABS_API_KEY` is not set or upstream returns an error (401, 429, 500, timeout), the backend immediately yields a valid, synthetic MPEG-1 Layer 3 silent audio frame (`X-Audio-Source: synthetic-fallback-mode`) to prevent UI lockup.
- **n8n / LLM Enrichment**: If `N8N_WEBHOOK_URL` is unreachable, the backend seamlessly switches to an offline deterministic reasoning engine that generates rigorous forensic findings and legal analysis.
- **Database Resilience**: If TigerData PostgreSQL is offline, the backend seamlessly falls back to in-memory caching for AMLSim ingestion.

### 5.3 Concurrency & Performance Optimization
- **Columnar Pre-filtering with Polars**: Polars processes tabular CSV ledgers using SIMD and multi-core parallelism, performing column selection, filtering ($>0$), and type casting up to 30x faster than standard Pandas.
- **Computational Cycle Bounds in NetworkX**: Cycle detection uses `nx.simple_cycles` constrained by `MAX_CYCLE_LENGTH` (default $k=5$) to avoid exponential path exploration stalls on dense subgraphs.
- **Non-blocking SSE Proxying**: Event streaming utilizes asynchronous generators (`async for line in response.aiter_lines()`) and `asyncio.sleep()`, preventing thread pool starvation in Uvicorn.
### 3. Evidentiary Strictness & Mathematical Reconciliation
- Accusations cannot cite unverified claims: every cited `record_id` must resolve against the corporate estate database.
- Per-table amounts must reconcile arithmetically within a **2% error tolerance**:
  $$\left|\frac{\sum \text{Exhibit Amounts} - \text{Claimed Finding Amount}}{\text{Claimed Finding Amount}}\right| \le 0.02$$
- Double-counting across stages (e.g. an invoice and the corresponding bank transfer that settled it) is prevented by computing reconciliation per table.

### 5.4 Testing & Quality Assurance
The codebase includes a comprehensive automated test suite across 13 test modules (121 tests) in `backend/tests/` executed via `pytest`:
- End-to-end pipeline verification in `backend/tests/test_pipeline.py`.
- Algorithmic pruning unit tests in `backend/tests/test_deterministic_filter.py`.
- TigerData PostgreSQL async persistence and pooling in `backend/tests/test_database.py`.
- Agent tool inspection and AST query security in `backend/tests/test_agent_tools.py`.
- Asserts that deterministic pruning eliminates legitimate payroll and merchant noise.
- Connects to the SSE endpoint using `httpx.ASGITransport` to validate `thought` and `verdict` payloads.
- Validates the ElevenLabs audio synthesis proxy endpoint and silent frame fallback.
### 4. Mandatory Ground Truth Isolation
- Ground truth keys are strictly isolated in `eval/` and `data/` and must never be imported, referenced, or accessible to agent tools or the backend reasoning runtime.

---

## 6. Quickstart Commands

```bash
# 1. Backend Setup & Test Verification
python -m venv venv && .\venv\Scripts\activate
pip install -r backend/requirements.txt
python -m pytest backend/tests/test_pipeline.py -v

# 2. Run Backend Server (http://localhost:8000)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend Setup & Build Verification (http://localhost:3000)
cd frontend
npm install
npm run build
npm run dev

# 4. Offline Zero-Network Audit CLI
python run_audit.py --estate data/estate.db --output submission.json
```
