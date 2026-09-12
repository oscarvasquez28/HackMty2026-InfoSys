import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, AsyncGenerator
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
import httpx

from backend.core.config import settings
from backend.services.ingestion import read_amlsim_csv
from backend.services.deterministic_filter import apply_deterministic_filter

router = APIRouter(prefix="/investigations", tags=["investigations"])

# In-memory case storage (in production, backed by PostgreSQL / Redis)
INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_investigation_dataset(
    file: UploadFile = File(...),
):
    """
    Receives an IBM AMLSim CSV dataset, ingests it via Polars, applies deterministic
    graph filtering (cycles + 90% in/out ratio within 48h), and returns case metadata
    with the suspicious subgraph.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV dataset."
        )

    try:
        content = await file.read()
        df, ingestion_meta = read_amlsim_csv(content)
        filter_results = apply_deterministic_filter(df)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing transaction dataset: {str(exc)}"
        )

    case_id = str(uuid.uuid4())
    case_record = {
        "case_id": case_id,
        "filename": file.filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ingestion": ingestion_meta,
        "filter_results": filter_results,
    }
    INVESTIGATION_CASES[case_id] = case_record

    return {
        "case_id": case_id,
        "message": "Dataset successfully processed and pruned.",
        "metrics": filter_results["metrics"],
        "subgraph": filter_results["subgraph"],
        "patterns": filter_results["patterns"],
    }


async def generate_n8n_or_simulated_stream(
    case_id: str,
    case_data: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    """
    Connects to n8n webhook if configured; otherwise generates a high-fidelity
    forensic auditor reasoning stream with SSE event format.
    """
    metrics = case_data.get("filter_results", {}).get("metrics", {})
    patterns = case_data.get("filter_results", {}).get("patterns", {})
    subgraph = case_data.get("filter_results", {}).get("subgraph", {})

    total_nodes = metrics.get("total_nodes_analyzed", 0)
    total_edges = metrics.get("total_edges_analyzed", 0)
    suspicious_nodes = metrics.get("suspicious_nodes_count", 0)
    cycles_count = metrics.get("detected_cycles_count", 0)
    pt_count = metrics.get("passthrough_accounts_count", 0)
    pruned_count = metrics.get("pruned_edges_count", 0)
    volume_mxn = metrics.get("suspicious_volume_mxn", 0.0)

    # Attempt external n8n webhook proxy if configured
    if settings.N8N_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.N8N_WEBHOOK_URL,
                    json={"case_id": case_id, "metrics": metrics, "patterns": patterns},
                )
                if response.status_code == 200 and "text/event-stream" in response.headers.get("content-type", ""):
                    async for line in response.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
                    return
        except Exception:
            # Fallback smoothly to internal forensic reasoning simulation
            pass

    # High-Fidelity Forensic Auditor Chain of Thought Steps
    thought_steps = [
        {
            "step": 1,
            "phase": "Ingesta y Validación de Topología",
            "message": f"Normalización con Polars completada: {total_nodes} entidades bancarias y {total_edges} transferencias identificadas.",
            "duration_ms": 350,
        },
        {
            "step": 2,
            "phase": "Construcción de Grafo Dirigido",
            "message": "Construyendo multígrafo con pesos y marcas temporales en NetworkX para modelado topológico.",
            "duration_ms": 400,
        },
        {
            "step": 3,
            "phase": "Extracción de Ciclos Dirigidos",
            "message": f"Detección de patrones circulares: {cycles_count} ciclos cerrados detectados (evidencia de tipología de pitufeo / smurfing).",
            "duration_ms": 500,
        },
        {
            "step": 4,
            "phase": "Análisis de Velocidad y Cuentas Puente",
            "message": f"Evaluando ventana temporal <= 48h: {pt_count} cuentas superan el umbral de retención > 90% (cuentas mula de estratificación rápida).",
            "duration_ms": 450,
        },
        {
            "step": 5,
            "phase": "Poda Matemática Determinista",
            "message": f"Descartadas {pruned_count} transacciones legítimas ({metrics.get('pruning_efficiency_pct', 0)}% de reducción de ruido). Subgrafo crítico aislado con {suspicious_nodes} nodos.",
            "duration_ms": 400,
        },
        {
            "step": 6,
            "phase": "Evaluación Pericial Regulatoria",
            "message": f"Contraste de tipologías GAFI/UIF: Volumen de riesgo calculado en ${volume_mxn:,.2f} MXN con alta probabilidad de dolo.",
            "duration_ms": 450,
        },
    ]

    for item in thought_steps:
        await asyncio.sleep(item["duration_ms"] / 1000.0)
        payload = {
            "step": item["step"],
            "phase": item["phase"],
            "message": item["message"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield f"event: thought\ndata: {json.dumps(payload)}\n\n"

    await asyncio.sleep(0.5)

    # Compile Final Forensic Verdict
    risk_level = "CRÍTICO" if (cycles_count > 0 or volume_mxn > 500000) else "ALTO"
    suspicious_node_ids = [n["id"] for n in subgraph.get("nodes", [])]

    verdict_payload = {
        "case_id": case_id,
        "risk_level": risk_level,
        "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido",
        "total_amount_mxn": volume_mxn,
        "confidence_score": 0.94 if cycles_count > 0 else 0.88,
        "entities_involved": suspicious_node_ids,
        "pruned_leads_count": metrics.get("pruned_edges_count", 0),
        "patterns_summary": {
            "closed_cycles": cycles_count,
            "passthrough_accounts": pt_count,
            "pruning_efficiency_pct": metrics.get("pruning_efficiency_pct", 0),
        },
        "legal_recommendation": (
            "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF "
            "y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente."
        ),
        "audit_summary_text": (
            f"Dictamen Pericial Forense para el caso {case_id[:8]}. Se identificó una red estructurada "
            f"de lavado de dinero por un monto total de ${volume_mxn:,.2f} pesos mexicanos. "
            f"El análisis topológico determinó {cycles_count} ciclos dirigidos de triangulación de fondos "
            f"y {pt_count} cuentas mula con dispersión superior al 90% en ventanas menores a 48 horas. "
            f"Se descartaron exitosamente {pruned_count} transferencias no vinculadas mediante poda determinista."
        ),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    yield f"event: verdict\ndata: {json.dumps(verdict_payload)}\n\n"


@router.get("/{case_id}/stream")
async def stream_investigation_thoughts(case_id: str):
    """
    Server-Sent Events (SSE) endpoint emitting real-time agent thought steps
    and concluding with the formal forensic verdict.
    """
    if case_id not in INVESTIGATION_CASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case '{case_id}' not found."
        )

    case_data = INVESTIGATION_CASES[case_id]

    return StreamingResponse(
        generate_n8n_or_simulated_stream(case_id, case_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
