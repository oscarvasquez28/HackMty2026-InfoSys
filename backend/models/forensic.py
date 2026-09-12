import hashlib
import math
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
