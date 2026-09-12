# Specification Discovery & Forensic Legal Architecture Report: Milestone 1

**Project**: Forensic Auditor Python Backend  
**Milestone**: M1 (Database Layer: Models & Legal Precedents)  
**Author**: Spec Miner (`spec_miner_m1_1`)  
**Date**: 2026-09-12  
**Target Modules**: `backend/models/forensic.py`, `backend/core/database.py`, `backend/core/config.py`, `backend/requirements.txt`

---

## 1. Executive Summary
This report establishes the authoritative specification for Milestone 1 of the Forensic Auditor platform. It defines the async SQLAlchemy 2.0 relational and vector database schema connecting to TigerData PostgreSQL with `pgvector`, specifies connection pooling and SSL enforcement mechanisms, details full schema compatibility with SQLite for automated testing, and encodes authoritative Mexican AML and tax compliance jurisprudence (CFF Art. 69-B, NIF A-2, and UIF/GAFI regulations) for retrieval-augmented generation (RAG) and automated audit verdicts.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | Database Engine | Async Engine Creation | Initializes `create_async_engine` with TigerData PostgreSQL driver, SSL enforcement, and connection pooling | `DATABASE_URL`, pool parameters | `AsyncEngine` instance | Raises `RuntimeError` or `ValueError` if `DATABASE_URL` is empty or malformed | ORIGINAL_REQUEST §R1, PROJECT.md §1 |
| 2 | Database Engine | Driver URL Normalization | Automatically normalizes `postgres://` or `postgresql://` to `postgresql+asyncpg://` or `postgresql+psycopg://` | Raw connection string | Normalized async driver URL | Retains original URL if already formatted with async driver prefix | PROJECT.md §1, doc/architecture |
| 3 | Database Engine | SSL Enforcement | Enforces `sslmode=require` / `ssl="require"` for secure remote TigerData PostgreSQL communication | SSL parameters, engine connect args | Validated encrypted TLS transport | Fails handshake if remote server refuses TLS | ORIGINAL_REQUEST §R1 |
| 4 | Database Engine | Connection Pooling | Configures connection pool with `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, and `pool_recycle=3600` | Pool configuration settings | Managed connection pool | Recycles stale connections; raises pool overflow timeout if exhausted | ORIGINAL_REQUEST §R1, PROJECT.md §1 |
| 5 | Database Session | Managed `get_db` Dependency | FastAPI dependency yielding an `AsyncSession` with auto-rollback on exception and guaranteed closure | HTTP request context | `AsyncGenerator[AsyncSession, None]` | Rolls back transaction and closes session upon unhandled exception | ORIGINAL_REQUEST §R1, PROJECT.md §2 |
| 6 | Database Lifecycle | `init_db()` Extension & Schema Hook | Executes `CREATE EXTENSION IF NOT EXISTS vector;` followed by `Base.metadata.create_all()` and precedent seeding | Async database engine | Schema and extension initialization | Catches errors gracefully; skips vector extension if running in SQLite test mode | ORIGINAL_REQUEST §R1, PROJECT.md §2 |
| 7 | Database Lifecycle | `close_db()` Teardown Hook | Disposes of engine connection pool during FastAPI application shutdown | Async database engine | None | Disposes pool gracefully | PROJECT.md §2 |
| 8 | Models | `InvestigationCase` Model | Persistent record for case metadata, Polars ingestion stats, NetworkX metrics, pruned subgraph, patterns, and verdict | Case attributes, JSONB payloads | ORM entity mapped to `investigation_cases` table | Validates types; raises `IntegrityError` if required fields missing | ORIGINAL_REQUEST §R1, doc/data-and-compliance |
| 9 | Models | `TransactionRecord` Model | Individual ledger records linked to case with origin, destination, amount, timestamp, suspicion flag, and reasons | Transaction row fields, foreign key | ORM entity mapped to `transactions` table | Foreign key cascade deletion on parent case delete | ORIGINAL_REQUEST §R1, doc/data-and-compliance |
| 10 | Models | `LegalArticleVector` Model | Knowledge base article with code, law name, textual content, and 1536-dim embedding with HNSW index | Legal precedent text, article code, vector | ORM entity mapped to `legal_knowledge_vectors` table | Enforces unique `article_code`; raises `IntegrityError` on duplicate | ORIGINAL_REQUEST §R1, doc/data-and-compliance |
| 11 | Models | HNSW Cosine Index | High-performance approximate nearest neighbor index on `LegalArticleVector.embedding` with `m=16, ef_construction=64` | `embedding` column | HNSW index `idx_legal_vectors_hnsw` | Index created in PostgreSQL; skipped or handled via compiler in SQLite | ORIGINAL_REQUEST §R1, doc/data-and-compliance |
| 12 | Models | SQLite Dialect Compatibility | `@compiles` compiler extensions mapping `Vector` to `TEXT` and `JSONB` to `JSON` for seamless in-memory SQLite testing | SQLite dialect compiler | Type string definitions | Prevents `CompileError` during test suite execution | PROJECT.md §6 |
| 13 | Compliance Seed | CFF Art. 69-B Knowledge | Comprehensive legal text distinguishing EFOS vs EDOS, 15 days rebuttal timeline, and 30 days regularization | Static precedent specification | Seed database row in `legal_knowledge_vectors` | Idempotent upsert by `article_code` | doc/data-and-compliance §5.1 |
| 14 | Compliance Seed | NIF A-2 Materiality Triad | Authoritative text defining economic substance, fecha cierta contracts, verifiable deliverables, and flow tracing | Static precedent specification | Seed database row in `legal_knowledge_vectors` | Idempotent upsert by `article_code` | doc/data-and-compliance §5.2 |
| 15 | Compliance Seed | UIF & GAFI Regulatory Guidelines | Authoritative text defining 24-48h ROI filing, $7,500 USD ROR threshold, Art. 115 LIC account freezing, and tipping-off ban | Static precedent specification | Seed database row in `legal_knowledge_vectors` | Idempotent upsert by `article_code` | doc/data-and-compliance §5.3 |
| 16 | Compliance Seed | Deterministic Vector Generator | Utility generating 1536-dim unit-normalized synthetic vectors from text hash for test and offline vector matching | Text string, dimension (1536) | `List[float]` with unit norm | Deterministic output for reproducible semantic similarity | doc/data-and-compliance §5.4 |
| 17 | Configuration | Database Settings Expansion | Pydantic Settings attributes for connection URL, pool sizing, and query echoing | Environment variables or `.env` | `Settings` attributes | Validates types and provides production defaults | ORIGINAL_REQUEST §R1, PROJECT.md §1 |
| 18 | Dependencies | PostgreSQL & Vector Drivers | Pinning `asyncpg`, `psycopg[binary]`, `pgvector`, `aiosqlite`, and `greenlet` in `requirements.txt` | Dependency specifications | Installed packages | Requires build/install dependencies | ORIGINAL_REQUEST §R1 |

---

## 3. Edge Cases

| # | Feature | Input | Observed / Required Behavior |
|---|---|---|---|
| 1 | Database Connection | Unconfigured or empty `DATABASE_URL` | Application must not crash on import; `get_db()` must raise an informative `RuntimeError` ("DATABASE_URL environment variable is not configured.") when a route requests a session. |
| 2 | Driver URL Normalization | `DATABASE_URL = "postgres://user:pass@host:5432/db"` (Heroku/Render format) | Driver normalizer rewrites scheme to `postgresql+asyncpg://user:pass@host:5432/db`. |
| 3 | SSL Enforcement | `postgresql+asyncpg://...` with `sslmode=require` query parameter | `asyncpg` does not accept `sslmode` query param natively; connection normalizer strips query param and supplies `connect_args={"ssl": "require"}` to `create_async_engine`. |
| 4 | Cascade Deletion | Case deletion via `session.delete(case)` | Database foreign key `ON DELETE CASCADE` and SQLAlchemy ORM `cascade="all, delete-orphan", passive_deletes=True` automatically deletes all associated `TransactionRecord` rows without orphan rows. |
| 5 | Testing in SQLite | In-memory `sqlite+aiosqlite:///:memory:` table creation | `pgvector.sqlalchemy.Vector` and `sqlalchemy.dialects.postgresql.JSONB` raise `CompileError` on SQLite unless `@compiles(Vector, "sqlite")` returning `"TEXT"` and `@compiles(JSONB, "sqlite")` returning `"JSON"` are registered. |
| 6 | Vector Cosine Index in SQLite | `Index(..., postgresql_using="hnsw", ...)` | SQLite dialect ignores `postgresql_using` and `postgresql_with` clauses during `create_all()`, preventing syntax errors. |
| 7 | Duplicate Precedent Seeding | Multiple runs of `init_db()` or seeding scripts | Seed mechanism must perform idempotent upsert or verify `article_code` existence before insertion to prevent `IntegrityError`. |
| 8 | Large Financial Amounts | Amount exceeding standard integer capacity (e.g. $950,000,000.00 MXN) | `Numeric(18, 2)` preserves exact decimal precision without floating point truncation or rounding anomalies. |
| 9 | Timezone Consistency | Ingestion timestamps without timezone | All model timestamps enforce `DateTime(timezone=True)`. Naive timestamps are normalized to UTC before insertion. |
| 10 | Ingestion Metadata Nullability | CSV upload with missing optional headers | `ingestion_metadata`, `metrics`, `subgraph`, and `patterns` use `default=dict` and `nullable=False`; `verdict` is `nullable=True` until case analysis is finalized. |

---

## 4. Authoritative Specification for `backend/models/forensic.py`

### 4.1 Architecture & Schema Mapping
The ORM models are mapped using modern **SQLAlchemy 2.0 Declarative Mapping** (`Mapped` and `mapped_column`), providing strict type validation, IDE autocompletion, and schema reflection.

```python
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
    func,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.compiler import compiles


# -----------------------------------------------------------------------------
# Base & SQLite Test Compatibility Compilers
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# Compiler hooks ensuring in-memory SQLite test execution does not fail
@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Cross-dialect JSONB type: native JSONB in PostgreSQL, JSON in SQLite
JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")
```

---

### 4.2 Model 1: `InvestigationCase`

#### Purpose
Represents an AML investigation case created from an uploaded IBM AMLSim or core banking transaction CSV dataset. Tracks execution lifecycle status, topological graph metrics, isolated suspicious subgraphs, extracted cycles and mule conduits, and the final forensic verdict.

#### Table Definition
- **Table Name**: `investigation_cases`
- **Class**: `InvestigationCase(Base)`

#### Column Specifications
| Field | Python Type | SQLAlchemy Type | Constraints / Defaults | Description |
|---|---|---|---|---|
| `id` | `uuid.UUID` | `Uuid` (or `PG_UUID(as_uuid=True)`) | `primary_key=True`, `default=uuid.uuid4` | Case primary key |
| `filename` | `str` | `String(255)` | `nullable=False` | Original filename of uploaded dataset |
| `status` | `str` | `String(50)` | `nullable=False`, `default="PENDING"` | Lifecycle status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) |
| `created_at` | `datetime` | `DateTime(timezone=True)` | `server_default=func.now()`, `nullable=False` | Creation UTC timestamp |
| `updated_at` | `datetime` | `DateTime(timezone=True)` | `server_default=func.now()`, `onupdate=func.now()`, `nullable=False` | Last modification UTC timestamp |
| `ingestion_metadata`| `Dict[str, Any]` | `JSONB` (via `JSON_DOCUMENT`) | `nullable=False`, `default=dict` | Summary ingestion stats (`total_records`, `total_volume`, `unique_accounts`, `original_columns`) |
| `metrics` | `Dict[str, Any]` | `JSONB` (via `JSON_DOCUMENT`) | `nullable=False`, `default=dict` | Deterministic pruning metrics (`pruning_efficiency_pct`, `suspicious_volume_mxn`, counts) |
| `subgraph` | `Dict[str, Any]` | `JSONB` (via `JSON_DOCUMENT`) | `nullable=False`, `default=dict` | Isolated suspicious subnetwork (`nodes: [...]`, `edges: [...]`) |
| `patterns` | `Dict[str, Any]` | `JSONB` (via `JSON_DOCUMENT`) | `nullable=False`, `default=dict` | Extracted patterns (`cycles: [...]`, `passthrough_accounts: [...]`) |
| `verdict` | `Optional[Dict[str, Any]]` | `JSONB` (via `JSON_DOCUMENT`) | `nullable=True`, `default=None` | Final forensic verdict payload persisted upon stream completion |

#### Relationships
- `transactions`: `Mapped[List["TransactionRecord"]] = relationship("TransactionRecord", back_populates="case", cascade="all, delete-orphan", passive_deletes=True)`

---

### 4.3 Model 2: `TransactionRecord`

#### Purpose
Stores individual financial transactions extracted from the dataset. Provides indexed relational fields for rapid counterparty profiling, flow filtering, and forensic graph reconstruction.

#### Table Definition
- **Table Name**: `transactions`
- **Class**: `TransactionRecord(Base)`

#### Column Specifications
| Field | Python Type | SQLAlchemy Type | Constraints / Defaults | Description |
|---|---|---|---|---|
| `id` | `uuid.UUID` | `Uuid` (or `PG_UUID(as_uuid=True)`) | `primary_key=True`, `default=uuid.uuid4` | Transaction unique ID |
| `case_id` | `uuid.UUID` | `ForeignKey("investigation_cases.id", ondelete="CASCADE")` | `index=True`, `nullable=False` | Parent case reference |
| `origin` | `str` | `String(100)` | `index=True`, `nullable=False` | Originating account ID / CLABE / RFC |
| `destination` | `str` | `String(100)` | `index=True`, `nullable=False` | Destination account ID / CLABE / RFC |
| `amount` | `Decimal` | `Numeric(18, 2)` | `nullable=False` | Transaction monetary value in MXN |
| `timestamp` | `datetime` | `DateTime(timezone=True)` | `nullable=False` | Transaction datetime / normalized step |
| `is_suspicious` | `bool` | `Boolean` | `default=False`, `index=True`, `nullable=False` | Flagged by graph pruning filter |
| `reasons` | `List[str]` | `JSONB` (via `JSON_DOCUMENT`) | `default=list`, `nullable=False` | Typology tags (`CYCLE_STEP`, `PASSTHROUGH_BRIDGE`) |

#### Relationships
- `case`: `Mapped["InvestigationCase"] = relationship("InvestigationCase", back_populates="transactions")`

---

### 4.4 Model 3: `LegalArticleVector`

#### Purpose
Knowledge base repository storing Mexican AML, tax, and banking jurisprudence. Supports sub-millisecond approximate nearest neighbor semantic vector retrieval using `pgvector` with HNSW cosine indexing (`vector_cosine_ops`), as well as keyword-based fallback matching.

#### Table Definition
- **Table Name**: `legal_knowledge_vectors`
- **Class**: `LegalArticleVector(Base)`

#### Column Specifications
| Field | Python Type | SQLAlchemy Type | Constraints / Defaults | Description |
|---|---|---|---|---|
| `id` | `uuid.UUID` | `Uuid` (or `PG_UUID(as_uuid=True)`) | `primary_key=True`, `default=uuid.uuid4` | Precedent unique identifier |
| `article_code` | `str` | `String(50)` | `unique=True`, `index=True`, `nullable=False` | Unique statutory identifier (e.g. `CFF-ART-69B`) |
| `law_name` | `str` | `String(100)` | `nullable=False` | Official name of the code or standard |
| `content` | `str` | `Text` | `nullable=False` | Comprehensive legal text and evidentiary criteria |
| `embedding` | `Optional[List[float]]`| `Vector(1536)` | `nullable=True` | 1536-dimensional semantic vector embedding |

#### Indexes
- **HNSW Cosine Index**:
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

---

## 5. Authoritative Mexican AML Jurisprudence Knowledge Base

The knowledge base encapsulates statutory criteria, procedural timelines, and evidentiary burdens established in Mexican federal legislation, administrative rules, and judicial precedents.

### 5.1 Precedent 1: CFF Art. 69-B (Inexistencia de Operaciones / EFOS y EDOS)
- **Article Code**: `CFF-ART-69B`
- **Law Name**: `Código Fiscal de la Federación`
- **Full Authoritative Text**:
> **Artículo 69-B del Código Fiscal de la Federación: Presunción de Inexistencia de Operaciones Amparadas con Comprobantes Fiscales Digitales (CFDI).**
> 
> 1. **Presunción de Inexistencia**: Cuando la autoridad fiscal (SAT) detecte que un contribuyente ha estado emitiendo comprobantes sin contar con los activos, personal, infraestructura o capacidad material, directa o indirectamente, para prestar los servicios o producir, comercializar o entregar los bienes que amparan tales comprobantes, o bien, que dicha persona no se encuentre localizable en su domicilio fiscal, se presumirá la inexistencia de las operaciones amparadas en tales comprobantes.
> 
> 2. **Diferenciación Dogmática: EFOS vs. EDOS**:
>    - **EFOS (Empresas que Facturan Operaciones Simuladas)**: Entidades emisoras que comercializan facturas sin sustento material para generar deducciones indebidas a terceros ("empresas fantasma" o "factureras"). En el grafo transaccional, operan típicamente como nodos puente de entrada y salida con dispersión casi total de recursos y retención nula de valor.
>    - **EDOS (Empresas que Deducen Operaciones Simuladas)**: Contribuyentes que adquieren o incorporan dichos CFDI en su contabilidad para erosionar la base gravable del Impuesto Sobre la Renta (ISR) y solicitar saldos a favor o acreditamientos improcedentes de IVA.
> 
> 3. **Plazos Procedimentales de Desvirtuación**:
>    - **Publicación Provisional (DOF y Portal SAT)**: Los contribuyentes notificados cuentan con un **plazo perentorio de quince (15) días hábiles**, contados a partir de la última de las notificaciones, para comparecer y presentar pruebas y alegatos que desvirtúen la presunción de inexistencia. Podrán solicitar una prórroga improrrogable de diez (10) días adicionales.
>    - **Publicación Definitiva**: Si el contribuyente no comparece o no acredita su capacidad material y operativa, el SAT publicará la lista definitiva en el Diario Oficial de la Federación. La resolución definitiva produce la **nulidad de pleno derecho de todos los comprobantes emitidos**, eliminando cualquier efecto fiscal.
> 
> 4. **Plazo de Regularización de Terceros (EDOS)**:
>    - Las personas físicas o morales que hayan dado efectos fiscales a los comprobantes emitidos por un EFOS definitivo cuentan con **treinta (30) días hábiles** siguientes a la publicación del listado definitivo en el DOF para acreditar ante el SAT la materialidad real de las operaciones o, en su defecto, corregir su situación fiscal mediante la reversión de deducciones y pago de contribuciones omitidas con actualizaciones y recargos, previo al inicio del ejercicio de facultades de comprobación y consignación por delito de defraudación fiscal calificada (Art. 108 CFF).

---

### 5.2 Precedent 2: NIF A-2 (Materialidad de Operaciones y Tríada Probatoria)
- **Article Code**: `NIF-A2-MATERIALIDAD`
- **Law Name**: `Normas de Información Financiera (CINIF) / Tesis SCJN 2a./J. 78/2019`
- **Full Authoritative Text**:
> **Norma de Información Financiera NIF A-2: Postulado Básico de Sustancia Económica y Criterio Judicial de Materialidad de Operaciones.**
> 
> 1. **Postulado de Sustancia Económica**: La sustancia económica debe prevalecer en la delimitación y operación del sistema de información financiera, así como en el reconocimiento contable de las transacciones, transformaciones internas y otros eventos que afectan económicamente a una entidad. El cumplimiento de formalidades legales no es suficiente para otorgar validez fiscal a una erogación si la sustancia económica real difiere de la forma jurídica adoptada.
> 
> 2. **Carga Probatoria de la Materialidad (Tesis Jurisprudencial 2a./J. 78/2019)**: La exhibición del CFDI y del comprobante de transferencia bancaria no acredita fehacientemente que la operación se haya ejecutado. Para superar el test pericial de materialidad ante el SAT y el Tribunal Federal de Justicia Administrativa (TFJA), el contribuyente debe exhibir la **Tríada Probatoria Forense**:
>    - **I. Contratos con Fecha Cierta**: Documentos mercantiles dotados de eficacia probatoria formal mediante certificación notarial, inscripción ante el Registro Público de la Propiedad y del Comercio, o firma electrónica avanzada acompañada de Constancia de Conservación de Mensajes de Datos bajo la Norma Oficial Mexicana NOM-151-SCFI-2016.
>    - **II. Entregables Contemporáneos y Verificables**: Evidencia técnica, tangible e inequívoca del servicio contratado o bien adquirido, incluyendo: bitácoras georreferenciadas con firmas de responsables, órdenes de compra y cotizaciones comparativas, planos y especificaciones técnicas de ingeniería, minutas de reuniones de trabajo, commits y repositorios de código fuente con firmas PGP, reportes de recepción de mercancía y Cartas Porte (CFDI de traslado con complemento de Carta Porte) emitidas por transportistas certificados.
>    - **III. Trazabilidad Financiera y Capacidad Instalada**: Conciliación bancaria íntegra que evidencie el flujo económico directo y libre de esquemas circulares de retorno de fondos (*round-tripping*), así como la acreditación de que el proveedor disponía de trabajadores registrados en el Instituto Mexicano del Seguro Social (cédula SUA/IMSS), instalaciones físicas arrendadas o propias idóneas, y activos fijos suficientes para desarrollar la prestación pactada.

---

### 5.3 Precedent 3: UIF - Reporte de Operación Inusual (ROI)
- **Article Code**: `UIF-ROI-24H`
- **Law Name**: `Disposiciones UIF / LFPIORPI / Recomendación 20 GAFI`
- **Full Authoritative Text**:
> **Disposiciones de Carácter General Relativas a Operaciones Inusuales y Prevención de Lavado de Dinero (UIF - SHCP).**
> 
> 1. **Definición de Operación Inusual**: Aquella operación, actividad, conducta o comportamiento realizado por un cliente o usuario que no concuerde con sus antecedentes o actividades conocidas o declaradas, o con su perfil transaccional inicial en función al monto, frecuencia, tipo o naturaleza de la operación, sin que exista una justificación económica o jurídica razonable para su realización, o bien, aquella que involucre tipologías reconocidas de estratificación o triangulación financiera.
> 
> 2. **Plazo Fatal de Presentación**: Las entidades financieras sujetas a la supervisión de la CNBV y de la Unidad de Inteligencia Financiera (UIF) deben remitir el **Reporte de Operación Inusual (ROI) en un plazo que no exceda de veinticuatro (24) a cuarenta y ocho (48) horas** contadas a partir de que el Comité de Comunicación y Control, o el Oficial de Cumplimiento de la institución, dictamine la inusualidad de la transacción.
> 
> 3. **Tipologías Subyacentes en Grafos Transaccionales**:
>    - Cuentas de paso rápido (*pass-through mule accounts*) donde la captación y dispersión presentan un coeficiente de conservación mayor o igual al 90% dentro de ventanas temporales inferiores a 48 horas.
>    - Estructuración circular (*circular flow layering*) donde los recursos retornan a la entidad de origen o a partes relacionadas mediante ciclos de 2 a 5 saltos intermedios.
>    - Smurfing (*pitufeo*) y fragmentación premeditada de transferencias para eludir los límites automáticos de vigilancia.
> 
> 4. **Prohibición Estricta de Alertamiento (*Tipping-Off Prohibition*)**: Conforme a la Recomendación 20 del Grupo de Acción Financiera Internacional (GAFI/FATF), las instituciones de crédito, sus directores, funcionarios y empleados tienen estrictamente prohibido revelar al cliente, a intermediarios o a terceros el hecho de que se ha remitido o se remitirá un ROI a la UIF, so pena de responsabilidades penales y cancelación de licencias de operación.

---

### 5.4 Precedent 4: UIF - Reporte de Operación Relevante (ROR)
- **Article Code**: `UIF-ROR-7500USD`
- **Law Name**: `Disposiciones de Carácter General Aplicables a Instituciones de Crédito`
- **Full Authoritative Text**:
> **Reporte de Operaciones Relevantes (ROR) ante la Unidad de Inteligencia Financiera.**
> 
> 1. **Umbral Obligatorio de Reporte**: Toda operación realizada con billetes y monedas metálicas de curso legal en los Estados Unidos Mexicanos o en cualquier otra jurisdicción, así como con cheques de viajero y monedas acuñadas en platino, oro y plata, por un **monto igual o superior al equivalente en moneda nacional a siete mil quinientos dólares de los Estados Unidos de América ($7,500 USD)**, debe ser reportada trimestralmente de manera obligatoria y automatizada a la UIF.
> 
> 2. **Acumulación y Fraccionamiento Premeditado**: Cuando diversas operaciones realizadas en beneficio de un mismo titular o por una misma cuenta en un periodo de hasta treinta (30) días naturales sumen un importe acumulado igual o superior a $7,500 USD, y los montos individuales se hayan estructurado artificialmente justo por debajo del límite regulatorio, la entidad bancaria tiene la obligación inmediata de reclasificar el conjunto transaccional como una **Operación Inusual**, detonando la emisión urgente de un ROI dentro de las 24 horas siguientes.

---

### 5.5 Precedent 5: Ley de Instituciones de Crédito Art. 115 (Lista de Personas Bloqueadas)
- **Article Code**: `LIC-ART-115-BLOQUEO`
- **Law Name**: `Ley de Instituciones de Crédito (Artículo 115)`
- **Full Authoritative Text**:
> **Artículo 115 de la Ley de Instituciones de Crédito: Medidas Cautelares de Inmovilización de Fondos y Lista de Personas Bloqueadas (LPB).**
> 
> 1. **Facultades de Inmovilización de la UIF**: La Secretaría de Hacienda y Crédito Público, por conducto de la Unidad de Inteligencia Financiera (UIF), tiene atribuciones para introducir a personas físicas o morales en la **Lista de Personas Bloqueadas (LPB)** con el objeto de prevenir e interrumpir el uso del sistema financiero mexicano para la comisión de delitos de operaciones con recursos de procedencia ilícita (lavado de dinero) o financiamiento al terrorismo.
> 
> 2. **Efectos Inmediatos del Bloqueo**: Al notificarse formalmente la inclusión en la LPB a través de la Comisión Nacional Bancaria y de Valores (CNBV), las instituciones de crédito deben suspender de manera inmediata la apertura de nuevas cuentas, cancelar el acceso a plataformas de banca electrónica (SPEI), e inmovilizar todos los saldos líquidos existentes, absteniéndose de ejecutar cualquier orden de débito, transferencia o dispersión de fondos solicitada por el titular o sus apoderados legales.
> 
> 3. **Garantías Constitucionales y Estándar Judicial**: De conformidad con la jurisprudencia 2a./J. 46/2018 emitida por la Segunda Sala de la Suprema Corte de Justicia de la Nación, el bloqueo administrativo cautelar únicamente es constitucionalmente válido sin orden judicial previa cuando emane del cumplimiento estricto de una solicitud o compromiso de colaboración internacional derivado de tratados bilaterales o multilaterales (e.g. resoluciones del Consejo de Seguridad de la ONU o solicitudes directas de agencias homólogas extranjeras como FinCEN).

---

### 5.6 Precedent 6: Código Penal Federal Art. 400 Bis (Lavado de Dinero)
- **Article Code**: `CPF-ART-400BIS`
- **Law Name**: `Código Penal Federal (Artículo 400 Bis)`
- **Full Authoritative Text**:
> **Artículo 400 Bis del Código Penal Federal: Tipificación del Delito de Operaciones con Recursos de Procedencia Ilícita (Lavado de Dinero).**
> 
> 1. **Tipo Penal Básico**: Se impondrá de cinco (5) a quince (15) años de prisión y de mil a cinco mil días de multa a quien por sí o por interpósita persona adquiera, enajene, administre, custodie, posea, cambie, convierta, deposite, retire, dé o reciba por cualquier motivo, invierta, traspase, transporte o transfiera, dentro del territorio nacional, de éste al extranjero o a la inversa, recursos, derechos o bienes de cualquier naturaleza, cuando tenga conocimiento de que proceden o representan el producto de una actividad ilícita.
> 
> 2. **Presunción de Ilicitud**: Se entenderá que los recursos, derechos o bienes proceden o representan el producto de una actividad ilícita cuando existan indicios fundados o certeza de que provienen directa o indirectamente, o representan las ganancias derivadas de la comisión de algún delito y no pueda acreditarse su legítima procedencia económica o jurídica.
> 
> 3. **Concurso con Delitos Fiscales (Art. 108 CFF)**: La adquisición o enajenación sistemática de comprobantes fiscales falsos o inexistentes (esquema EFOS/EDOS) que resulte en una defraudación fiscal superior a los montos agravados tipificados en el Artículo 108 del Código Fiscal de la Federación se persigue de forma autónoma y concurrente como delito de lavado de dinero, con penas agravadas en hasta una mitad cuando participen apoderados de instituciones que componen el sistema financiero.

---

### 5.7 Precedent Vector Generation Specification
To ensure deterministic testing and zero external API dependencies during offline verification, Worker M1 will implement a deterministic 1536-dimensional unit vector generation function:

```python
import hashlib
import math
from typing import List


def generate_deterministic_embedding(text: str, dim: int = 1536) -> List[float]:
    """
    Generates a deterministic, reproducible, unit-normalized vector embedding
    of length `dim` (default 1536) derived from the SHA-256 hash of the input text.
    Satisfies Euclidean unit norm (sum(x_i^2) == 1.0) for cosine distance (<=>).
    """
    values: List[float] = []
    current_seed = text.encode("utf-8")
    
    while len(values) < dim:
        digest = hashlib.sha256(current_seed).digest()
        for i in range(0, len(digest), 4):
            if len(values) >= dim:
                break
            # Convert 4 bytes to signed integer and normalize to [-1.0, 1.0]
            val = int.from_bytes(digest[i : i + 4], byteorder="little", signed=True)
            normalized_val = val / 2147483648.0
            values.append(normalized_val)
        current_seed = digest

    # Normalize vector to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in values)) or 1.0
    return [round(x / norm, 6) for x in values]
```

---

## 6. Authoritative Specification for `backend/core/database.py`

### 6.1 Requirements
1. Connect to TigerData PostgreSQL using async SQLAlchemy 2.0.
2. Accept `DATABASE_URL` supporting both `postgresql+asyncpg` and `postgresql+psycopg`.
3. Normalize legacy schemes (e.g. `postgres://` or `postgresql://` -> `postgresql+asyncpg://`).
4. Enforce SSL encrypted transport (`sslmode=require` / `connect_args={"ssl": "require"}`).
5. Configure pooling: `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`.
6. Provide managed `get_db()` dependency generator with transactional context and auto-rollback.
7. Provide lifecycle hooks `init_db()` (extension creation, table schema setup, seed data upsert) and `close_db()`.

### 6.2 Recommended Engine & Session Architecture
```python
import logging
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy import text

from backend.core.config import settings
from backend.models.forensic import Base, LegalArticleVector, SEED_LEGAL_PRECEDENTS

logger = logging.getLogger("forensic_auditor.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_database_url(raw_url: str) -> tuple[str, dict]:
    """
    Normalizes a database URL to ensure async driver compatibility and SSL enforcement.
    Returns (cleaned_url, connect_args).
    """
    if not raw_url:
        return "", {}

    # Support SQLite memory or file URLs directly for testing
    if raw_url.startswith("sqlite"):
        return raw_url, {}

    parsed = urlparse(raw_url)
    scheme = parsed.scheme

    # Normalize scheme to asyncpg
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+psycopg2":
        scheme = "postgresql+psycopg"

    # Extract query params
    query_params = parse_qs(parsed.query)
    connect_args = {}

    # AsyncPG expects ssl="require" in connect_args, not sslmode query param
    if "asyncpg" in scheme:
        if "sslmode" in query_params:
            mode = query_params.pop("sslmode")[0]
            if mode in ("require", "verify-ca", "verify-full"):
                connect_args["ssl"] = mode
        elif "ssl" in query_params:
            connect_args["ssl"] = query_params.pop("ssl")[0]
        else:
            connect_args["ssl"] = "require"

    new_query = urlencode(query_params, doseq=True)
    normalized_url = urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))

    return normalized_url, connect_args


def get_engine() -> AsyncEngine:
    """Returns or creates the singleton AsyncEngine instance."""
    global _engine, _session_factory
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. Please set the DATABASE_URL "
                "environment variable or configure it in .env"
            )

        db_url, connect_args = normalize_database_url(settings.DATABASE_URL)
        
        # SQLite engines do not accept pool_size or max_overflow
        if "sqlite" in db_url:
            _engine = create_async_engine(db_url, echo=settings.DB_ECHO)
        else:
            _engine = create_async_engine(
                db_url,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
                pool_recycle=settings.DB_POOL_RECYCLE,
                connect_args=connect_args,
            )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the async sessionmaker factory."""
    if _session_factory is None:
        get_engine()
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding a transactional AsyncSession.
    Automatically rolls back on exception and closes when completed.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initializes database schema, creates pgvector extension if on PostgreSQL,
    and populates seed legal precedent articles idempotently.
    """
    engine = get_engine()

    async with engine.begin() as conn:
        # Enable pgvector extension if PostgreSQL
        if engine.dialect.name == "postgresql":
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as e:
                logger.warning(f"Failed to enable vector extension: {e}")
        
        # Create all registered tables
        await conn.run_sync(Base.metadata.create_all)

    # Seed legal precedents
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        for item in SEED_LEGAL_PRECEDENTS:
            stmt = select(LegalArticleVector).where(
                LegalArticleVector.article_code == item["article_code"]
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing is None:
                article = LegalArticleVector(
                    article_code=item["article_code"],
                    law_name=item["law_name"],
                    content=item["content"],
                    embedding=item.get("embedding"),
                )
                session.add(article)
        await session.commit()
    logger.info("Database schema initialized and seed precedents verified.")


async def close_db() -> None:
    """Disposes of the database engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine connection pool disposed.")
```

---

## 7. Recommended Settings & Dependencies

### 7.1 `backend/core/config.py` Additions
```python
    # Database Settings
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False
```

### 7.2 `backend/requirements.txt` Additions
```txt
sqlalchemy[asyncio]>=2.0.28
asyncpg>=0.29.0
psycopg[binary]>=3.1.18
pgvector>=0.2.5
aiosqlite>=0.20.0
greenlet>=3.0.3
```

---

## 8. Milestone 1 Worker Implementation Checklist
The assigned Worker implementing Milestone 1 should execute the following sequence:

1. **Update `backend/requirements.txt`**: Add `sqlalchemy[asyncio]`, `asyncpg`, `psycopg[binary]`, `pgvector`, `aiosqlite`, `greenlet`.
2. **Update `backend/core/config.py`**: Add database configuration parameters (`DATABASE_URL`, pool settings).
3. **Implement `backend/models/forensic.py`**:
   - Create `Base`, SQLite compatibility compilers for `Vector` and `JSONB`.
   - Implement `InvestigationCase`, `TransactionRecord`, `LegalArticleVector`.
   - Implement `generate_deterministic_embedding`.
   - Define `SEED_LEGAL_PRECEDENTS` with the 6 authoritative precedents.
4. **Implement `backend/core/database.py`**:
   - Implement `normalize_database_url`, `get_engine`, `get_session_factory`, `get_db`, `init_db`, `close_db`.
5. **Update `backend/main.py`**:
   - In `lifespan`: call `await init_db()` if `settings.DATABASE_URL` is set, and `await close_db()` in teardown.
6. **Implement Unit Tests in `backend/tests/test_database.py`**:
   - Test async engine creation with SQLite in-memory fixture.
   - Test model CRUD operations for `InvestigationCase` and `TransactionRecord`.
   - Verify cascade deletion behavior.
   - Test `LegalArticleVector` creation and seed precedent presence.
