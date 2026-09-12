# Documentation Agent Routing Index 🧭⚡

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
| **Polars data ingestion, column alias resolution, or CSV cleansing** | [`doc/backend/README.md`](./backend/README.md) | `read_amlsim_csv()` implementation, column mapping, and Polars filtering. | UI styling or legal jurisprudence docs |
| **NetworkX graph building, cycle detection, or pass-through account algorithms** | [`doc/backend/README.md`](./backend/README.md) | Mathematical graph algorithms, `MAX_CYCLE_LENGTH`, and pruning telemetry. | Frontend components or audio synthesis code |
| **ElevenLabs TTS streaming proxy, API key shielding, or silent MP3 fallback** | [`doc/backend/README.md`](./backend/README.md) | Audio streaming proxy endpoint, chunked transfer, and offline fallback frame. | Frontend UI layout or database models |
| **Next.js dashboard UI, component hierarchy, or layout** | [`doc/frontend/README.md`](./frontend/README.md) | App Router (`page.tsx`, `layout.tsx`), FileUpload, ThoughtStream, VerdictCard. | Backend Python code or database models |
| **Frontend streaming hooks (`useInvestigationStream` or `useAudioStream`)** | [`doc/frontend/README.md`](./frontend/README.md) | `EventSource` lifecycle, Blob URL audio synthesis, and abort signaling. | Graph pruning math or Docker configs |
| **Fixing missing `frontend/lib/utils.ts` / `formatCurrencyMXN` build error** | [`doc/frontend/README.md`](./frontend/README.md) | Section 6 edge cases identifying the missing utility and exact solution. | Backend code or AMLSim schemas |
| **Implementing the interactive AML Money Trail Visualizer with `@xyflow/react`** | [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md) | React Flow 12+ setup, `@dagrejs/dagre` layout engine, custom nodes & edges. | Backend algorithms or legal compliance docs |
| **IBM AMLSim benchmark dataset schema, column formats, or synthetic sample** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Transaction schema fields, aliases, and `sample_amlsim.csv` patterns. | Frontend components or Dockerfiles |
| **Deterministic graph pruning mathematical formulas and noise reduction proof** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Bounded cycle equations, flow retention ratios, and smurfing logic. | REST endpoints or React hooks |
| **Mexican legal AML compliance (Art. 69-B CFF EFOS/EDOS, NIFs, UIF/GAFI ROI)** | [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md) | Mexican tax/AML statutes, operational materiality, and forensic defense proofs. | Frontend styling or API routing boilerplate |

---

## 2. Segment Catalog & Keyword Map

Scan this catalog to match domain concepts to their home directory:

### [`doc/architecture/README.md`](./architecture/README.md)
- **Keywords**: `architecture`, `topology`, `docker-compose`, `sse-contracts`, `n8n-integration`, `tigerdata`, `end-to-end`, `event-schemas`
- **Read When**: Designing cross-service integrations, configuring container environments, reviewing SSE event contracts, or updating communication boundaries between FastAPI, Next.js, TigerData, and n8n.
- **Skip When**: Modifying specific React UI components, tuning Python graph algorithms, or writing database migrations.

### [`doc/backend/README.md`](./backend/README.md)
- **Keywords**: `fastapi`, `polars`, `networkx`, `sse-streaming`, `elevenlabs`, `tigerdata-sqlalchemy`, `pytest`, `httpx`
- **Read When**: Developing backend API routes, improving Polars ingestion speed, tuning NetworkX pruning, implementing SQLAlchemy models for TigerData, or updating the ElevenLabs voice proxy.
- **Skip When**: Editing Next.js JSX/TSX components, styling with Tailwind, or reading Mexican statutory law texts.

### [`doc/frontend/README.md`](./frontend/README.md)
- **Keywords**: `nextjs`, `react`, `tailwindcss`, `sse-streaming`, `audio-streaming`, `components`, `hooks`, `types`
- **Read When**: Modifying the web dashboard, adding UI components, handling SSE connection state in React, managing audio playback, or resolving frontend build errors.
- **Skip When**: Writing Python backend logic, tuning graph pruning algorithms, or designing database schemas.
- **Sub-module**:
  - [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md) - Complete design blueprint for the `@xyflow/react` AML Money Trail interactive graph visualizer.

### [`doc/frontend/react-flow-blueprint.md`](./frontend/react-flow-blueprint.md)
- **Keywords**: `react-flow`, `xyflow`, `dagre`, `graph-visualizer`, `custom-nodes`, `custom-edges`, `money-trail`
- **Read When**: Implementing or enhancing the interactive graph visualizer, custom bank account nodes, animated transaction edges, or Dagre layout calculation.
- **Skip When**: Working on anything outside the interactive graph canvas component.

### [`doc/data-and-compliance/README.md`](./data-and-compliance/README.md)
- **Keywords**: `amlsim`, `deterministic_filter`, `graph_pruning`, `cff_69b`, `efos_edos`, `uif_gafi`, `pgvector`, `materialidad`
- **Read When**: Understanding or generating AMLSim synthetic datasets, analyzing graph pruning math (cycles and passthrough ratios), or structuring legal forensic audit reports under Mexican law (CFF Art. 69-B, NIF A-2, UIF ROI).
- **Skip When**: Writing frontend React components, styling CSS, or adjusting FastAPI routing boilerplate.

---

## 3. Recommended Progressive Retrieval Flow for AI Agents

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

