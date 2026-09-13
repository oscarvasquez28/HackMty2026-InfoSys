# AGENTS.md — Forensic Auditor

Entry point for agents and new contributors. This file is intentionally short: it gives you the
architecture, the commands, and the code conventions, then routes you into `doc/` for depth.

**Project**: monorepo AML (anti-money-laundering) forensic auditor. A FastAPI backend ingests
IBM AMLSim transaction CSVs with Polars, prunes them deterministically with NetworkX graph
algorithms (closed cycles + high-velocity pass-through accounts), streams agent reasoning to a
Next.js dashboard over Server-Sent Events, and vocalizes the final verdict through an ElevenLabs
proxy.

---

## 1. Documentation Map (read top-down, stop as soon as you have enough)

The docs are a tree: general at the root, increasingly specific as you descend. **Do not read the
whole tree** — it will exhaust your context.

```text
AGENTS.md                              # Level 0 — you are here: conventions, commands, routing
README.md                              # Level 0 — repo tour + quickstart (Spanish)
doc/
├── index.md                           # Level 1 — ROUTING INDEX: task -> single target file
├── README.md                          # Level 1 — master architecture hub, cross-cutting concerns
├── architecture/README.md             # Level 2 — 6-stage lifecycle, container topology, SSE contracts
├── backend/README.md                  # Level 2 — FastAPI routes, Polars ingestion, NetworkX math,
│                                      #            SQLAlchemy/TigerData blueprint, ElevenLabs proxy
├── frontend/README.md                 # Level 2 — App Router layout, components, streaming hooks
│   └── react-flow-blueprint.md        # Level 3 — @xyflow/react + Dagre money-trail visualizer
└── data-and-compliance/README.md      # Level 2 — AMLSim schema, pruning proofs, Mexican AML law
```

**Retrieval order**: `AGENTS.md` (this file) → <ref_file file="C:\Users\Lenovo\Downloads\HackMty2026\HackMty2026-InfoSys\doc\index.md" /> to
pick the *one* file your task needs → that file → only escalate to
<ref_file file="C:\Users\Lenovo\Downloads\HackMty2026\HackMty2026-InfoSys\doc\README.md" /> if you need
cross-cutting system context.

| Your task | Go to |
| :--- | :--- |
| Anything — find the right file first | `doc/index.md` |
| System-wide context, tech stack, env vars, fallback strategy | `doc/README.md` |
| Docker topology, SSE/webhook JSON contracts, service boundaries | `doc/architecture/README.md` |
| FastAPI routes, Polars ingestion, graph algorithms, TTS proxy, pytest | `doc/backend/README.md` |
| Dashboard UI, components, `useInvestigationStream` / `useAudioStream` | `doc/frontend/README.md` |
| Interactive graph canvas (React Flow, Dagre, custom nodes/edges) | `doc/frontend/react-flow-blueprint.md` |
| AMLSim CSV schema, pruning math, Mexican AML/fiscal compliance | `doc/data-and-compliance/README.md` |

---

## 2. Architecture at a Glance

```text
CSV (IBM AMLSim)
   │  POST /api/v1/investigations/upload
   ▼
backend/services/ingestion.py          Polars: alias-resolve columns -> origin/destination/amount/timestamp
   ▼
backend/services/deterministic_filter.py
   ├─ build_transaction_graph()        NetworkX DiGraph, aggregated edges + per-node in/out flows & timestamps
   ├─ detect_closed_cycles()           nx.simple_cycles bounded by MAX_CYCLE_LENGTH (default 5)
   ├─ detect_passthrough_accounts()    min(in,out)/max(in,out) >= 0.90 within <= 48h
   └─ apply_deterministic_filter()     -> { subgraph, metrics, patterns }   (85-98% noise pruned)
   ▼
backend/api/routes/investigations.py   in-memory INVESTIGATION_CASES[case_id]
   │  GET /api/v1/investigations/{case_id}/stream  (text/event-stream)
   ├─ n8n webhook proxy if N8N_WEBHOOK_URL set and returns text/event-stream
   └─ else local 6-phase reasoning fallback
   ▼
SSE events: `thought` (xN) then `verdict` (terminal, client closes)
   ▼
frontend/hooks/useInvestigationStream.ts -> ThoughtStream.tsx / VerdictCard.tsx
   ▼
POST /api/v1/tts/synthesize -> backend/api/routes/tts.py -> ElevenLabs (audio/mpeg stream)
   └─ no API key? emits a silent MP3 frame with header X-Audio-Source: synthetic-fallback-mode
```

Layering rules: `api/routes/*` handles HTTP/validation only; all analytics live in `services/*`;
configuration only ever comes from `backend/core/config.py::settings` (never `os.environ` inline).
`docker-compose.yml` additionally provisions `pgvector/pgvector:pg16` and `n8nio/n8n` for the
orchestration/vector-search tier (production targets managed PostgreSQL on TigerData).

---

## 3. Commands

Run backend commands **from the repo root** — imports are absolute (`from backend.core.config import settings`),
so `cd backend` will break them.

```bash
# Backend setup
python -m venv venv && .\venv\Scripts\activate      # Linux/macOS: source venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

# Backend dev server -> http://localhost:8000, Swagger at /api/v1/docs
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Tests (e2e pipeline: upload -> pruning -> SSE -> TTS). Currently 2 passed.
python -m pytest backend/tests/test_pipeline.py -v

# Frontend -> http://localhost:3000
cd frontend && npm install && cp .env.example .env.local
npm run dev            # dev server
npm run build          # production build == de-facto typecheck (tsc noEmit via next)
npm run lint           # next lint

# Full stack (backend + frontend + pgvector + n8n)
docker compose up --build
```

Health probe: `GET /health`. Sample dataset for manual runs: `data/sample_amlsim.csv`.

---

## 4. Code Conventions

### Backend (Python 3.11+, FastAPI)
- **Imports**: absolute from the `backend` package. Order: stdlib → third-party → local.
- **Config**: extend `Settings` in `backend/core/config.py` (Pydantic Settings, `case_sensitive=True`,
  `extra="ignore"`), add the key to `backend/.env.example`, then import the `settings` singleton.
  Algorithm thresholds are settings, never literals — pass them as function defaults
  (`max_cycle_length: int = settings.MAX_CYCLE_LENGTH`) so tests can override them.
- **Routers**: one `APIRouter` per file with `prefix=` and `tags=`, exported as `router`, registered
  in `backend/main.py` under `settings.API_V1_STR`. Raise `HTTPException` with `status.HTTP_*`
  constants — never bare integers.
- **Types**: annotate all signatures, including return types (`-> Tuple[pl.DataFrame, Dict[str, Any]]`,
  `-> AsyncGenerator[str, None]`). Request bodies are Pydantic `BaseModel` with `Field(...)` metadata.
- **Docstrings**: triple-quoted, in **English**, on every public function and route; document the
  `Returns:` shape when it is a dict/tuple.
- **Services** return plain JSON-serializable dicts (`{"subgraph": ..., "metrics": ..., "patterns": ...}`),
  never NetworkX or Polars objects, and round monetary floats to 2 decimals (ratios to 4).
- **Errors**: `ValueError` from services → `422` at the route; unexpected → `500`. External
  integrations (n8n, ElevenLabs) must degrade gracefully to a deterministic local fallback rather
  than fail the request — this is a demo-critical invariant.
- **Async**: all I/O is `async`; use `httpx.AsyncClient` with an explicit `timeout=`, and stream with
  async generators (`aiter_lines()` / `aiter_bytes()`) instead of buffering.
- **Naming**: `snake_case` functions/vars, `SCREAMING_SNAKE` module constants (`COLUMN_ALIASES`,
  `INVESTIGATION_CASES`), verb-first service functions (`read_amlsim_csv`, `detect_closed_cycles`).
- **Machine-readable enums** stay uppercase ASCII (`CIRCULAR_FLOW_CYCLE`, `PASSTHROUGH_BRIDGE`).

### Frontend (Next.js 14 App Router, React 18, TypeScript strict)
- **`"use client"`** on the first line of every interactive component and hook.
- **Imports** use the `@/*` alias from `tsconfig.json` (`@/types/investigation`, `@/lib/utils`,
  `@/components/AudioPlayer`) — no deep relative paths.
- **Components**: named exports, `PascalCase` file = component name, typed as
  `React.FC<XProps>` with a local `interface XProps`. Icons come from `lucide-react`.
- **Hooks**: `use*.ts` in `hooks/`, each declaring an explicit `UseXReturn` interface; wrap callbacks
  in `useCallback`, hold `EventSource`/`AbortController` in `useRef`, and always clean up in a
  `useEffect` teardown.
- **Types**: every SSE/REST payload has a mirrored `interface` in `types/investigation.ts` whose field
  names match the backend JSON **exactly** (`snake_case` on the wire — do not camelCase them).
- **Styling**: Tailwind utility classes inline; dark forensic palette via the semantic tokens defined
  in `tailwind.config.js` (`background`, `surface`, `surface-border`, `brand.*`) rather than raw hex.
  Conditional classes today use template literals plus a small helper function (see
  `getRiskBadgeColor` in `VerdictCard.tsx`); `clsx` + `tailwind-merge` are available in `@/lib/utils`
  for anything more complex.
- **Formatting**: currency through `formatCurrencyMXN` in `@/lib/utils`, never ad-hoc `toLocaleString`.
- **Language**: code, identifiers, and comments in English; **user-facing strings and forensic
  terminology in Spanish** (`"Dictamen Pericial Forense"`, risk levels `CRÍTICO`/`ALTO`/`MEDIO`/`BAJO`).

### Shared contracts
- Base URL from `process.env.NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); all API paths are
  prefixed `/api/v1`.
- SSE frames are emitted as `event: <name>\ndata: <json>\n\n`; `thought` repeats, `verdict` terminates
  the stream. Changing either payload means updating **three** places: the producer in
  `investigations.py`, the TS interface in `types/investigation.ts`, and
  `doc/architecture/README.md`.
- Secrets stay server-side. `ELEVENLABS_API_KEY` and `DATABASE_URL` are never exposed to the client;
  only `NEXT_PUBLIC_*` vars reach the browser.

---

## 5. Verification Before Declaring Done

1. `python -m pytest backend/tests/test_pipeline.py -v` from the repo root (expects 2 passing tests).
2. `cd frontend && npm run build` for any TS/TSX change (this is the typecheck).
3. If you touched an SSE payload, graph metric, or endpoint path, update the corresponding `doc/`
   file in the same change.

---

## 6. Known Gotchas

- **A bare `.gitignore` pattern at any depth swallows a same-named frontend path**: this has bitten
  the project twice now — a bare `lib/` pattern matched `frontend/lib/utils.ts` (`cn`,
  `formatCurrencyMXN`), and later a bare `data` pattern matched `frontend/app/investigate/data/` (the
  Data Estate route). Both are fixed by anchoring to the repo root (`/lib/`, `/data`) so only the
  top-level folder is ignored. If a build fails to find a frontend file that is clearly present on
  disk, check `git check-ignore -v <path>` before assuming the file is missing.
- **`mermaid` is pinned to `11.17.2` (exact)**: `mermaid@12` requires Node ≥ 22.12; this repo targets
  Node 20 everywhere (Dockerfile and local dev). Don't bump the major version without also bumping
  the Node target. `sql.js`/`papaparse` are pinned exact for the same "deliberate upgrade only" reason.
- **Mermaid must render through its sandbox**: `globals.css`'s reduced-motion block sets
  `* { transition-duration: 0.01ms !important }`, which puts transitions on SVG geometry; Mermaid then
  measures mid-transition values and emits a tiny, off-center diagram with a huge viewBox (only on
  machines with reduced motion enabled). `lib/caseFile/mermaid.ts::renderMermaidSvg` renders inside
  the off-screen `.mermaid-sandbox`, which opts out of transitions — never call `mermaid.render`
  without it. `frontend/fixtures/case-file.dense-trail.json` is the visual regression fixture.
- **`sql.js`'s WASM binary is generated, not committed**: `npm run dev`/`npm run build` run a
  `predev`/`prebuild` step that copies it to `frontend/public/sql-wasm.wasm` (gitignored). If the Data
  Estate page (`/investigate/data`) throws a WASM-load error after a fresh clone, run
  `npm run copy:sqlwasm` from `frontend/` manually.
- **`validate_format.py` needs `-X utf8` on Windows**: without it, `Path.read_text()` uses the system
  codepage (cp1252) and raises on the accented characters in Spanish sample data. Always run it as
  `python -X utf8 student-materials/forensic-auditor/validate_format.py --submission <file>.json`.
- **Case storage is in-memory**: `INVESTIGATION_CASES` is a module-level dict, so cases vanish on
  reload and are not shared across Uvicorn workers. Persistence to TigerData PostgreSQL +
  `pgvector` is designed but not implemented — blueprint in `doc/backend/README.md`.
- **`timestamp` units are dataset-defined**: the pass-through window compares raw timestamp deltas
  against `PASS_THROUGH_WINDOW_HOURS`, i.e. AMLSim `step` values are treated as hours. Datasets with
  epoch seconds need conversion during ingestion.
- **n8n and ElevenLabs are optional**: with `N8N_WEBHOOK_URL` unreachable or the API key unset/left as
  `your_...`, the system silently serves the local fallback stream and a silent MP3. Confirm which
  path ran (`X-Audio-Source` header, thought wording) before debugging "wrong" output.

## 7. Current Frontend Ownership and Entry Points

- Backend development is owned by another contributor. Keep UI work frontend-only; coordinate explicitly before touching backend code, tests, services or configuration.
- The Polar landing page is `/`; **Explore the platform** and **Explore Polar** open `/investigate`.
- Per the user's preference, the current workspace interface is **English**, overriding the earlier Spanish UI convention. Backend narrative text and the case file's own data (narratives, legal names) retain their supplied language.
- **`/investigate` is the Case File Viewer**: loads a case file JSON — conforming to
  [`student-materials/forensic-auditor/submission_schema.json`](../student-materials/forensic-auditor/submission_schema.json)
  — from a bundled sample, a local file, the Data Estate page, or the backend's proposed (not yet
  implemented) `/case-file` endpoint, and presents it as an animated, chapter-by-chapter guided tour
  (the full vertical document stays mounted but hidden as the source for Print/HTML) with a
  ZIP/Print/HTML/Markdown/JSON export toolbar — the ZIP bundle also auto-downloads once per loaded
  case file when `diagramsSettled` first turns true. See `doc/frontend/README.md` §10 (§10.6 for the tour) for the pipeline and
  `doc/architecture/README.md` §4.6 for the JSON contract.
- **`/investigate/data` is the Data Estate page**: loads SQLite `.db`, CSV, CFDI 4.0 XML, or JSON
  entirely in the browser (`sql.js` WASM), validates it against `estate_schema.sql`, and lets the Case
  File Viewer check exhibits against it. See `doc/frontend/README.md` §11. The loaded case file and
  estate are shared for the tab's lifetime (`InvestigateSessionProvider`) but never persist across a reload.
- **`/investigate/simulation` is the legacy frontend-only simulation** (deprecated, kept for reference
  behind a banner). It accepts 1-5 CSV files and uses local sample values for visual context; agent
  findings and the final risk level are illustrative. It does not call the backend or claim real fraud
  analysis, and plays no part in the two entry points above.
- Do not fabricate live backend activity if the application is later reconnected to SSE. Keep simulation and live-analysis modes explicitly distinct.
- From `frontend`, `npx --no-install tsc --noEmit --incremental false` provides a typecheck without writing to `.next`. The production build is still required; ask for assistance if Windows locks `.next/trace` rather than deleting build files or stopping another contributor's processes — stopping a dev server *you* started in the same session first is fine and often resolves it.

