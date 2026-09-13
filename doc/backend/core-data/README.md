# Backend Core Data, Models, and Schema Architecture

[← Back to Backend Documentation](../README.md) | [Master Architecture](../../README.md) | [Agent Routing Index](../../index.md)

---

## 1. Overview & Core Responsibilities

The `backend/core-data` subsystem forms the foundation for data persistence, schema validation, configuration governance, and data privacy across the Polar Forensic Auditor AML Engine.

It unifies:
1. **Centralized Configuration Management (`backend/core/config.py`)**: Environment variable ingestion, algorithm threshold defaults, CORS policies, and integration configuration via Pydantic v2 `BaseSettings`.
2. **Database Engine & Connection Pool Architecture (`backend/core/database.py`)**: Asynchronous engine management (`AsyncEngine`), connection pooling, SSL normalization for managed TigerData PostgreSQL instances, cross-dialect SQLite fallback execution, and lifecycle schema initialization.
3. **Personally Identifiable Information (PII) Redaction Engine (`backend/core/masking.py`)**: Compliance-grade masking of sensitive banking identifiers (18-digit CLABEs, tax IDs/SSN, emails, physical addresses, phone numbers) before data egress to external LLMs, agent networks (n8n), or client views.
4. **SQLAlchemy 2.0 Declarative ORM Models (`backend/models/`)**:
   - `models/forensic.py`: Case lifecycle management (`investigation_cases`), raw/pruned transaction storage (`transactions`), 1536-dimensional HNSW cosine vector index for Mexican jurisprudence (`legal_knowledge_vectors`), and core banking entities (`accounts`, `account_mappings`, `parties`, `cash_transactions`).
   - `models/estate.py`: The corporate Data Estate schema modeling CFDI 4.0 invoices, general ledger entries, purchase orders, commercial contracts, SAT Article 69-B blacklists (`efos_list`), and audit exhibits.
5. **Pydantic v2 Validation Schemas & Tool Contracts (`backend/schemas/`)**:
   - `schemas/investigation.py`: Request and response models for dataset ingestion, topological metrics, isolated subgraphs, streaming thought events, and final forensic verdicts.
   - `schemas/agent_tools.py`: Strongly-typed contracts for n8n ReAct agent tools, including a secure composable Abstract Syntax Tree (AST) dynamic query engine equipped with strict field whitelisting and mandatory tenant/case scoping.

---

## 2. Architecture & Entity Relationships

### 2.1 Entity-Relationship Diagram

The following diagram illustrates the relational models across Forensic Investigations, Core Banking, Vector Knowledge, and the Corporate Data Estate:

```mermaid
erDiagram
    %% Forensic Investigation Domain
    INVESTIGATION_CASES ||--o{ TRANSACTIONS : "contains (cascade delete)"
    INVESTIGATION_CASES {
        uuid id PK
        string filename
        string status
        datetime created_at
        datetime updated_at
        jsonb ingestion_metadata
        jsonb metrics
        jsonb subgraph
        jsonb patterns
        jsonb verdict
    }
    TRANSACTIONS {
        uuid id PK
        uuid case_id FK
        string origin
        string destination
        numeric amount
        timestamptz timestamp
        boolean is_suspicious
        jsonb reasons
    }
    LEGAL_KNOWLEDGE_VECTORS {
        uuid id PK
        string article_code UK
        string law_name
        text content
        vector_1536 embedding
    }

    %% Core Banking Domain
    ACCOUNTS ||--o{ ACCOUNT_MAPPINGS : "mapped via acct_id"
    PARTIES ||--o{ ACCOUNT_MAPPINGS : "mapped via cust_id"
    ACCOUNTS ||--o{ CASH_TRANSACTIONS : "executes ATM ops"
    ACCOUNTS {
        string acct_id PK
        string dsply_nm
        string type
        string acct_stat
        string acct_rptng_crncy
        integer prior_sar_count
        string branch_id
        numeric initial_deposit
        string ssn
    }
    ACCOUNT_MAPPINGS {
        string cust_acct_mapping_id PK
        string acct_id FK
        string cust_id FK
        string cust_acct_role
    }
    PARTIES {
        string party_id PK
        string party_type
        boolean is_individual
        string legal_name
        string nationality
        string primary_phone
        string company_email
    }
    CASH_TRANSACTIONS {
        string tran_id PK
        string account_id FK
        string tx_type
        numeric amount
        string timestamp
        boolean is_sar
    }

    %% Corporate Data Estate Domain
    VENDORS ||--o{ INVOICES : "emits (issuer_rfc)"
    VENDORS ||--o{ PURCHASE_ORDERS : "receives (vendor_rfc)"
    VENDORS ||--o{ CONTRACTS : "signs (vendor_rfc)"
    INVOICES ||--o{ LEDGER : "reconciled via invoice_uuid"
    EFOS_LIST ||--o| VENDORS : "SAT 69-B match on rfc"
    VENDORS {
        string rfc PK
        string legal_name
        string bank_clabe
        string contact_email
    }
    INVOICES {
        string uuid PK
        string issuer_rfc FK
        string receiver_rfc
        string issue_date
        numeric total
        string uso_cfdi
        string status
    }
    LEDGER {
        integer entry_id PK
        string date
        string account_code
        numeric debit
        numeric credit
        string invoice_uuid FK
    }
    BANK_TXNS {
        string txn_id PK
        string from_clabe
        string to_clabe
        numeric amount
        string date
    }
    PURCHASE_ORDERS {
        string po_id PK
        string vendor_rfc FK
        numeric amount
        string requester
        string approver
    }
    CONTRACTS {
        string contract_id PK
        string vendor_rfc FK
        numeric value
        text scope_text
    }
    EMPLOYEES {
        string emp_id PK
        string name
        string role
        string bank_clabe
    }
    EFOS_LIST {
        string rfc PK
        string legal_name
        string status
        string publication_date
    }
    EXHIBITS {
        string exhibit_id PK
        string source_table
        string record_id
        text sentence
    }
```

### 2.2 Core Data Flow & Privacy Architecture

The core data tier ensures configuration cascades to the engine pool, models are persisted safely, and sensitive fields are masked before reaching external agents or clients:

```mermaid
flowchart TD
    subgraph Configuration ["Core Configuration (core/config.py)"]
        ENV[".env / backend/.env"] --> Settings["Settings (Pydantic BaseSettings)"]
        Settings --> DB_CFG["Database Pool & SSL Flags"]
        Settings --> THRESHOLDS["Graph Pruning Thresholds"]
        Settings --> SECRETS["API Keys & CORS Config"]
    end

    subgraph DatabaseEngine ["Engine & Sessionmaker (core/database.py)"]
        DB_CFG --> Norm["normalize_database_url()"]
        Norm --> Engine["AsyncEngine (asyncpg / psycopg / SQLite)"]
        Engine --> Pool["Connection Pool (pool_size=20, max_overflow=10)"]
        Pool --> SessionFactory["async_sessionmaker[AsyncSession]"]
        SessionFactory --> Dependency["get_db() FastAPI Dependency"]
    end

    subgraph DataAccess ["ORM Models & In-Memory Fallback (models/)"]
        Dependency --> ForensicORM["models/forensic.py<br/>InvestigationCase, TransactionRecord, LegalArticleVector"]
        Dependency --> BankingORM["models/forensic.py<br/>AccountRecord, PartyRecord, CashTransactionRecord"]
        Dependency --> EstateORM["models/estate.py<br/>VendorRecord, InvoiceRecord, LedgerRecord, EfosRecord"]
        BankingORM -.-> Cache["IN_MEMORY_BANKING_DATA Cache<br/>(Sub-millisecond fallback)"]
    end

    subgraph SecurityMasking ["Data Masking Engine (core/masking.py)"]
        ForensicORM --> Masker["mask_sensitive_payload()"]
        BankingORM --> Masker
        EstateORM --> Masker
        Masker --> CLABE["CLABE Redaction (18 digits -> 4...4)"]
        Masker --> Email["Email Redaction (u***r@domain)"]
        Masker --> PII["Address & Phone Redaction"]
    end

    subgraph ValidationSchemas ["Validation Schemas (schemas/)"]
        Masker --> InvSchemas["schemas/investigation.py<br/>InvestigationUploadResponse, VerdictPayload, ThoughtEvent"]
        Masker --> ToolSchemas["schemas/agent_tools.py<br/>DynamicQueryRequest, RelatedEntitiesResponse, LegalPrecedentItem"]
        InvSchemas --> ClientAPI["Frontend Next.js Client / SSE"]
        ToolSchemas --> AgentAPI["External n8n ReAct Agent Tools"]
    end
```

---

## 3. In-Depth Component Specifications

### 3.1 Centralized Configuration (`backend/core/config.py`)

The configuration subsystem provides typed, validated, and immutable application settings via Pydantic v2 `BaseSettings`.

#### Class: `Settings`
Inherits `pydantic_settings.BaseSettings` with `case_sensitive=True` and `extra="ignore"`.

```python
class Settings(BaseSettings):
    PROJECT_NAME: str = "Forensic Auditor AML Engine"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ...
```

#### Key Configuration Attributes

| Attribute | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `BACKEND_CORS_ORIGINS` | `Union[List[str], str]` | `["http://localhost:3000", "http://127.0.0.1:3000", ...]` | Validated list of permitted origins. The validator accepts raw JSON arrays or comma-delimited strings. |
| `N8N_WEBHOOK_URL` | `str` | `""` | Target webhook URL for the n8n forensic agent orchestrator. |
| `ELEVENLABS_API_KEY` | `str` | `""` | API key for ElevenLabs voice synthesis. |
| `ELEVENLABS_VOICE_ID` | `str` | `"21m00Tcm4TlvDq8ikWAM"` | Default narrator voice ID (Rachel). |
| `ELEVENLABS_MODEL_ID` | `str` | `"eleven_multilingual_v2"` | Multilingual generative voice model ID. |
| `ELEVENLABS_SAFE_MODE` | `bool` | `True` | Safety switch: when `True`, bypasses external API calls to preserve quota, triggering the synthetic MP3 fallback. |
| `TTS_TIMEOUT` | `float` | `30.0` | Read timeout in seconds for streaming audio synthesis. |
| `TTS_CONNECT_TIMEOUT` | `float` | `5.0` | Connection timeout in seconds for audio requests. |
| `MAX_CYCLE_LENGTH` | `int` | `5` | Maximum path hop length $k$ for directed cycle extraction in NetworkX. |
| `PASS_THROUGH_RATIO_THRESHOLD`| `float` | `0.90` | Minimum turnover ratio $\frac{\min(\text{in}, \text{out})}{\max(\text{in}, \text{out})}$ to flag a pass-through mule account. |
| `PASS_THROUGH_WINDOW_HOURS` | `float` | `48.0` | Maximum temporal duration (in hours or steps) between first inflow and last outflow for conduit accounts. |
| `DATABASE_URL` | `Optional[str]` | `None` | PostgreSQL or SQLite connection string. Stripped and converted to `None` if empty string. |
| `DB_POOL_SIZE` | `int` | `20` | Persistent connection pool size for SQLAlchemy PostgreSQL engine. |
| `DB_MAX_OVERFLOW` | `int` | `10` | Maximum additional temporary connections permitted above `DB_POOL_SIZE`. |
| `DB_POOL_PRE_PING` | `bool` | `True` | Issues a `SELECT 1` ping prior to checking out connections to eliminate stale connections. |
| `DB_POOL_RECYCLE` | `int` | `3600` | Recycles connections after 1 hour (3600 seconds) to prevent server-side drops. |
| `DB_SSL_REQUIRE` | `bool` | `True` | Enforces SSL mode `require` on PostgreSQL connections (mandatory for TigerData). |
| `DB_ECHO` | `bool` | `False` | Enables raw SQL logging for debugging when `True`. |

---

### 3.2 Database Engine, Connection Pooling & Lifecycle (`backend/core/database.py`)

This module manages the asynchronous connection infrastructure, URL protocol transformations, connection pooling, and lifecycle initialization.

#### 1. URL Normalization & Sanitization
Managed PostgreSQL providers (such as TigerData, Supabase, Neon) supply URLs formatted as `postgres://` or `postgresql://`. The `asyncpg` driver requires `postgresql+asyncpg://`, and does not accept `?sslmode=require` as a URL query parameter (which throws a runtime configuration error).

- `sanitize_database_url(url: str) -> str`: Masks passwords in connection URLs (`postgres://user:****@host:5432/db`) for safe diagnostic logging.
- `normalize_database_url(raw_url: str) -> Tuple[str, Dict[str, Any]]`:
  - Translates `postgres://` or `postgresql://` schemes into `postgresql+asyncpg://`.
  - Translates `postgresql+psycopg2://` into `postgresql+psycopg://`.
  - Parses query string parameters: extracts `sslmode` or `ssl` and populates `connect_args={"ssl": mode}` for `asyncpg`.
  - Re-encodes the remaining URL query parameters cleanly.

#### 2. Engine & Sessionmaker Creation
`create_engine_and_sessionmaker(database_url: str, echo: Optional[bool] = None)` configures dialect-specific pooling:
- **SQLite Configuration**: Configures `poolclass=StaticPool`, disables thread-checking (`check_same_thread=False`), and attaches a listener to the sync engine:
  ```python
  @event.listens_for(engine.sync_engine, "connect")
  def _set_sqlite_pragma(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA foreign_keys=ON;")
      cursor.close()
  ```
- **PostgreSQL Configuration**: Applies `pool_size=settings.DB_POOL_SIZE`, `max_overflow=settings.DB_MAX_OVERFLOW`, `pool_pre_ping=settings.DB_POOL_PRE_PING`, and `pool_recycle=settings.DB_POOL_RECYCLE`.
- **Session Factory**: Produces `async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)`.

#### 3. FastAPI Session Dependency
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
```
Yields an active `AsyncSession`. Automatically executes `await session.commit()` upon successful route execution, triggers `await session.rollback()` on unhandled exceptions, and guarantees `await session.close()` in the `finally` block.

#### 4. Lifecycle Methods
- `init_db(engine: Optional[AsyncEngine] = None) -> None`:
  1. Executes `CREATE EXTENSION IF NOT EXISTS vector;` when connected to PostgreSQL.
  2. Creates all ORM tables registered with `Base.metadata` via `conn.run_sync(Base.metadata.create_all)`.
  3. Seeds Mexican AML jurisprudence articles idempotently via `seed_legal_knowledge(session)`.
  4. Seeds core banking entities from sample CSVs via `seed_core_banking_data(session)`.
- `close_db() -> None`: Disposes of the engine connection pool via `await _engine.dispose()`.

---

### 3.3 PII Redaction & Legal Compliance Masking (`backend/core/masking.py`)

To adhere to Mexican data privacy statutes (LFPDPPP) and banking secrecy standards (CNBV/LIC), all sensitive personal and account identifiers must be masked before transmission to external systems.

#### Masking Algorithms

```python
# Regular Expressions
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
CLABE_REGEX = re.compile(r"\b(\d{4})\d{10}(\d{4})\b")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{2,3}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}")
```

| Function | Input Pattern | Transformation Rule | Example Output |
| :--- | :--- | :--- | :--- |
| `mask_clabe(clabe)` | 18-digit Mexican CLABE | Preserves first 4 digits (bank code) and last 4 digits (account suffix), masking middle 10 digits with `*`. | `012180015678901234` $\to$ `0121**********1234` |
| `mask_email(email)` | Standard email address | Preserves first and last character of local-part; preserves domain unaltered. | `investigador@sat.gob.mx` $\to$ `i**********r@sat.gob.mx` |
| `mask_phone(phone)` | Digits / formatted phone | Strips non-digits; preserves only the final 4 digits, prepending `******`. | `+52 (81) 8345-6789` $\to$ `******6789` |
| `mask_address(addr)` | Physical street address | Completely replaces domicile details with standard legal notice string. | `[DIRECCIÓN PROTEGIDA / REDACTED ADDRESS]` |
| `mask_ssn(ssn)` | CURP / SSN / Tax ID | Preserves final 4 characters; masks preceding characters as `***-**-`. | `***-**-9876` |
| `mask_free_text(text)` | Arbitrary narrative text | Scans free text with regexes to replace embedded emails and 18-digit CLABEs. | Masks occurrences inside invoice `concepto` or ledger description fields. |

#### Recursive Redaction
- `mask_sensitive_record(record: Dict[str, Any]) -> Dict[str, Any]`: Traverses a flat or nested dictionary. Direct field names matching `SENSITIVE_FIELD_HANDLERS` (`bank_clabe`, `from_clabe`, `to_clabe`, `contact_email`, `personal_email`, `work_email`, `primary_phone`, `cell_phone`, `address`, `street_addr`, `ssn`, `birth_date`) are transformed. Free-text fields (`description`, `reference`, `concepto_text`, `note`, `sentence`, `scope_text`) are processed through `mask_free_text`. Key relational and evidentiary identifiers (`rfc`, `uuid`, `entry_id`, `po_id`, `contract_id`) are preserved intact.
- `mask_sensitive_payload(payload: Any) -> Any`: Traverses arbitrary nested structures containing dicts, lists, and primitives.

---

### 3.4 Forensic ORM Models & pgvector Jurisprudence (`backend/models/forensic.py`)

#### Declarative Base & SQLite Test Compatibility
```python
class Base(AsyncAttrs, DeclarativeBase):
    pass
```
To enable automated CI and local unit tests without requiring a live PostgreSQL instance, compiler extensions compile pgvector and JSONB types to standard SQLite types:
- `@compiles(Vector, "sqlite")`: Compiles to `"TEXT"`.
- `@compiles(JSONB, "sqlite")`: Compiles to `"JSON"`.
- `JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")`: Uses binary JSON on PostgreSQL and text-based JSON on SQLite.

#### 1. Model: `InvestigationCase`
Table: `investigation_cases`
Represents an AML investigation case created from an uploaded transaction CSV dataset.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Uuid` | Primary Key, default `uuid.uuid4` | Unique case identifier. |
| `filename` | `String(255)` | Not Null | Original filename of uploaded dataset. |
| `status` | `String(50)` | Not Null, default `"PENDING"` | Lifecycle status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`). |
| `created_at` | `DateTime(tz=True)` | Server Default `now()` | Case creation timestamp. |
| `updated_at` | `DateTime(tz=True)` | Server Default `now()`, onupdate `now()` | Timestamp of last status or verdict update. |
| `ingestion_metadata` | `JSON_DOCUMENT` | Not Null, default `{}` | Summary stats from Polars ingestion (raw row count, columns, total volume). |
| `metrics` | `JSON_DOCUMENT` | Not Null, default `{}` | Topological metrics from NetworkX pruning. |
| `subgraph` | `JSON_DOCUMENT` | Not Null, default `{}` | Isolated suspicious subgraph nodes and edges. |
| `patterns` | `JSON_DOCUMENT` | Not Null, default `{}` | Extracted circular flow cycles and pass-through mule accounts. |
| `verdict` | `JSON_DOCUMENT` | Nullable, default `None` | Final forensic verdict, risk level, confidence score, and legal recommendations. |
| `transactions` | Relationship | `cascade="all, delete-orphan"`, `passive_deletes=True` | 1-to-many relationship with `TransactionRecord`. |

#### 2. Model: `TransactionRecord`
Table: `transactions`
Individual transactions from the raw or pruned dataset.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Uuid` | Primary Key, default `uuid.uuid4` | Unique transaction ID. |
| `case_id` | `Uuid` | Foreign Key `investigation_cases.id`, `ondelete="CASCADE"`, Index | Associated case ID. |
| `origin` | `String(100)` | Index, Not Null | Originating bank account number. |
| `destination` | `String(100)` | Index, Not Null | Beneficiary bank account number. |
| `amount` | `Numeric(18, 2)` | Not Null | Transaction amount in MXN. |
| `timestamp` | `DateTime(tz=True)` | Not Null | Transaction execution timestamp or step. |
| `is_suspicious` | `Boolean` | Index, default `False` | Deterministic suspicion flag. |
| `reasons` | `JSON_DOCUMENT` | Not Null, default `[]` | List of topological justifications (e.g. `CIRCULAR_FLOW_CYCLE`, `PASSTHROUGH_BRIDGE`). |

#### 3. Model: `LegalArticleVector`
Table: `legal_knowledge_vectors`
Stores Mexican fiscal and anti-money laundering jurisprudence. Indexed with pgvector HNSW for approximate nearest neighbor retrieval using cosine distance.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Uuid` | Primary Key, default `uuid.uuid4` | Vector entry ID. |
| `article_code` | `String(50)` | Unique, Index, Not Null | Statutory identifier (e.g., `CFF-ART-69B`, `NIF-A2-MATERIALIDAD`). |
| `law_name` | `String(100)` | Not Null | Formal legal statute name. |
| `content` | `Text` | Not Null | Jurisprudence body, doctrinal criteria, or statutory text. |
| `embedding` | `Vector(1536)` | Nullable | 1536-dimensional unit-norm vector embedding. |

**Index Definition**:
```python
__table_args__ = (
    Index(
        "idx_legal_vectors_hnsw",
        "embedding",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    ),
)
```

#### Deterministic Vector Embedding Generation
`generate_deterministic_embedding(text: str, dim: int = 1536) -> List[float]` generates reproducible, unit-normalized vector embeddings derived from the SHA-256 hash of the input text:
1. Progressively computes 32-bit signed integers from consecutive 4-byte chunks of SHA-256 digests.
2. Normalizes values to $[-1.0, 1.0]$.
3. Computes the Euclidean norm $L_2 = \sqrt{\sum x_i^2}$ and normalizes the vector such that $\sum x_i^2 = 1.0$, satisfying unit-norm requirements for cosine similarity queries (`<=>`).

#### Seed Jurisprudence Knowledge Base
The database automatically seeds six key Mexican AML legal articles on startup:
1. `CFF-ART-69B`: Código Fiscal de la Federación (Artículo 69-B) — Presunción de operaciones inexistentes, tipologías EFOS vs. EDOS, plazos de 15 días hábiles para desvirtuar y nulidad de comprobantes.
2. `NIF-A2-MATERIALIDAD`: Normas de Información Financiera / Tesis SCJN 2a./J. 78/2019 — Sustancia económica sobre forma jurídica y la Tríada Probatoria Forense (Fecha Cierta, Entregables Contemporáneos, Trazabilidad Financiera).
3. `UIF-ROI-24H`: Disposiciones UIF / LFPIORPI — Reporte de Operaciones Inusuales (ROI) dentro de 24-48h y prohibición de alertamiento (Tipping-Off).
4. `UIF-ROR-7500USD`: Disposiciones de Carácter General CNBV/UIF — Reporte de Operaciones Relevantes (ROR) con umbral de $\$7,500\text{ USD}$ y detección de pitufeo/estructuración.
5. `LIC-ART-115-BLOQUEO`: Ley de Instituciones de Crédito (Artículo 115) — Medidas cautelares de inmovilización de fondos y Lista de Personas Bloqueadas (LPB).
6. `CPF-ART-400BIS`: Código Penal Federal (Artículo 400 Bis) — Tipificación del delito de lavado de dinero y concurso con delitos fiscales del Art. 108 CFF.

#### 4. Core Banking Models & In-Memory Fallback Cache
- `AccountRecord` (`accounts`): Bank account profiles with KYC details (`dsply_nm`, `type`, `acct_stat`, `prior_sar_count`, `initial_deposit`, `ssn`, geolocation).
- `AccountMappingRecord` (`account_mappings`): Cross-reference relationships between accounts (`acct_id`) and customer party IDs (`cust_id`).
- `PartyRecord` (`parties`): Identity registry for individuals and organizations (`party_type`, `legal_name`, `nationality`, `occupation`, contact information).
- `CashTransactionRecord` (`cash_transactions`): ATM cash deposits and cashouts (`amount`, `tx_type`, `is_sar`).
- `IN_MEMORY_BANKING_DATA`: A pre-loaded in-memory dictionary cache populated at startup from sample CSVs (`accounts.csv`, `accountMapping.csv`, `individuals-bulkload.csv`, `organizations-bulkload.csv`, `cash_tx.csv`) providing sub-millisecond lookups even when PostgreSQL is offline.

---

### 3.5 Corporate Data Estate ORM Models (`backend/models/estate.py`)

Implements the forensic financial estate data model, mirroring Mexican CFDI 4.0 electronic invoicing and corporate accounting standards:

| Model | Table | Primary Key | Key Fields | Description |
| :--- | :--- | :--- | :--- | :--- |
| `VendorRecord` | `vendors` | `rfc` (`String(13)`) | `legal_name`, `registered_date`, `address`, `bank_clabe`, `category`, `contact_email` | Suppliers and commercial counterparties. |
| `InvoiceRecord` | `invoices` | `uuid` (`String(64)`) | `issuer_rfc`, `receiver_rfc`, `issue_date`, `subtotal`, `iva`, `total`, `concepto_text`, `uso_cfdi`, `forma_pago`, `status` | CFDI 4.0 digital fiscal invoices. |
| `LedgerRecord` | `ledger` | `entry_id` (`Integer`) | `date`, `account_code`, `account_name`, `debit`, `credit`, `description`, `invoice_uuid`, `cost_center`, `approver` | General ledger double-entry journal entries. |
| `BankTxnRecord` | `bank_txns` | `txn_id` (`String(64)`) | `date`, `from_clabe`, `to_clabe`, `amount`, `reference`, `channel` | Interbank SPEI and treasury wire transactions. |
| `PurchaseOrderRecord` | `purchase_orders` | `po_id` (`String(64)`) | `vendor_rfc`, `date`, `amount`, `requester`, `approver`, `description` | Corporate procurement requisitions and purchase orders. |
| `ContractRecord` | `contracts` | `contract_id` (`String(64)`) | `vendor_rfc`, `start_date`, `value`, `scope_text` | Commercial service and procurement contracts. |
| `EmployeeRecord` | `employees` | `emp_id` (`String(32)`) | `name`, `role`, `bank_clabe`, `hire_date` | Corporate employees and procurement officers. |
| `EfosRecord` | `efos_list` | `rfc` (`String(13)`) | `legal_name`, `status` (Presunto/Definitivo), `publication_date` | SAT Article 69-B blacklisted simulated invoice companies. |
| `ExhibitRecord` | `exhibits` | `exhibit_id` (`String(32)`) | `source_table`, `record_id`, `sentence` | Extracted audit exhibits and cross-evidence statements. |

---

### 3.6 Investigation API Schemas (`backend/schemas/investigation.py`)

Pydantic v2 schemas validating client uploads, metrics calculation, and Server-Sent Events (SSE).

#### 1. Graph & Pruning Topology Schemas
- `GraphNode`: Validates node data (`id`, `total_in`, `total_out`, `in_degree`, `out_degree`, `reasons`, `risk_score` $[0.0\text{--}1.0]$).
- `GraphEdge`: Validates directed edges (`source`, `target`, `amount`, `count`, `timestamps`, `reasons`).
- `SubgraphData`: Container for isolated suspicious elements (`nodes: List[GraphNode]`, `edges: List[GraphEdge]`).
- `InvestigationMetrics`: Mathematical audit metrics including `pruning_efficiency_pct`, `detected_cycles_count`, `passthrough_accounts_count`, and `suspicious_volume_mxn`.
- `CyclePattern`: Sequence and hop length of circular laundering loops (`path: List[str]`, `length: int`, `estimated_volume: float`).
- `PassthroughAccountPattern`: Mule account conduit statistics (`account`, `total_in`, `total_out`, `ratio`, `time_delta_hours`).

#### 2. Streaming Reasoning & Verdict Schemas
- `ThoughtEvent`: Emitted over SSE during investigative analysis:
  ```python
  class ThoughtEvent(BaseModel):
      step: int = Field(..., ge=1, le=6)
      phase: str
      message: str
      timestamp: Union[datetime, str]
  ```
- `VerdictPayload`: Final terminal payload emitted on stream closure:
  Includes `case_id`, `risk_level` (`CRÍTICO`, `ALTO`, `MEDIO`, `BAJO`), `fraud_type`, `total_amount_mxn`, `confidence_score` $[0.0\text{--}1.0]$, `entities_involved`, `patterns_summary`, `legal_recommendation`, and `audit_summary_text`.

#### 3. Request & Response Envelopes
- `InvestigationUploadResponse`: Returned by `POST /api/v1/investigations/upload`. Contains `case_id`, initial `status="PROCESSING"`, `metrics`, `subgraph`, and `patterns`.
- `InvestigationSummary`: Summarized model for case directory listing with `model_validator` resolving aliases across dicts and ORM instances.
- `InvestigationPaginationResponse`: Standard pagination envelope (`total`, `page`, `page_size`, `total_pages`, `items`).
- `InvestigationDetailResponse`: Comprehensive detail model returning full case graphs, metadata, and verdict if completed.
- `EstateAuditRequest` & `EstateAuditResponse`: Input/output contracts for multi-source financial estate audits.

---

### 3.7 Agent Tools & Dynamic Query Contracts (`backend/schemas/agent_tools.py`)

Defines the contract for external n8n ReAct agents and internal dynamic SQL generation.

#### 1. Security Whitelists & Enums
- `TargetEntity`: Target dataset enum (`transactions`, `cases`, `entities`, `nodes`, `edges`, `patterns`, `cycles`, `passthrough_accounts`, `legal_precedents`, `legal_vectors`, `accounts`, `parties`, `cash_transactions`, `account_mappings`).
- `FilterOperator`: Supported operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, `not_in`).
- `SortOrder`: Direction (`asc`, `desc`).
- `TARGET_FIELD_WHITELISTS`: Security dictionary mapping every `TargetEntity` to its permitted queryable fields and data types. Prevents arbitrary column access or SQL injection attacks.
- `CASE_SCOPED_TARGETS`: Set of targets requiring mandatory `case_id` qualification (`transactions`, `entities`, `nodes`, `edges`, `patterns`, `cycles`, `passthrough_accounts`).

#### 2. Dynamic Query Engine Schemas
```python
class QueryFilter(BaseModel):
    field: str
    operator: FilterOperator
    value: Any

class DynamicQueryRequest(BaseModel):
    target: Union[TargetEntity, str]
    case_id: Optional[Union[uuid.UUID, str]] = None
    filters: List[QueryFilter] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_order: SortOrder = SortOrder.ASC
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
```
Validators enforce:
1. `case_id` presence for any target in `CASE_SCOPED_TARGETS`.
2. Array validation when using `in` or `not_in` operators.
3. Whitelist validation verifying all filter and sort columns exist in `TARGET_FIELD_WHITELISTS[target]`.

#### 3. Specialized Forensic Agent Tool Contracts
The schema defines 10 specialized tool contracts used by the forensic reasoning agent:

| Tool Contract | Purpose | Key Request Fields | Key Response Fields |
| :--- | :--- | :--- | :--- |
| `TransactionQueryRequest`/`Response` | Filter transactions inside a case | `case_id`, `entity_id`, `min_amount`, `max_amount`, `start_time`, `end_time` | `total`, `total_volume_mxn`, `items: List[TransactionItem]` |
| `EntityProfileRequest`/`Response` | Profile counterparty nodes | `case_id`, `entity_id`, `min_risk_score`, `is_suspicious` | `total_entities`, `entities: List[EntityProfileItem]` |
| `PatternQueryRequest`/`Response` | Extract cycles & mule accounts | `case_id`, `pattern_type`, `min_cycle_length`, `min_passthrough_ratio` | `cycles: List[CyclePatternItem]`, `passthrough_mules: List[PassthroughMuleItem]` |
| `LegalPrecedentQueryRequest`/`Response`| Vector search on Mexican law | `query_text`, `top_k`, `similarity_threshold`, `law_name_filter` | `total_matches`, `results: List[LegalPrecedentItem]` |
| `RelatedEntitiesRequest`/`Response` | Find persistent counterparties | `entity_id`, `case_id`, `min_tx_count`, `min_volume` | `target_entity_id`, `items: List[RelatedEntityItem]` |
| `CompareEntitiesRequest`/`Response` | Common ownership & SSN analysis| `entity_ids: List[str]`, `case_id` | `groups_by_owner`, `comparisons: List[EntityOwnerComparisonItem]` |
| `AnalyzePaymentPatternsRequest`/`Response`| Classify flow topographies | `case_id`, `entity_id` | `has_fraudulent_patterns`, `has_circular_patterns`, `has_mule_patterns` |
| `FinancialHistoryRequest`/`Response` | Retrieve KYC & SAR history | `account_id`, `party_id` | `owner_name`, `associated_accounts`, `prior_sar_count`, `initial_deposit` |
| `CashoutRequest`/`Response` | ATM cash withdrawal analysis | `account_id`, `min_amount`, `start_date`, `end_date` | `total_cashouts`, `total_amount`, `items: List[CashoutItem]` |
| `TraceMoneyFlowRequest`/`Response` | Breadth/depth money trail trace| `source_account`, `destination_account`, `case_id`, `max_depth` | `total_paths`, `paths: List[FlowPathItem]` |

---

## 4. Key Files, Models, and Schemas Reference

| Module File | Exported Class / Symbol | Type | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| `backend/core/config.py` | `Settings`, `settings` | Pydantic BaseSettings | Centralized environment, CORS, and threshold configuration. |
| `backend/core/database.py` | `get_db` | Async Generator | FastAPI dependency providing managed transactional `AsyncSession`. |
| `backend/core/database.py` | `normalize_database_url` | Function | Transforms generic URLs to async drivers and normalizes asyncpg SSL parameters. |
| `backend/core/database.py` | `init_db`, `close_db` | Async Functions | Lifecycle hooks for pgvector extension, table creation, and connection pool teardown. |
| `backend/core/masking.py` | `mask_clabe`, `mask_email` | Functions | Atomic PII transformation functions for banking identifiers. |
| `backend/core/masking.py` | `mask_sensitive_payload` | Function | Recursive dictionary and list PII redaction engine. |
| `backend/models/forensic.py` | `Base` | Declarative Base | SQLAlchemy 2.0 async base with SQLite cross-dialect compiler hooks. |
| `backend/models/forensic.py` | `InvestigationCase` | ORM Model | Persists case lifecycle, graph metrics, isolated subgraphs, and verdicts. |
| `backend/models/forensic.py` | `TransactionRecord` | ORM Model | Individual financial ledger rows linked to an investigation case. |
| `backend/models/forensic.py` | `LegalArticleVector` | ORM Model | Stores 1536-dimensional embeddings with an HNSW cosine index for jurisprudence retrieval. |
| `backend/models/forensic.py` | `AccountRecord`, `PartyRecord` | ORM Models | Core banking entity and KYC customer models. |
| `backend/models/forensic.py` | `generate_deterministic_embedding` | Function | Reproducible SHA-256 derived unit-norm pseudo-random embedding generator. |
| `backend/models/estate.py` | `VendorRecord`, `InvoiceRecord` | ORM Models | CFDI 4.0 vendor registry and electronic invoice records. |
| `backend/models/estate.py` | `LedgerRecord`, `BankTxnRecord` | ORM Models | General ledger accounting entries and SPEI wire records. |
| `backend/models/estate.py` | `EfosRecord` | ORM Model | SAT Article 69-B blacklisted simulated invoice entities. |
| `backend/schemas/investigation.py` | `InvestigationUploadResponse` | Pydantic Model | API response envelope returned after CSV ingestion and deterministic pruning. |
| `backend/schemas/investigation.py` | `VerdictPayload`, `ThoughtEvent` | Pydantic Models | Server-Sent Events (SSE) data contracts for agent reasoning and verdicts. |
| `backend/schemas/agent_tools.py` | `DynamicQueryRequest`, `DynamicQueryResponse` | Pydantic Models | Composable AST query request and response models with column whitelisting. |
| `backend/schemas/agent_tools.py` | `LegalPrecedentQueryRequest` | Pydantic Model | Natural language vector query request for Mexican AML statutes. |
| `backend/schemas/agent_tools.py` | `RelatedEntitiesRequest` | Pydantic Model | Query contract for identifying persistent counterparty relationships. |

---

## 5. Dependencies & Consumers

### Internal Dependencies
- `backend/core/config.py` is imported by `backend/core/database.py`, `backend/services/deterministic_filter.py`, `backend/api/routes/investigations.py`, and `backend/api/routes/tts.py`.
- `backend/models/forensic.py` provides `Base` to `backend/models/estate.py` ensuring all models register on a shared `MetaData` catalog.
- `backend/core/masking.py` is consumed by `backend/api/routes/investigations.py` and `backend/services/tool_registry.py` prior to JSON serialization.

### External Dependencies
- **`pydantic-settings` & `pydantic` (v2)**: Core validation, settings management, and field aliasing.
- **`SQLAlchemy` (v2.0+)**: Async ORM, session management, and expression language.
- **`asyncpg` & `psycopg`**: Async PostgreSQL drivers.
- **`pgvector`**: PostgreSQL vector extension integration (`pgvector.sqlalchemy.Vector`).

### Primary Consumers
- **`backend/api/routes/investigations.py`**: Utilizes `get_db`, `InvestigationCase`, and `schemas/investigation.py`.
- **`backend/api/routes/agent_tools.py`**: Utilizes `get_db`, `schemas/agent_tools.py`, and `core/masking.py`.
- **`backend/services/tool_registry.py`**: Translates Pydantic tool requests into parameterized SQL statements against ORM models.
- **Frontend / Next.js Client**: Consumes masked schemas mirrored in `frontend/types/investigation.ts`.

---

## 6. Edge Cases, Gotchas & Operational Invariants

1. **`asyncpg` Query Parameter Rejection**:
   - `asyncpg` does not accept `?sslmode=require` in the database connection string. Passing it directly causes engine initialization to fail.
   - Always run connection strings through `normalize_database_url()`, which strips `sslmode` from the URL query and places it in `connect_args={"ssl": "require"}`.
2. **SQLite Testing Type Discrepancies**:
   - SQLite does not natively support `VECTOR` or `JSONB` column types.
   - The compiler hooks (`@compiles(Vector, "sqlite")` and `@compiles(JSONB, "sqlite")`) in `backend/models/forensic.py` map these to `TEXT` and `JSON` respectively during test runs with `sqlite+aiosqlite://`.
3. **Mandatory Case Scoping in Dynamic Queries**:
   - In dynamic queries targeting `transactions`, `nodes`, `edges`, `cycles`, or `passthrough_accounts`, `case_id` is strictly mandatory. Omitting `case_id` will trigger a `422 Unprocessable Entity` validation error to prevent cross-tenant data leakage.
4. **Strict Column Whitelisting**:
   - Dynamic queries against `TARGET_FIELD_WHITELISTS` validate both `filters` and `sort_by` parameters. Attempting to filter or sort by unwhitelisted columns immediately raises a `ValueError` describing permissible fields.
5. **Deterministic Embedding Cosine Normalization**:
   - `generate_deterministic_embedding` calculates the Euclidean norm $L_2 = \sqrt{\sum x_i^2}$. If norm is non-zero, each dimension is divided by the norm and rounded to 6 decimal places. This ensures that the dot product directly equals the cosine similarity when querying via pgvector's `<=>` operator.
6. **In-Memory Banking Cache Resilience**:
   - `IN_MEMORY_BANKING_DATA` in `backend/models/forensic.py` loads accounts, mappings, parties, and cashouts into memory on module import. If PostgreSQL connection drops or `DATABASE_URL` is unset, tool registry lookups fall back smoothly to the in-memory cache.
