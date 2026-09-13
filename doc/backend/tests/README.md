# Backend Testing Framework & Test Suite Catalog

[← Back to Backend Documentation](../README.md) | [Master Architecture](../../README.md) | [Agent Routing Index](../../index.md)

---

## 1. Module Overview & Core Responsibilities

The **Backend Testing Framework** for the Polar Forensic Auditor AML Engine provides an exhaustive, multi-tiered verification harness. Spanning 24 suite components (23 functional test modules containing 160 automated tests, plus the package initializer `__init__.py`), it guarantees mathematical precision, zero-leak resource management, deterministic graph pruning, adversarial resilience, and legal compliance across all financial auditing operations.

```
backend/tests/
├── __init__.py                          # Package initializer enabling module discovery
├── test_pipeline.py                     # Baseline ingestion, graph pruning, and synthetic fallbacks
├── test_challenge_m2_streaming.py       # Milestone 2: 6-phase SSE streaming & pool safety
├── test_challenge_m3_tools.py           # Milestone 3: SQLi prevention, scoping & operator matrix
├── test_challenger_m3_2.py              # Milestone 3: Dual-engine DB vs in-memory parity
├── test_challenge_m4_tts.py             # Milestone 4: Speech synthesis boundaries & upstream faults
├── test_challenge_m4_2.py               # Milestone 4: Client cancellation, socket leaks & canary keys
├── test_agent_tools.py                  # Dedicated tool endpoints & composable query builder
├── test_database_tools.py               # Estate catalog, table readers & exhibit registration
├── test_forensic_tools_suite.py         # 11 forensic agent tools & banking table targets
├── test_deterministic_detectors.py      # 5 competition fraud typologies & decoy clearance
├── test_estate_connector.py             # Multi-tenant SQLite engine & Polars DataFrame extraction
├── test_estate_seeder.py                # Deterministic estate generation & validate_format.py
├── test_estate_api.py                   # Estate audit endpoint (/api/v1/investigations/audit-estate)
├── test_estate_upload.py                # Raw SQLite estate upload & immediate audit
├── test_exhibit_reconciler.py           # 2% peso mathematical reconciliation & exhibit auto-fill
├── test_case_file_generator.py          # 5-section legal document & Mermaid flowchart rendering
├── test_n8n_enrichment.py               # External ReAct orchestrator proxy & SSE audit stream
├── test_masking.py                      # PII redaction engine (CLABEs, emails, phone numbers, SSNs)
├── test_database.py                     # SQLAlchemy 2.0 async engine, TigerData SSL & pgvector
├── test_investigations.py               # Investigation lifecycle, CSV ingestion & cascade deletes
├── test_investigations_challenge.py     # Adversarial CSV uploads, UUID fuzzing & stress tests
├── test_tts.py                          # Shielded ElevenLabs audio proxy & bitwise MP3 oracle
└── test_e2e_full_lifecycle.py           # Unified 10-step full system lifecycle integration
```

### Core Responsibilities

1. **Deterministic Algorithm Verification**: Ensures NetworkX graph pruning algorithms (closed cycles $L=2\dots 5$ and rapid pass-through conduit ratios $\ge 90\%$ in $\le 48\text{h}$) reliably eliminate $85\%\text{--}98\%$ of legitimate transaction noise without false negatives.
2. **Adversarial & Empirical Challenge Validation**: Stress-tests all API ingress boundaries against malformed CSVs, SQL injection payloads in AST operators and field names, path traversals, cross-case tenant leakage, and client disconnection storms.
3. **Dual-Engine Architectural Parity**: Validates strict behavioral equivalence between the production PostgreSQL/TigerData engine (with `pgvector` HNSW indexes) and the offline, in-memory Python fallback cache (`INVESTIGATION_CASES` and `IN_MEMORY_BANKING_DATA`).
4. **Evidentiary Reconciliation & Mexican Compliance**: Guarantees that fraud findings automatically resolve against underlying estate ledgers, bank transactions, and invoices within the strict $2.0\%$ peso variance margin required by legal and regulatory frameworks (CFF Art. 69-B, LFPIORPI).
5. **Zero-Leak Lifecycle & Connection Management**: Simulates mid-stream client disconnects, socket churn, and upstream service partitions using `psutil` and `asyncio.CancelledError` traps to prove zero connection pool exhaustion and zero dangling file descriptors.

---

## 2. Test Architecture & Execution Categorization

The test architecture is structured into a hierarchical verification pipeline ranging from pure unit tests to full 10-step integration lifecycles:

```mermaid
flowchart TD
    subgraph L1 ["Level 1: Pure Unit & Deterministic Tests"]
        U1["Data Masking & PII Redaction<br/>(test_masking.py)"]
        U2["Database Normalization & Embeddings<br/>(test_database.py)"]
        U3["Bitwise Silent MP3 Audio Frame<br/>(test_tts.py, test_challenge_m4_tts.py)"]
        U4["2% Mathematical Reconciliation<br/>(test_exhibit_reconciler.py)"]
        U5["Mermaid Money Trail Flowcharts<br/>(test_case_file_generator.py)"]
    end

    subgraph L2 ["Level 2: Challenge Milestone Suites (Adversarial)"]
        C1["Milestone 2: SSE Stream Lifecycle & Pool Leaks<br/>(test_challenge_m2_streaming.py)"]
        C2["Milestone 3: Dynamic SQLi & Case Isolation<br/>(test_challenge_m3_tools.py, test_challenger_m3_2.py)"]
        C3["Milestone 4: TTS Fault Injection & Socket Audit<br/>(test_challenge_m4_tts.py, test_challenge_m4_2.py)"]
        C4["Investigations Adversarial Fuzzing<br/>(test_investigations_challenge.py)"]
    end

    subgraph L3 ["Level 3: Integration & Subsystem Tests"]
        I1["Polars Ingestion & Pruning Pipeline<br/>(test_pipeline.py)"]
        I2["Investigation REST & SSE Routes<br/>(test_investigations.py)"]
        I3["Agent Tools Registry & Banking Tables<br/>(test_agent_tools.py, test_forensic_tools_suite.py)"]
        I4["Forensic Detector Typology Engine<br/>(test_deterministic_detectors.py)"]
        I5["Estate Connector & Seeder Benchmarks<br/>(test_estate_connector.py, test_estate_seeder.py)"]
        I6["Estate Ingestion & Audit Endpoints<br/>(test_estate_api.py, test_estate_upload.py, test_database_tools.py)"]
        I7["n8n LLM Enrichment & Webhook Proxy<br/>(test_n8n_enrichment.py)"]
    end

    subgraph L4 ["Level 4: Full End-to-End System Integration"]
        E2E["10-Step E2E Full Lifecycle<br/>Upload → Ingest → DB Persist → List → Detail → Tools Query → AST Query → SSE Stream → Verdict Persist → TTS Synthesize<br/>(test_e2e_full_lifecycle.py)"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
```

### Mocking & Isolation Strategies

| Boundary / Dependency | Isolation / Mocking Strategy | Applied In |
| :--- | :--- | :--- |
| **HTTP Transport** | `httpx.ASGITransport(app=app)` paired with `httpx.AsyncClient`. Executes API requests directly in-process via ASGI without spawning network sockets or requiring an active Uvicorn daemon. | `test_investigations.py`, `test_agent_tools.py`, `test_tts.py`, `test_estate_api.py`, `test_e2e_full_lifecycle.py` |
| **Relational Database** | `sqlite+aiosqlite:///:memory:` dynamically configured via context managers (`isolated_test_db()`, `setup_test_db()`). All SQLAlchemy models, tables, and constraints are provisioned and destroyed per test. | `test_database.py`, `test_investigations.py`, `test_agent_tools.py`, `test_forensic_tools_suite.py` |
| **Forensic Data Estate** | Isolated temporary directory SQLite databases (`tempfile.TemporaryDirectory()`) provisioned with all 9 estate tables (`vendors`, `invoices`, `ledger`, `bank_txns`, `purchase_orders`, `contracts`, `employees`, `efos_list`, `exhibits`). | `test_estate_connector.py`, `test_deterministic_detectors.py`, `test_exhibit_reconciler.py`, `test_database_tools.py` |
| **n8n Webhook Service** | `unittest.mock.patch` capturing outbound `httpx.AsyncClient.post` calls to `N8N_WEBHOOK_URL`, returning mocked JSON verdicts or simulating offline connection drops to trigger deterministic heuristic fallbacks. | `test_n8n_enrichment.py` |
| **ElevenLabs Speech API** | Custom `MockAsyncHttpClient` and `MockStreamResponse` generating controlled audio byte streams, or simulating HTTP 401, 429, 500, timeouts, and network drops to verify seamless fallback to synthetic silent audio frames. | `test_tts.py`, `test_challenge_m4_tts.py`, `test_challenge_m4_2.py` |
| **Resource & Socket Audits** | Real OS process introspection via `psutil.Process().net_connections()` and file descriptor inspection across rapid concurrent client connection and disconnect loops. | `test_challenge_m4_2.py` |

---

## 3. Comprehensive Test Catalog Table

The table below catalogs all **24 test suite files** in `backend/tests/`, summarizing tested subsystems, automated test counts, and primary verification assertions:

| Test File | Subsystem Under Test | Tests | Primary Assertions & Verification Target |
| :--- | :--- | :---: | :--- |
| [`test_pipeline.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_pipeline.py) | Core Pipeline & Ingestion | 4 | Ingestion of `sample_amlsim.csv`, graph building, cycle/mule pruning, noise reduction metrics, SSE event streaming, TTS proxy, missing timestamp column synthesis, and null cell defaults. |
| [`test_challenge_m2_streaming.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m2_streaming.py) | Milestone 2 Streaming Engine | 6 | Strict 6-phase thought ordering, verdict schema compliance, database status transition (`PROCESSING` $\to$ `COMPLETED`), pool safety across 10 consecutive streams, `GeneratorExit` cleanup, benign empty-graph handling. |
| [`test_challenge_m3_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m3_tools.py) | Milestone 3 Agent Tools | 14 | SQL injection immunity in fields/sort/filters, mandatory `case_id` scoping enforcement, cross-case tenant isolation, 9-operator AST validation matrix, vector dimension checking, tool registry reflection. |
| [`test_challenger_m3_2.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenger_m3_2.py) | Milestone 3 Dual Parity | 8 | Strict functional parity between Database mode and In-Memory fallback mode across compound transaction filters, entity profiling, cycle pattern extraction, and legal vector search. |
| [`test_challenge_m4_tts.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m4_tts.py) | Milestone 4 TTS Security | 18 | Boundary string lengths ($0, 1, 5000, 5001, 100000$ chars), multilingual/emoji payloads, SSRF/traversal in `voice_id`, CRLF/null byte rejection, upstream error matrix (400, 403, 404, 502, 503, 504), Cloudflare HTML intercept handling, bitwise MPEG-1 Layer 3 validation. |
| [`test_challenge_m4_2.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m4_2.py) | Milestone 4 TTS Resilience | 9 | Mid-stream client disconnects, `aclose()` generator exit stress, 30 concurrent disconnect storms, `psutil` socket leak audit, header audits (`X-Audio-Source`), zero-leak canary key shielding in all artifacts. |
| [`test_agent_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_agent_tools.py) | Dedicated Agent Tool APIs | 16 | Dedicated `/tools/transactions`, `/tools/entities`, `/tools/patterns`, `/tools/legal-precedents`, AST dynamic queries with sorting/pagination/security, runtime custom tool registration, inverted timestamp rejection, empty `in` handling. |
| [`test_database_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_database_tools.py) | Estate Database Inspection | 1 | Database table cataloging (`/database/tables`), dedicated entity readers (`/database/vendors`, `/database/contracts`), filtered queries, single record lookups by ID, and exhibit insertion with evidence citations. |
| [`test_forensic_tools_suite.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_forensic_tools_suite.py) | 11 Core Forensic Tools | 12 | Comprehensive suite testing `search_transactions`, `find_related_entities`, `compare_entities`, `analyze_payment_patterns`, `search_financial_history`, `get_cashout`, `trace_money_flow`, `find_related_transactions`, `find_transaction_chains`, `find_shared_entities`, `detect_circular_flow`, and dynamic queries on banking tables (`accounts`, `parties`, `cash_transactions`, `account_mappings`). |
| [`test_deterministic_detectors.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_deterministic_detectors.py) | Fraud Typology Suite | 1 | Planted estate detection covering all 5 typologies (Phantom Vendor, Kickback, Round-Tripping, Threshold Splitting, Revenue Inflation), decoy clearance into `leads_not_pursued`, and 100% `validate_format.py` compliance. |
| [`test_estate_connector.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_connector.py) | Multi-Tenant SQLite Engine | 2 | Dynamic SQLite estate initialization (both `:memory:` and temp files), full CRUD across all 9 tables, zero-copy Polars DataFrame extraction, exhibit resolution, and per-table 2% reconciliation. |
| [`test_estate_seeder.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_seeder.py) | Benchmark Estate Seeder | 4 | 8-table schema integrity and primary keys, record count population, random seed determinism, and full structural passing of `validate_format.py`. |
| [`test_estate_api.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_api.py) | Estate Audit Endpoint | 1 | End-to-end invocation of `/api/v1/investigations/audit-estate`, executing deterministic detection over an uploaded estate, returning validated case file JSON. |
| [`test_estate_upload.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_upload.py) | Estate Upload Endpoint | 1 | Multipart binary upload of `.db` file to `/api/v1/estates/upload`, standalone persistence, and optional on-demand execution of the deterministic audit pipeline. |
| [`test_exhibit_reconciler.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_exhibit_reconciler.py) | Exhibit Reconciler | 5 | Exact match (0.00%), 1.5% variance acceptance (within 2% limit), 2.5% variance rejection, multi-table settlements without double counting (invoices + bank transactions), auto-completion to $\ge 3$ exhibits, and database persistence. |
| [`test_case_file_generator.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_case_file_generator.py) | Legal Document Generator | 2 | Mermaid flowchart syntax generation with MXN currency labels, full generation of 5 required sections in exact sequence, `leads_not_pursued` inclusion, dual export (`case_file.md` and `submission.json`), and validator compliance. |
| [`test_n8n_enrichment.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_n8n_enrichment.py) | n8n ReAct Orchestration | 3 | Sequential one-by-one LLM finding enrichment with mocked n8n responses, offline deterministic heuristic fallback, and real-time SSE stream emission (`/api/v1/investigations/audit-estate/stream`). |
| [`test_masking.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_masking.py) | PII Masking Engine | 2 | Masking units for 18-digit CLABEs (`0121**********8901`), email prefixes, phone numbers, addresses, free-text scanning, and automatic redaction across database API endpoints. |
| [`test_database.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_database.py) | SQLAlchemy Engine & Persistence | 7 | Database URL asyncpg normalization, credential sanitization in logs, connection pool configuration, 1536-dim unit vector generation, SQLite CRUD with cascading deletes, idempotent legal knowledge seeding, engine lifespan. |
| [`test_investigations.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_investigations.py) | Investigation Lifecycle API | 11 | CSV upload and DB row creation, in-memory fallback upload, file validation contracts, paginated case listing, detail retrieval with subgraph/metrics, SSE reasoning stream, 404 for non-existent IDs, cascade delete, and missing/null timestamp handling. |
| [`test_investigations_challenge.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_investigations_challenge.py) | Ingress Adversarial Fuzzing | 11 | Non-CSV extension rejection, case-insensitive extension parsing (`.CSV`), corrupt/empty payload handling, numeric timestamp fuzzing (negative, extreme), ISO timestamp string conversion, pagination boundary fuzzing, malformed UUID rejection, empty database listing, 600-row dataset stress, concurrent uploads. |
| [`test_tts.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_tts.py) | ElevenLabs Proxy & Security | 17 | Fallback when API key is None/empty/placeholder, minimal silent MP3 frame structure (320 bytes), live streaming mode, upstream failure matrix (500, 401, 429, timeout, connect drop), validation errors (empty/missing/oversized text), and key leak shielding. |
| [`test_e2e_full_lifecycle.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_e2e_full_lifecycle.py) | End-to-End System Integration | 5 | Unified 10-step full system lifecycle (Health $\to$ Ingest $\to$ DB $\to$ List $\to$ Detail $\to$ Tools $\to$ AST $\to$ SSE $\to$ Verdict DB $\to$ TTS), dynamic query whitelisting rejection, cascade deletion verification, non-existent UUID handling, complete offline in-memory lifecycle. |
| [`__init__.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/__init__.py) | Package Initializer | — | Python package initialization facilitating absolute package imports (`backend.tests.*`) and pytest suite discovery. |

---

## 4. Detailed Test Suite Specifications

### 4.1 Core Forensic Pipeline & Ingestion
- **Source File**: [`backend/tests/test_pipeline.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_pipeline.py)
- **Primary Subsystems**: [`backend/services/ingestion.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/ingestion.py), [`backend/services/deterministic_filter.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/deterministic_filter.py), [`backend/api/routes/investigations.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/investigations.py), [`backend/api/routes/tts.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/tts.py).
- **Execution Mode**: Hybrid (sync DataFrame unit tests + async ASGI pipeline tests).
- **Key Scenarios Tested**:
  1. `test_complete_forensic_pipeline`: Ingests `data/sample_amlsim.csv` via `POST /api/v1/investigations/upload`. Asserts 201 response with valid `case_id`, verifies NetworkX graph builds with pruned metrics, requests `GET /api/v1/investigations/{case_id}/stream`, reads chunks over SSE, verifying that sequential `thought` events precede the final `verdict` event.
  2. `test_tts_synthesize_proxy`: Posts verdict narration to `/api/v1/tts/synthesize`, asserting HTTP 200, `audio/mpeg` content type, and synthetic fallback headers when `ELEVENLABS_API_KEY` is in default state.
  3. `test_read_amlsim_csv_synthetic_fallback`: Parses CSV missing the timestamp column; verifies Polars synthesis of sequential numeric `step` intervals.
  4. `test_read_amlsim_csv_null_timestamp_cells`: Parses CSV with null/empty cells in timestamp column; asserts automatic fallback imputation to `0.0`.

### 4.2 Adversarial Challenge Suites (Milestones 2, 3, 4)

#### Milestone 2: Streaming Engine Hardening
- **Source File**: [`backend/tests/test_challenge_m2_streaming.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m2_streaming.py)
- **Primary Subsystems**: [`backend/api/routes/investigations.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/investigations.py), [`backend/core/database.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/core/database.py).
- **Key Assertions**:
  - Validates that the 6 reasoning phases emit strictly sequentially:
    1. Phase 1: `Ingestion and Column Normalization`
    2. Phase 2: `Topological Graph Construction`
    3. Phase 3: `Circular Layering Detection`
    4. Phase 4: `Rapid Velocity Conduit Analysis`
    5. Phase 5: `Legal Jurisprudence & Regulatory Matching`
    6. Phase 6: `Forensic Verdict Synthesis`
  - Asserts case database status transitions from `PROCESSING` $\to$ `COMPLETED` upon conclusion of the stream, persisting the full `verdict` JSON.
  - Stresses 10 consecutive streams on a single case ID to verify database connection pool safety (`DB_POOL_SIZE` is not leaked).
  - Asserts clean handling of `GeneratorExit` when a client closes the stream prematurely.

#### Milestone 3: Dynamic Query Security & Dual-Engine Parity
- **Source Files**: [`backend/tests/test_challenge_m3_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m3_tools.py), [`backend/tests/test_challenger_m3_2.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenger_m3_2.py)
- **Primary Subsystems**: [`backend/api/routes/agent_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/agent_tools.py), [`backend/services/tool_registry.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/tool_registry.py).
- **Key Assertions**:
  - **SQL Injection Defense**: Injects payloads into dynamic query fields (`amount; DROP TABLE transactions;--`), `sort_by` parameters, and operators. Verifies that schema validation rejects illegal characters and that filter values are strictly bound as parameterized literals.
  - **Multi-Tenant Isolation**: Uploads Case A and Case B; asserts that queries scoped to Case A cannot read or filter records from Case B, preventing cross-tenant leakage.
  - **Operator Matrix**: Stresses all 9 supported AST operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`).
  - **Dual Parity**: Executes identical queries against TigerData PostgreSQL/SQLite and the in-memory fallback dictionary (`INVESTIGATION_CASES`), asserting identical record sets, sums, and ordering.

#### Milestone 4: Speech Synthesis Proxy Hardening
- **Source Files**: [`backend/tests/test_challenge_m4_tts.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m4_tts.py), [`backend/tests/test_challenge_m4_2.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_challenge_m4_2.py)
- **Primary Subsystems**: [`backend/api/routes/tts.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/tts.py).
- **Key Assertions**:
  - Boundary checking: Empty string (0 chars) $\to$ 422; 1 char $\to$ 200; 5000 chars $\to$ 200; 5001 chars $\to$ 422; 100,000 char DOS payload $\to$ 422.
  - Path traversal and SSRF protection in `voice_id` (e.g., `../../etc/passwd`, `http://169.254.169.254`).
  - Fault tolerance matrix: Simulates upstream 400, 403, 404, 500, 502, 503, 504 errors, network partitions mid-stream, and connection resets; asserts automatic degradation to synthetic silent MP3 with HTTP 200.
  - Bitwise oracle verification: Validates binary structure of synthetic silent MP3 frame (`0xFFFB9004...`, MPEG-1 Layer 3, 128 kbps, 44.1 kHz, 320 bytes).
  - Secret key shielding: Verifies that even if upstream returns a 401 detailing `Invalid xi-api-key: <KEY>`, the API key is stripped and never echoed in response bodies, headers, or exception dumps.
  - High concurrency stress: 30 simultaneous client disconnect storms; verifies via `psutil` that zero network sockets or file descriptors leak.

### 4.3 Forensic Agent Investigation Tools
- **Source Files**: [`backend/tests/test_agent_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_agent_tools.py), [`backend/tests/test_forensic_tools_suite.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_forensic_tools_suite.py), [`backend/tests/test_database_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_database_tools.py)
- **Primary Subsystems**: [`backend/api/routes/agent_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/agent_tools.py), [`backend/api/routes/database_tools.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/database_tools.py), [`backend/models/forensic.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/models/forensic.py).
- **Key Tools Tested**:
  1. `search_transactions`: Amount range filters, origin/destination filtering, suspicion flags.
  2. `find_related_entities`: Graph neighbor discovery, incoming/outgoing edge classification.
  3. `compare_entities`: Comparative structural metrics (flow ratios, degree centrality, suspicious volumes).
  4. `analyze_payment_patterns`: Transaction burst frequencies, time delta variances, round amount detection.
  5. `search_financial_history`: Historic transactional volume and ledger balance deltas.
  6. `get_cashout`: Rapid conversion to cash or conduit exits (SPEI, ATM, teller withdrawals).
  7. `trace_money_flow`: Directed multi-hop path extraction from source node to sink node.
  8. `find_related_transactions`: Correlation of transactions by shared metadata, timestamps, or entities.
  9. `find_transaction_chains`: Linear pass-through mule chain detection ($A \to B \to C \to D$).
  10. `find_shared_entities`: Identification of common bridge entities between independent suspect accounts.
  11. `detect_circular_flow`: Closed ring cycle detection with cycle length bounds.
  12. Dynamic Query Builder: Composable AST querying across banking tables (`accounts`, `parties`, `cash_transactions`, `account_mappings`).

### 4.4 Deterministic Detectors & Graph Algorithms
- **Source File**: [`backend/tests/test_deterministic_detectors.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_deterministic_detectors.py)
- **Primary Subsystems**: [`backend/services/deterministic_detectors.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/deterministic_detectors.py), [`backend/models/estate.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/models/estate.py).
- **Typologies Verified**:
  - **Phantom Vendor**: Vendor listed in `efos_list` (SAT Art. 69-B definitive list), issuing invoices without backing contracts or material deliverables.
  - **Kickback**: Vendor receiving audited company funds and transferring illicit commissions to an employee's personal CLABE account.
  - **Round-Tripping**: Funds transferred from audited company through a sequence of intermediate shell entities and returned back to the company.
  - **Threshold Splitting**: Structuring invoices just below corporate approval thresholds (e.g. $\$100,000$ MXN limit split into multiple $\$45,000$ and $\$48,000$ invoices).
  - **Revenue Inflation**: Fictitious invoices issued to inflate commercial volume without corresponding real banking transactions.
  - **Decoy Clearance**: Innocent supplier anomalies cleared and cataloged in `leads_not_pursued`.

### 4.5 Forensic Data Estate & Ingestion Ecosystem
- **Source Files**: [`backend/tests/test_estate_connector.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_connector.py), [`backend/tests/test_estate_seeder.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_seeder.py), [`backend/tests/test_estate_api.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_api.py), [`backend/tests/test_estate_upload.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_estate_upload.py)
- **Primary Subsystems**: [`backend/services/estate_connector.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/estate_connector.py), [`scripts/seed_estate.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/scripts/seed_estate.py), [`backend/api/routes/estates.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/api/routes/estates.py).
- **Key Assertions**:
  - Multi-tenant connection management: Dynamically creates and pools SQLite connections to distinct `.db` files or `:memory:` targets.
  - Full CRUD operations and Polars zero-copy DataFrame table extractions across all 9 estate tables (`vendors`, `invoices`, `ledger`, `bank_txns`, `purchase_orders`, `contracts`, `employees`, `efos_list`, `exhibits`).
  - Estate seeder validation: Confirms that identical random seeds produce byte-identical SQLite estate files and matching ground truth JSON artifacts.
  - Multipart upload handling: Validates upload of raw SQLite `.db` binaries, verifying file persistence and optional trigger of the forensic detector suite.

### 4.6 Exhibit Reconciliation & Legal Case File Generation
- **Source Files**: [`backend/tests/test_exhibit_reconciler.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_exhibit_reconciler.py), [`backend/tests/test_case_file_generator.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_case_file_generator.py)
- **Primary Subsystems**: [`backend/services/exhibit_builder.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/exhibit_builder.py), [`backend/services/case_file_generator.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/case_file_generator.py).
- **Key Assertions**:
  - **2% Tolerance Rule**: Implements and validates strict legal mathematical reconciliation:
    $$\text{Variance \%} = \frac{|\text{Claimed Amount} - \text{Table Sum}|}{\text{Claimed Amount}} \le 0.02$$
    - 0.00% variance $\to$ Passed.
    - 1.50% variance $\to$ Passed.
    - 2.50% variance $\to$ Failed.
  - **Anti-Double Counting**: When an invoice ($\$92,800$) and its settling bank transfer ($\$92,800$) are both cited, the reconciler selects the best matching single table rather than summing both ($\$185,600$), preventing double-counting.
  - **Auto-Completion**: Automatically identifies and generates exhibits to meet the minimum constraint of 3 exhibits per scheme finding.
  - **Legal Case File Generation**: Emits `case_file.md` with the 5 mandatory sections in exact order:
    1. Executive Summary Table
    2. Primary Scheme Analysis
    3. Secondary Scheme Analysis
    4. Leads Not Pursued
    5. Per-Table Mathematical Reconciliations
  - Renders valid Mermaid flowchart code (`flowchart LR`) with MXN currency annotations and exhibit citation badges (`[EX-01]`).

### 4.7 n8n ReAct Orchestration & LLM Enrichment
- **Source File**: [`backend/tests/test_n8n_enrichment.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_n8n_enrichment.py)
- **Primary Subsystems**: [`backend/services/n8n_enrichment.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/services/n8n_enrichment.py).
- **Key Assertions**:
  - Sequential one-by-one review: Feeds detected fraud schemes individually into the n8n ReAct webhook, asserting enriched judge verdicts, rule citations, and legal narratives.
  - Offline fallback: When the n8n webhook is offline or unconfigured, gracefully switches to a local deterministic heuristic engine without raising unhandled errors.
  - Live SSE streaming: Verifies `/api/v1/investigations/audit-estate/stream` emitting SSE chunks (`review_thought`, `finding_verdict`, `audit_complete`).

### 4.8 Persistence, PII Protection & Engine Lifespan
- **Source Files**: [`backend/tests/test_masking.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_masking.py), [`backend/tests/test_database.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_database.py)
- **Primary Subsystems**: [`backend/core/masking.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/core/masking.py), [`backend/core/database.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/core/database.py).
- **Key Assertions**:
  - Masking engine redacts sensitive PII:
    - CLABE: `012180012345678901` $\to$ `0121**********8901`
    - Email: `informes@proveedorfantasma.com.mx` $\to$ `i***s@proveedorfantasma.com.mx`
    - Phone: `+52 55 1234 5678` $\to$ `******5678`
    - Address: Street names redacted with `[DIRECCIÓN PROTEGIDA]`
  - URL Normalization: Converts `postgres://` and `postgresql://` strings to `postgresql+asyncpg://`, strips SSL queries to configure `connect_args={"ssl": "require"}`.
  - Embedding Generator: Verifies 1536-dimensional vector generation with unit L2 norm ($|v| \approx 1.0$).
  - Relational Integrity: Deleting an `investigation_cases` row cascades and automatically deletes child `transactions` records.

### 4.9 End-to-End System Integration (10-Step Lifecycle)
- **Source File**: [`backend/tests/test_e2e_full_lifecycle.py`](file:///c:/Users/maxan/OneDrive/Documentos/Repositories/HackMTY%202026/Infosys/Polar/backend/tests/test_e2e_full_lifecycle.py)
- **Primary Subsystems**: Entire backend application stack.
- **Unified 10-Step Verification Workflow**:
  ```
  Step 1: GET /health                                  (Health check -> 200 OK)
     │
  Step 2: POST /api/v1/investigations/upload           (CSV Ingestion -> 201 Created)
     │
  Step 3: Direct DB Row Assertion                     (Verify InvestigationCase + TransactionRecord rows)
     │
  Step 4: GET /api/v1/investigations                  (Paginated listing -> verify status PROCESSING)
     │
  Step 5: GET /api/v1/investigations/{id}             (Detail retrieval -> verify subgraph & flow metrics)
     │
  Step 6: Dedicated Tool Queries                      (/tools/transactions, /entities, /patterns, /precedents)
     │
  Step 7: Composable Dynamic AST Query                (/tools/query with parameter whitelisting)
     │
  Step 8: GET /api/v1/investigations/{id}/stream      (SSE stream -> receive thoughts + terminal verdict)
     │
  Step 9: Post-Stream DB State Assertion              (Verify case status COMPLETED & verdict persisted)
     │
  Step 10: POST /api/v1/tts/synthesize                (Audio stream -> MP3 proxy or synthetic fallback)
  ```
- **Additional Scenarios**: Cascading deletion verification, security whitelisting rejection, nonexistent UUID handling (404), and execution in pure offline in-memory mode.

---

## 5. Test Execution Guide & Operational Best Practices

### 5.1 Running Tests from Repository Root

All backend tests **must be executed from the repository root**. Absolute package imports (`from backend.core.config import settings`) depend on the repository root existing in `sys.path`.

```bash
# Execute the default verified e2e pipeline test
python -m pytest backend/tests/test_pipeline.py -v

# Run an entire specific test suite
python -m pytest backend/tests/test_database.py -v
python -m pytest backend/tests/test_agent_tools.py -v
python -m pytest backend/tests/test_e2e_full_lifecycle.py -v

# Run tests by keyword filter
python -m pytest backend/tests -k "streaming or verdict" -v

# Run the comprehensive forensic tool suite
python -m pytest backend/tests/test_forensic_tools_suite.py -v

# Run exhibit reconciler tests
python -m pytest backend/tests/test_exhibit_reconciler.py -v
```

### 5.2 Environment Variables & Configuration

Tests execute out-of-the-box using the built-in SQLite in-memory engine and synthetic audio generator without requiring live external services. To test live integrations against managed services, configure the following environment variables:

```bash
# Optional: Target live TigerData PostgreSQL instance
export DATABASE_URL="postgresql+asyncpg://forensic_user:secret@db.tigerdata.com:5432/audit_db"

# Optional: Enable live ElevenLabs audio synthesis proxy
export ELEVENLABS_API_KEY="sk_live_elevenlabs_key"

# Optional: Enable live external n8n ReAct agent webhook
export N8N_WEBHOOK_URL="https://n8n.internal.net/webhook/forensic-audit"
```

### 5.3 Windows Platform Gotchas & Operational Guidelines

1. **UTF-8 Output Encoding (`-X utf8`)**: When running scripts that parse Spanish legal text or validate case files on Windows, Python defaults to the legacy Windows ANSI code page (cp1252), causing `UnicodeDecodeError`. Always specify `-X utf8`:
   ```bash
   python -X utf8 student-materials/forensic-auditor/validate_format.py --submission case_file.json
   ```
2. **SQLite File Locks in Temporary Directories**: On Windows, SQLite locks `.db` files while connections remain open. In tests utilizing `tempfile.TemporaryDirectory()`, call `await connector.dispose_all()` before exiting the async scope to release file handles; otherwise, `TemporaryDirectory.cleanup()` will raise `PermissionError: [WinError 32]`.
3. **Module Resolution for `validate_format.py`**: The `test_estate_seeder.py` test suite imports `validate_format` directly. When running this suite, ensure `student-materials/forensic-auditor` is included in `PYTHONPATH`:
   ```bash
   # Windows PowerShell
   $env:PYTHONPATH=".;student-materials/forensic-auditor;tmp"
   python -m pytest backend/tests/test_estate_seeder.py -v
   ```
4. **Pytest Asyncio Loop Scope**: Tests utilize `@pytest.mark.asyncio`. Under modern `pytest-asyncio` ($\ge 0.23$), asynchronous fixtures and tests operate under function-scoped loops by default, ensuring pristine database and memory state isolation across tests.

---

## 6. Verification Checklist Before Pull Requests

Before committing changes to the backend codebase or modifying API router signatures:

- [ ] **Core Pipeline Verification**: `python -m pytest backend/tests/test_pipeline.py -v` passes.
- [ ] **E2E Full Lifecycle**: `python -m pytest backend/tests/test_e2e_full_lifecycle.py -v` passes.
- [ ] **Database & Migrations**: `python -m pytest backend/tests/test_database.py -v` passes.
- [ ] **Agent Tools & Security**: `python -m pytest backend/tests/test_agent_tools.py -v` passes.
- [ ] **Reconciler Precision**: `python -m pytest backend/tests/test_exhibit_reconciler.py -v` passes.
- [ ] **Documentation Sync**: If an endpoint, schema, or algorithm threshold is altered, update `doc/backend/README.md`, `doc/architecture/README.md`, and this test catalog.
