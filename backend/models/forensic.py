import csv
import hashlib
import math
import os
from pathlib import Path
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# -----------------------------------------------------------------------------
# Base & SQLite Test Compatibility Compilers
# -----------------------------------------------------------------------------
class Base(AsyncAttrs, DeclarativeBase):
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


# -----------------------------------------------------------------------------
# ORM Models
# -----------------------------------------------------------------------------
class InvestigationCase(Base):
    """
    Represents an AML investigation case created from uploaded transaction datasets.
    Stores lifecycle status, graph metrics, isolated subgraphs, and forensic verdict.
    """
    __tablename__ = "investigation_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ingestion_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    subgraph: Mapped[Dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    patterns: Mapped[Dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    verdict: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=True, default=None
    )

    transactions: Mapped[List["TransactionRecord"]] = relationship(
        "TransactionRecord",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TransactionRecord(Base):
    """
    Individual financial transactions extracted from datasets.
    Relational linkage to InvestigationCase with rapid index scanning on origin, destination,
    and suspicion flags.
    """
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("investigation_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_suspicious: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, nullable=False
    )
    reasons: Mapped[List[str]] = mapped_column(JSON_DOCUMENT, default=list, nullable=False)

    case: Mapped["InvestigationCase"] = relationship(
        "InvestigationCase", back_populates="transactions"
    )


class LegalArticleVector(Base):
    """
    Knowledge base repository storing Mexican AML, tax, and banking jurisprudence.
    Indexed with pgvector HNSW cosine approximate nearest neighbor index.
    """
    __tablename__ = "legal_knowledge_vectors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    article_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    law_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)

    __table_args__ = (
        Index(
            "idx_legal_vectors_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class AccountRecord(Base):
    """
    Bank account records with KYC owner details, branch, deposits, and status.
    Mapped from accounts.csv.
    """
    __tablename__ = "accounts"

    acct_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    dsply_nm: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    acct_stat: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    acct_rptng_crncy: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default="USD")
    prior_sar_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    branch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    open_dt: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    close_dt: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    initial_deposit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    tx_behavior_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bank_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    street_addr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    zip: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    birth_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ssn: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    lon: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)


class AccountMappingRecord(Base):
    """
    Mapping relationships linking account identifiers to customer/party IDs.
    Mapped from accountMapping.csv.
    """
    __tablename__ = "account_mappings"

    cust_acct_mapping_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    acct_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cust_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cust_acct_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default="Primary")
    src_sys: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    data_dump_dt: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class PartyRecord(Base):
    """
    Customer / entity identity records for individuals and organizations.
    Mapped from individuals-bulkload.csv and organizations-bulkload.csv.
    """
    __tablename__ = "parties"

    party_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    party_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Individual")
    is_individual: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name_alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    birth_place_country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country_of_residency: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country_of_incorporation: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    organization_symbol: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_of_income: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=True)
    listed_company: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    work_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cell_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    alternate_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    home_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    personal_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    work_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    company_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    alternate_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    death_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class CashTransactionRecord(Base):
    """
    Cash transactions (ATM deposits and withdrawals/cashouts).
    Mapped from cash_tx.csv.
    """
    __tablename__ = "cash_transactions"

    tran_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    bene_acct: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tx_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="CASH-OUT")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_sar: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON_DOCUMENT, default=dict, nullable=False)



# -----------------------------------------------------------------------------
# Deterministic Embedding Generator & Mexican AML Jurisprudence Precedents
# -----------------------------------------------------------------------------
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
            val = int.from_bytes(digest[i : i + 4], byteorder="little", signed=True)
            normalized_val = val / 2147483648.0
            values.append(normalized_val)
        current_seed = digest

    norm = math.sqrt(sum(x * x for x in values)) or 1.0
    return [round(x / norm, 6) for x in values]


SEED_LEGAL_PRECEDENTS: List[Dict[str, Any]] = [
    {
        "article_code": "CFF-ART-69B",
        "law_name": "Código Fiscal de la Federación (Artículo 69-B)",
        "content": (
            "Artículo 69-B del Código Fiscal de la Federación: Presunción de Inexistencia de Operaciones "
            "Amparadas con Comprobantes Fiscales Digitales (CFDI).\n\n"
            "1. Presunción de Inexistencia: Cuando la autoridad fiscal (SAT) detecte que un contribuyente ha estado "
            "emitiendo comprobantes sin contar con los activos, personal, infraestructura o capacidad material, directa o "
            "indirectamente, para prestar los servicios o producir, comercializar o entregar los bienes que amparan tales "
            "comprobantes, o bien, que dicha persona no se encuentre localizable en su domicilio fiscal, se presumirá la "
            "inexistencia de las operaciones amparadas en tales comprobantes.\n\n"
            "2. Diferenciación Dogmática: EFOS vs. EDOS:\n"
            "- EFOS (Empresas que Facturan Operaciones Simuladas): Entidades emisoras que comercializan facturas sin "
            "sustento material para generar deducciones indebidas a terceros ('empresas fantasma' o 'factureras'). En el grafo "
            "transaccional, operan típicamente como nodos puente de entrada y salida con dispersión casi total de recursos y "
            "retención nula de valor.\n"
            "- EDOS (Empresas que Deducen Operaciones Simuladas): Contribuyentes que adquieren o incorporan dichos CFDI en su "
            "contabilidad para erosionar la base gravable del Impuesto Sobre la Renta (ISR) y solicitar saldos a favor o "
            "acreditamientos improcedentes de IVA.\n\n"
            "3. Plazos Procedimentales de Desvirtuación:\n"
            "- Publicación Provisional (DOF y Portal SAT): Los contribuyentes notificados cuentan con un plazo perentorio de "
            "quince (15) días hábiles, contados a partir de la última de las notificaciones, para comparecer y presentar pruebas y "
            "alegatos que desvirtúen la presunción de inexistencia. Podrán solicitar una prórroga improrrogable de diez (10) días "
            "adicionales.\n"
            "- Publicación Definitiva: Si el contribuyente no comparece o no acredita su capacidad material y operativa, el SAT "
            "publicará la lista definitiva en el Diario Oficial de la Federación. La resolución definitiva produce la nulidad de pleno "
            "derecho de todos los comprobantes emitidos, eliminando cualquier efecto fiscal.\n\n"
            "4. Plazo de Regularización de Terceros (EDOS):\n"
            "Las personas físicas o morales que hayan dado efectos fiscales a los comprobantes emitidos por un EFOS definitivo "
            "cuentan con treinta (30) días hábiles siguientes a la publicación del listado definitivo en el DOF para acreditar ante "
            "el SAT la materialidad real de las operaciones o, en su defecto, corregir su situación fiscal mediante la reversión de "
            "deducciones y pago de contribuciones omitidas con actualizaciones y recargos, previo al inicio del ejercicio de facultades "
            "de comprobación y consignación por delito de defraudación fiscal calificada (Art. 108 CFF)."
        ),
    },
    {
        "article_code": "NIF-A2-MATERIALIDAD",
        "law_name": "Normas de Información Financiera (CINIF) / Tesis SCJN 2a./J. 78/2019",
        "content": (
            "Norma de Información Financiera NIF A-2: Postulado Básico de Sustancia Económica y Criterio Judicial de Materialidad "
            "de Operaciones.\n\n"
            "1. Postulado de Sustancia Económica: La sustancia económica debe prevalecer en la delimitación y operación del sistema de "
            "información financiera, así como en el reconocimiento contable de las transacciones, transformaciones internas y otros "
            "eventos que afectan económicamente a una entidad. El cumplimiento de formalidades legales no es suficiente para otorgar "
            "validez fiscal a una erogación si la sustancia económica real difiere de la forma jurídica adoptada.\n\n"
            "2. Carga Probatoria de la Materialidad (Tesis Jurisprudencial 2a./J. 78/2019): La exhibición del CFDI y del comprobante "
            "de transferencia bancaria no acredita fehacientemente que la operación se haya ejecutado. Para superar el test pericial de "
            "materialidad ante el SAT y el Tribunal Federal de Justicia Administrativa (TFJA), el contribuyente debe exhibir la Tríada "
            "Probatoria Forense:\n"
            "- I. Contratos con Fecha Cierta: Documentos mercantiles dotados de eficacia probatoria formal mediante certificación "
            "notarial, inscripción ante el Registro Público de la Propiedad y del Comercio, o firma electrónica avanzada acompañada "
            "de Constancia de Conservación de Mensajes de Datos bajo la Norma Oficial Mexicana NOM-151-SCFI-2016.\n"
            "- II. Entregables Contemporáneos y Verificables: Evidencia técnica, tangible e inequívoca del servicio contratado o bien "
            "adquirido, incluyendo bitácoras georreferenciadas con firmas de responsables, órdenes de compra y cotizaciones comparativas, "
            "planos y especificaciones técnicas de ingeniería, minutas de reuniones de trabajo, commits y repositorios de código fuente con "
            "firmas PGP, reportes de recepción de mercancía y Cartas Porte (CFDI de traslado con complemento Carta Porte) emitidas por transportistas certificados.\n"
            "- III. Trazabilidad Financiera y Capacidad Instalada: Conciliación bancaria íntegra que evidencie el flujo económico directo y "
            "libre de esquemas circulares de retorno de fondos (round-tripping), así como la acreditación de que el proveedor disponía de "
            "trabajadores registrados en el Instituto Mexicano del Seguro Social (cédula SUA/IMSS), instalaciones físicas arrendadas o propias "
            "idóneas, y activos fijos suficientes para desarrollar la prestación pactada."
        ),
    },
    {
        "article_code": "UIF-ROI-24H",
        "law_name": "Disposiciones UIF / LFPIORPI / Recomendación 20 GAFI",
        "content": (
            "Disposiciones de Carácter General Relativas a Operaciones Inusuales y Prevención de Lavado de Dinero (UIF - SHCP).\n\n"
            "1. Definición de Operación Inusual: Aquella operación, actividad, conducta o comportamiento realizado por un cliente o "
            "usuario que no concuerde con sus antecedentes o actividades conocidas o declaradas, o con su perfil transaccional inicial "
            "en función al monto, frecuencia, tipo o naturaleza de la operación, sin que exista una justificación económica o jurídica "
            "razonable para su realización, o bien, aquella que involucre tipologías reconocidas de estratificación o triangulación financiera.\n\n"
            "2. Plazo Fatal de Presentación: Las entidades financieras sujetas a la supervisión de la CNBV y de la Unidad de Inteligencia "
            "Financiera (UIF) deben remitir el Reporte de Operación Inusual (ROI) en un plazo que no exceda de veinticuatro (24) a cuarenta "
            "y ocho (48) horas contadas a partir de que el Comité de Comunicación y Control, o el Oficial de Cumplimiento de la institución, "
            "dictamine la inusualidad de la transacción.\n\n"
            "3. Tipologías Subyacentes en Grafos Transaccionales:\n"
            "- Cuentas de paso rápido (pass-through mule accounts) donde la captación y dispersión presentan un coeficiente de conservación "
            "mayor o igual al 90% dentro de ventanas temporales inferiores a 48 horas.\n"
            "- Estructuración circular (circular flow layering) donde los recursos retornan a la entidad de origen o a partes relacionadas "
            "mediante ciclos de 2 a 5 saltos intermedios.\n"
            "- Smurfing (pitufeo) y fragmentación premeditada de transferencias para eludir los límites automáticos de vigilancia.\n\n"
            "4. Prohibición Estricta de Alertamiento (Tipping-Off Prohibition): Conforme a la Recomendación 20 del Grupo de Acción "
            "Financiera Internacional (GAFI/FATF), las instituciones de crédito, sus directores, funcionarios y empleados tienen "
            "estrictamente prohibido revelar al cliente, a intermediarios o a terceros el hecho de que se ha remitido o se remitirá un "
            "ROI a la UIF, so pena de responsabilidades penales y cancelación de licencias de operación."
        ),
    },
    {
        "article_code": "UIF-ROR-7500USD",
        "law_name": "Disposiciones de Carácter General Aplicables a Instituciones de Crédito",
        "content": (
            "Reporte de Operaciones Relevantes (ROR) ante la Unidad de Inteligencia Financiera.\n\n"
            "1. Umbral Obligatorio de Reporte: Toda operación realizada con billetes y monedas metálicas de curso legal en los Estados "
            "Unidos Mexicanos o en cualquier otra jurisdicción, así como con cheques de viajero y monedas acuñadas en platino, oro y plata, "
            "por un monto igual o superior al equivalente en moneda nacional a siete mil quinientos dólares de los Estados Unidos de América "
            "($7,500 USD), debe ser reportada trimestralmente de manera obligatoria y automatizada a la UIF.\n\n"
            "2. Acumulación y Fraccionamiento Premeditado: Cuando diversas operaciones realizadas en beneficio de un mismo titular o por una "
            "misma cuenta en un periodo de hasta treinta (30) días naturales sumen un importe acumulado igual o superior a $7,500 USD, y los "
            "montos individuales se hayan estructurado artificialmente justo por debajo del límite regulatorio, la entidad bancaria tiene la "
            "obligación inmediata de reclasificar el conjunto transaccional como una Operación Inusual, detonando la emisión urgente de un "
            "ROI dentro de las 24 horas siguientes."
        ),
    },
    {
        "article_code": "LIC-ART-115-BLOQUEO",
        "law_name": "Ley de Instituciones de Crédito (Artículo 115)",
        "content": (
            "Artículo 115 de la Ley de Instituciones de Crédito: Medidas Cautelares de Inmovilización de Fondos y Lista de Personas "
            "Bloqueadas (LPB).\n\n"
            "1. Facultades de Inmovilización de la UIF: La Secretaría de Hacienda y Crédito Público, por conducto de la Unidad de "
            "Inteligencia Financiera (UIF), tiene atribuciones para introducir a personas físicas o morales en la Lista de Personas "
            "Bloqueadas (LPB) con el objeto de prevenir e interrumpir el uso del sistema financiero mexicano para la comisión de delitos "
            "de operaciones con recursos de procedencia ilícita (lavado de dinero) o financiamiento al terrorismo.\n\n"
            "2. Efectos Inmediatos del Bloqueo: Al notificarse formalmente la inclusión en la LPB a través de la Comisión Nacional "
            "Bancaria y de Valores (CNBV), las instituciones de crédito deben suspender de manera inmediata la apertura de nuevas cuentas, "
            "cancelar el acceso a plataformas de banca electrónica (SPEI), e inmovilizar todos los saldos líquidos existentes, absteniéndose "
            "de ejecutar cualquier orden de débito, transferencia o dispersión de fondos solicitada por el titular o sus apoderados legales.\n\n"
            "3. Garantías Constitucionales y Estándar Judicial: De conformidad con la jurisprudencia 2a./J. 46/2018 emitida por la Segunda Sala "
            "de la Suprema Corte de Justicia de la Nación, el bloqueo administrativo cautelar únicamente es constitucionalmente válido sin "
            "orden judicial previa cuando emane del cumplimiento estricto de una solicitud o compromiso de colaboración internacional derivado "
            "de tratados bilaterales o multilaterales (e.g. resoluciones del Consejo de Seguridad de la ONU o solicitudes directas de agencias "
            "homólogas extranjeras como FinCEN)."
        ),
    },
    {
        "article_code": "CPF-ART-400BIS",
        "law_name": "Código Penal Federal (Artículo 400 Bis)",
        "content": (
            "Artículo 400 Bis del Código Penal Federal: Tipificación del Delito de Operaciones con Recursos de Procedencia Ilícita "
            "(Lavado de Dinero).\n\n"
            "1. Tipo Penal Básico: Se impondrá de cinco (5) a quince (15) años de prisión y de mil a cinco mil días de multa a quien por sí "
            "o por interpósita persona adquiera, enajene, administre, custodie, posea, cambie, convierta, deposite, retire, dé o reciba por "
            "cualquier motivo, invierta, traspase, transporte o transfiera, dentro del territorio nacional, de éste al extranjero o a la "
            "inversa, recursos, derechos o bienes de cualquier naturaleza, cuando tenga conocimiento de que proceden o representan el producto "
            "de una actividad ilícita.\n\n"
            "2. Presunción de Ilicitud: Se entenderá que los recursos, derechos o bienes proceden o representan el producto de una actividad "
            "ilícita cuando existan indicios fundados o certeza de que provienen directa o indirectamente, o representan las ganancias "
            "derivadas de la comisión de algún delito y no pueda acreditarse su legítima procedencia económica o jurídica.\n\n"
            "3. Concurso con Delitos Fiscales (Art. 108 CFF): La adquisición o enajenación sistemática de comprobantes fiscales falsos o "
            "inexistentes (esquema EFOS/EDOS) que resulte en una defraudación fiscal superior a los montos agravados tipificados en el "
            "Artículo 108 del Código Fiscal de la Federación se persigue de forma autónoma y concurrente como delito de lavado de dinero, con "
            "penas agravadas en hasta una mitad cuando participen apoderados de instituciones que componen el sistema financiero."
        ),
    },
]


async def seed_legal_knowledge(session: AsyncSession) -> int:
    """
    Seeds Mexican AML jurisprudence precedents into the legal_knowledge_vectors table.
    Idempotent: updates or skips existing article_code records.
    Returns the count of newly inserted records.
    """
    inserted_count = 0
    for item in SEED_LEGAL_PRECEDENTS:
        stmt = select(LegalArticleVector).where(
            LegalArticleVector.article_code == item["article_code"]
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is None:
            embedding = item.get("embedding")
            if embedding is None:
                embedding = generate_deterministic_embedding(item["content"])
            article = LegalArticleVector(
                article_code=item["article_code"],
                law_name=item["law_name"],
                content=item["content"],
                embedding=embedding,
            )
            session.add(article)
            inserted_count += 1
    if inserted_count > 0:
        await session.commit()
    return inserted_count


# -----------------------------------------------------------------------------
# Banking Data Repository & Initialization (Accounts, Mappings, Parties, Cash)
# -----------------------------------------------------------------------------
IN_MEMORY_BANKING_DATA: Dict[str, Any] = {
    "accounts": {},           # acct_id (str) -> dict
    "account_mappings": [],   # list of dicts
    "parties": {},            # party_id (str) -> dict
    "cash_transactions": [],  # list of dicts
}


def get_sample_data_dir() -> Path:
    """Discovers the directory containing sample banking CSVs."""
    candidates = [
        Path("data/sample"),
        Path(__file__).parent.parent.parent / "data" / "sample",
        Path(__file__).parent.parent / "data" / "sample",
        Path("backend/data/sample"),
    ]
    for c in candidates:
        if c.exists() and (c / "accounts.csv").exists():
            return c
    return candidates[0]


def load_in_memory_banking_data(sample_dir: Optional[Path] = None) -> Dict[str, int]:
    """
    Loads banking datasets (accounts, mappings, individuals, organizations, cash)
    into IN_MEMORY_BANKING_DATA for sub-millisecond local queries and fallback execution.
    """
    target_dir = sample_dir or get_sample_data_dir()
    counts = {"accounts": 0, "account_mappings": 0, "parties": 0, "cash_transactions": 0}

    # 1. Accounts
    accts_file = target_dir / "accounts.csv"
    if accts_file.exists():
        with open(accts_file, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                aid = str(row.get("acct_id", "")).strip()
                if not aid:
                    continue
                sar_raw = str(row.get("prior_sar_count", "0")).strip().lower()
                prior_sar = 1 if sar_raw in ("true", "1") else (int(sar_raw) if sar_raw.isdigit() else 0)
                dep_raw = row.get("initial_deposit")
                init_dep = float(dep_raw) if dep_raw and dep_raw != "" else None
                lon_raw = row.get("lon")
                lat_raw = row.get("lat")
                IN_MEMORY_BANKING_DATA["accounts"][aid] = {
                    "acct_id": aid,
                    "dsply_nm": row.get("dsply_nm"),
                    "type": row.get("type"),
                    "acct_stat": row.get("acct_stat"),
                    "acct_rptng_crncy": row.get("acct_rptng_crncy") or "USD",
                    "prior_sar_count": prior_sar,
                    "branch_id": row.get("branch_id"),
                    "open_dt": row.get("open_dt"),
                    "close_dt": row.get("close_dt"),
                    "initial_deposit": init_dep,
                    "tx_behavior_id": row.get("tx_behavior_id"),
                    "bank_id": row.get("bank_id"),
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "street_addr": row.get("street_addr"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "country": row.get("country"),
                    "zip": row.get("zip"),
                    "gender": row.get("gender"),
                    "birth_date": row.get("birth_date"),
                    "ssn": row.get("ssn"),
                    "lon": float(lon_raw) if lon_raw else None,
                    "lat": float(lat_raw) if lat_raw else None,
                }
        counts["accounts"] = len(IN_MEMORY_BANKING_DATA["accounts"])

    # 2. Account Mappings
    mappings_file = target_dir / "accountMapping.csv"
    if mappings_file.exists():
        mappings_list = []
        with open(mappings_file, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                mid = str(row.get("cust_acct_mapping_id", "")).strip()
                aid = str(row.get("acct_id", "")).strip()
                cid = str(row.get("cust_id", "")).strip()
                if not mid or not aid:
                    continue
                mappings_list.append({
                    "cust_acct_mapping_id": mid,
                    "acct_id": aid,
                    "cust_id": cid,
                    "cust_acct_role": row.get("cust_acct_role") or "Primary",
                    "src_sys": row.get("src_sys"),
                    "data_dump_dt": row.get("data_dump_dt"),
                })
        IN_MEMORY_BANKING_DATA["account_mappings"] = mappings_list
        counts["account_mappings"] = len(mappings_list)

    # 3. Individuals & Organizations (Parties)
    indiv_file = target_dir / "individuals-bulkload.csv"
    if indiv_file.exists():
        with open(indiv_file, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("partyId", "")).strip()
                if not pid:
                    continue
                is_act = str(row.get("isActive", "1")).lower() in ("1", "true")
                is_listed = str(row.get("listedCompany", "0")).lower() in ("1", "true")
                IN_MEMORY_BANKING_DATA["parties"][pid] = {
                    "party_id": pid,
                    "party_type": "Individual",
                    "is_individual": True,
                    "first_name": row.get("firstName"),
                    "last_name": row.get("lastName"),
                    "middle_name": row.get("middleName"),
                    "legal_name": row.get("legalName"),
                    "name": row.get("name"),
                    "name_alias": row.get("nameAlias"),
                    "birth_place_country": row.get("birthPlaceCountry"),
                    "country_of_residency": row.get("countryofResidency") or row.get("countryOfResidency"),
                    "country_of_incorporation": None,
                    "nationality": row.get("nationality"),
                    "occupation": row.get("occupation"),
                    "organization_symbol": row.get("organizationSymbol"),
                    "source_of_income": row.get("sourceOfIncome"),
                    "title": row.get("title"),
                    "website": row.get("website"),
                    "gender": row.get("gender"),
                    "marital_status": row.get("maritalStatus"),
                    "is_active": is_act,
                    "listed_company": is_listed,
                    "primary_phone": row.get("primaryPhone"),
                    "work_phone": row.get("workPhone"),
                    "cell_phone": row.get("cellPhone"),
                    "alternate_phone": row.get("alternatePhone"),
                    "home_phone": row.get("homePhone"),
                    "personal_email": row.get("personalEmail"),
                    "work_email": row.get("workEmail"),
                    "company_email": row.get("companyEmail"),
                    "alternate_email": row.get("alternateEmail"),
                    "death_time": row.get("deathTime"),
                }

    org_file = target_dir / "organizations-bulkload.csv"
    if org_file.exists():
        with open(org_file, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                pid = str(row.get("partyId", "")).strip()
                if not pid:
                    continue
                is_act = str(row.get("isActive", "1")).lower() in ("1", "true")
                is_listed = str(row.get("listedCompany", "0")).lower() in ("1", "true")
                IN_MEMORY_BANKING_DATA["parties"][pid] = {
                    "party_id": pid,
                    "party_type": "Organization",
                    "is_individual": False,
                    "first_name": row.get("firstName"),
                    "last_name": row.get("lastName"),
                    "middle_name": row.get("middleName"),
                    "legal_name": row.get("legalName"),
                    "name": row.get("name"),
                    "name_alias": row.get("nameAlias"),
                    "birth_place_country": row.get("birthPlaceCountry"),
                    "country_of_residency": row.get("countryofResidency") or row.get("countryOfResidency"),
                    "country_of_incorporation": row.get("countryOfIncorporation"),
                    "nationality": row.get("nationality"),
                    "occupation": row.get("occupation"),
                    "organization_symbol": row.get("organizationSymbol"),
                    "source_of_income": row.get("sourceOfIncome"),
                    "title": row.get("title"),
                    "website": row.get("website"),
                    "gender": row.get("gender"),
                    "marital_status": row.get("maritalStatus"),
                    "is_active": is_act,
                    "listed_company": is_listed,
                    "primary_phone": row.get("primaryPhone"),
                    "work_phone": row.get("workPhone"),
                    "cell_phone": row.get("cellPhone"),
                    "alternate_phone": row.get("alternatePhone"),
                    "home_phone": row.get("homePhone"),
                    "personal_email": row.get("personalEmail"),
                    "work_email": row.get("workEmail"),
                    "company_email": row.get("companyEmail"),
                    "alternate_email": row.get("alternateEmail"),
                    "death_time": row.get("deathTime"),
                }
    counts["parties"] = len(IN_MEMORY_BANKING_DATA["parties"])

    # 4. Cash Transactions (ATM takeouts and deposits)
    cash_files = [target_dir / "cash_tx.csv", target_dir.parent.parent / "AMLSim" / "sample" / "outputs" / "cash_tx.csv"]
    cash_list = []
    for c_file in cash_files:
        if c_file.exists() and c_file.stat().st_size > 80:
            with open(c_file, "r", encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    tid = str(row.get("TXN_ID") or row.get("tran_id") or "").strip()
                    aid = str(row.get("ACCOUNT_ID") or row.get("orig_acct") or "").strip()
                    if not tid or not aid:
                        continue
                    ttype = str(row.get("TXN_SOURCE_TYPE_CODE") or row.get("tx_type") or "CASH-OUT").strip()
                    amt_val = float(row.get("TXN_AMOUNT_ORIG") or row.get("base_amt") or 0.0)
                    ts = str(row.get("RUN_DATE") or row.get("tran_timestamp") or "")
                    bid = str(row.get("BRANCH_ID") or "")
                    is_sar = str(row.get("is_sar", "0")).lower() in ("1", "true")
                    cash_list.append({
                        "tran_id": tid,
                        "account_id": aid,
                        "bene_acct": row.get("bene_acct"),
                        "tx_type": ttype,
                        "amount": amt_val,
                        "timestamp": ts,
                        "branch_id": bid,
                        "is_sar": is_sar,
                        "alert_id": row.get("alert_id"),
                        "raw_metadata": dict(row),
                    })
            if cash_list:
                break
    IN_MEMORY_BANKING_DATA["cash_transactions"] = cash_list
    counts["cash_transactions"] = len(cash_list)

    return counts


# Automatically load on module import
try:
    load_in_memory_banking_data()
except Exception:
    pass


async def seed_core_banking_data(session: AsyncSession, sample_dir: Optional[Path] = None) -> Dict[str, int]:
    """
    Seeds core banking tables (accounts, account_mappings, parties, cash_transactions)
    from sample CSV files into PostgreSQL / SQLite database tables idempotently.
    Returns counts of newly inserted records per table.
    """
    load_in_memory_banking_data(sample_dir)
    results = {"accounts": 0, "account_mappings": 0, "parties": 0, "cash_transactions": 0}

    # 1. Accounts
    existing_accts = (await session.execute(select(func.count(AccountRecord.acct_id)))).scalar() or 0
    if existing_accts == 0 and IN_MEMORY_BANKING_DATA["accounts"]:
        for aid, data in IN_MEMORY_BANKING_DATA["accounts"].items():
            record = AccountRecord(
                acct_id=data["acct_id"],
                dsply_nm=data["dsply_nm"],
                type=data["type"],
                acct_stat=data["acct_stat"],
                acct_rptng_crncy=data["acct_rptng_crncy"],
                prior_sar_count=data["prior_sar_count"],
                branch_id=data["branch_id"],
                open_dt=data["open_dt"],
                close_dt=data["close_dt"],
                initial_deposit=Decimal(str(data["initial_deposit"])) if data["initial_deposit"] is not None else None,
                tx_behavior_id=data["tx_behavior_id"],
                bank_id=data["bank_id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                street_addr=data["street_addr"],
                city=data["city"],
                state=data["state"],
                country=data["country"],
                zip=data["zip"],
                gender=data["gender"],
                birth_date=data["birth_date"],
                ssn=data["ssn"],
                lon=Decimal(str(data["lon"])) if data["lon"] is not None else None,
                lat=Decimal(str(data["lat"])) if data["lat"] is not None else None,
            )
            session.add(record)
            results["accounts"] += 1

    # 2. Account Mappings
    existing_mappings = (await session.execute(select(func.count(AccountMappingRecord.cust_acct_mapping_id)))).scalar() or 0
    if existing_mappings == 0 and IN_MEMORY_BANKING_DATA["account_mappings"]:
        for data in IN_MEMORY_BANKING_DATA["account_mappings"]:
            record = AccountMappingRecord(
                cust_acct_mapping_id=data["cust_acct_mapping_id"],
                acct_id=data["acct_id"],
                cust_id=data["cust_id"],
                cust_acct_role=data["cust_acct_role"],
                src_sys=data["src_sys"],
                data_dump_dt=data["data_dump_dt"],
            )
            session.add(record)
            results["account_mappings"] += 1

    # 3. Parties
    existing_parties = (await session.execute(select(func.count(PartyRecord.party_id)))).scalar() or 0
    if existing_parties == 0 and IN_MEMORY_BANKING_DATA["parties"]:
        for pid, data in IN_MEMORY_BANKING_DATA["parties"].items():
            record = PartyRecord(
                party_id=data["party_id"],
                party_type=data["party_type"],
                is_individual=data["is_individual"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                middle_name=data["middle_name"],
                legal_name=data["legal_name"],
                name=data["name"],
                name_alias=data["name_alias"],
                birth_place_country=data["birth_place_country"],
                country_of_residency=data["country_of_residency"],
                country_of_incorporation=data["country_of_incorporation"],
                nationality=data["nationality"],
                occupation=data["occupation"],
                organization_symbol=data["organization_symbol"],
                source_of_income=data["source_of_income"],
                title=data["title"],
                website=data["website"],
                gender=data["gender"],
                marital_status=data["marital_status"],
                is_active=data["is_active"],
                listed_company=data["listed_company"],
                primary_phone=data["primary_phone"],
                work_phone=data["work_phone"],
                cell_phone=data["cell_phone"],
                alternate_phone=data["alternate_phone"],
                home_phone=data["home_phone"],
                personal_email=data["personal_email"],
                work_email=data["work_email"],
                company_email=data["company_email"],
                alternate_email=data["alternate_email"],
                death_time=data["death_time"],
            )
            session.add(record)
            results["parties"] += 1

    # 4. Cash Transactions
    existing_cash = (await session.execute(select(func.count(CashTransactionRecord.tran_id)))).scalar() or 0
    if existing_cash == 0 and IN_MEMORY_BANKING_DATA["cash_transactions"]:
        for data in IN_MEMORY_BANKING_DATA["cash_transactions"]:
            record = CashTransactionRecord(
                tran_id=data["tran_id"],
                account_id=data["account_id"],
                bene_acct=data["bene_acct"],
                tx_type=data["tx_type"],
                amount=Decimal(str(data["amount"])),
                timestamp=data["timestamp"],
                branch_id=data["branch_id"],
                is_sar=data["is_sar"],
                alert_id=data["alert_id"],
                raw_metadata=data["raw_metadata"],
            )
            session.add(record)
            results["cash_transactions"] += 1

    total_inserted = sum(results.values())
    if total_inserted > 0:
        await session.commit()

    return results

