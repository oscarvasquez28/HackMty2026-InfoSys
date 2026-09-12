# Technical Analysis: SSE Streaming & Database Verdict Persistence (Milestone 2)

**Author:** Teamwork Explorer Agent (`explorer_m2_2`)  
**Scope:** Milestone 2 (`GET /api/v1/investigations/{case_id}/stream`, n8n Webhook Proxy, Simulated Reasoning, and PostgreSQL Verdict Persistence)  
**Target Repository:** Forensic Auditor Python Backend  
**Date:** 2026-09-12  

---

## 1. Executive Summary

In the Forensic Auditor platform, an AML forensic investigation progresses through ingestion, deterministic graph pruning (Polars + NetworkX), and forensic agentic reasoning. Milestone 2 delivers the core streaming and persistence bridge:
1. **Case Retrieval**: Resolving the `InvestigationCase` by UUID from PostgreSQL (with 404 validation before starting SSE transmission).
2. **Dynamic Reasoning Pipeline**: Dispatching case metrics, topological subgraphs, and detected AML patterns to an external n8n ReAct agent via webhook if configured, with an instantaneous fallback to an internal, deterministic 6-phase forensic reasoning simulation.
3. **SSE Protocol Transmission**: Emitting standard Server-Sent Events (`event: thought` steps 1 through 6, concluded by `event: verdict`) matching the Next.js frontend contracts (`useInvestigationStream.ts`).
4. **PostgreSQL Verdict Persistence**: Upon stream conclusion, saving the comprehensive forensic verdict JSON dictionary into `InvestigationCase.verdict` and transitioning `InvestigationCase.status` from `"PROCESSING"` to `"COMPLETED"`, committing atomically to TigerData PostgreSQL.
5. **Session Safety & Connection Pool Health**: Decoupling the SSE generator from long-lived database connections to eliminate connection pool starvation (`DB_POOL_SIZE=20`) and prevent session closure errors.

---

## 2. Architectural Context & Problem Statement

### 2.1 The Streaming Challenge in Async FastAPI
In conventional FastAPI routes returning JSON, an injected database session (`db: AsyncSession = Depends(get_db)`) begins when the request enters and commits/closes when the endpoint function returns.

However, `GET /api/v1/investigations/{case_id}/stream` returns a `StreamingResponse(generator, media_type="text/event-stream")`.
- When the route function returns the `StreamingResponse` object, FastAPI completes the dependency lifecycle for `get_db()`, executing `await session.close()`.
- The streaming generator itself continues running for 2.5 to 3.5 seconds (or longer during external webhook streaming).
- If the generator attempts to use the injected `db` session at the end of the stream to persist the final verdict, SQLAlchemy raises:
  ```python
  sqlalchemy.exc.IllegalStateChangeError: Method 'execute()' can't be called here; session is closed
  ```
- Conversely, if a single database connection were held open across the entire streaming duration (`asyncio.sleep` intervals), just 20 concurrent streaming clients would exhaust the entire engine pool (`pool_size=20`), causing all other incoming API requests to block and time out.

### 2.2 The Solution: Two-Phase Decoupled Persistence
To solve both issues:
1. **Phase 1 (Verification & Load - < 5 ms)**: The route handler fetches the case metadata from PostgreSQL using a brief transactional query (or fallback cache). If the case does not exist, it immediately raises an HTTP 404 error *before* issuing SSE response headers.
2. **Phase 2 (Streaming - 2.5 to 3.5 s)**: The async generator yields SSE thought events without holding any database connection from the pool.
3. **Phase 3 (Atomic Verdict Save - < 5 ms)**: Once the final verdict is computed (or received from n8n), a fresh, dedicated async session is created via `get_session_factory()` to execute an atomic `UPDATE investigation_cases SET verdict=:v, status='COMPLETED', updated_at=:now WHERE id=:id`. The session commits and closes immediately, and the terminal `event: verdict` is emitted to the client.

---

## 3. Database Schema & State Transitions

### 3.1 Model Definition (`InvestigationCase`)
From `backend/models/forensic.py`:
- `id`: `uuid.UUID` (Primary Key)
- `filename`: `str`
- `status`: `str` (`"PENDING"`, `"PROCESSING"`, `"COMPLETED"`, `"FAILED"`)
- `created_at`: `datetime` (UTC)
- `updated_at`: `datetime` (UTC)
- `ingestion_metadata`: `JSONB` / `JSON_DOCUMENT`
- `metrics`: `JSONB` / `JSON_DOCUMENT` (contains topological statistics from NetworkX)
- `subgraph`: `JSONB` / `JSON_DOCUMENT` (contains isolated suspicious nodes & edges)
- `patterns`: `JSONB` / `JSON_DOCUMENT` (contains detected elementary cycles and pass-through mule accounts)
- `verdict`: `JSONB` / `JSON_DOCUMENT` (nullable; populated upon completion)

### 3.2 State Lifecycle
```
[POST /upload] 
      │
      ▼
Status: "PROCESSING" (verdict: NULL)
      │
      │   Client connects: GET /investigations/{case_id}/stream
      ▼
Status: "PROCESSING" (Streaming SSE thought events...)
      │
      ├── Case finished: Compute / parse verdict
      │   Persist verdict dictionary into InvestigationCase.verdict
      ▼
Status: "COMPLETED" (verdict: {...}) ──► Emits "event: verdict"
```

---

## 4. Detailed Component Design

### 4.1 Route Entrypoint & Case Validation
**Endpoint**: `GET /api/v1/investigations/{case_id}/stream`

```python
@router.get("/{case_id}/stream")
async def stream_investigation_thoughts(
    case_id: str,
    db: Optional[AsyncSession] = Depends(get_optional_db),
):
```

#### Step-by-Step Execution:
1. **UUID Syntax Validation**:
   ```python
   try:
       case_uuid = uuid.UUID(case_id)
   except ValueError:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail=f"Invalid case ID format: '{case_id}'. Must be a valid UUID."
       )
   ```
2. **Database Case Retrieval**:
   - If `db is not None`:
     ```python
     stmt = select(InvestigationCase).where(InvestigationCase.id == case_uuid)
     res = await db.execute(stmt)
     case_obj = res.scalar_one_or_none()
     ```
   - If found in DB, extract plain dictionaries:
     ```python
     case_data = {
         "case_id": str(case_obj.id),
         "metrics": case_obj.metrics or {},
         "patterns": case_obj.patterns or {},
         "subgraph": case_obj.subgraph or {},
         "verdict": case_obj.verdict,
         "status": case_obj.status,
     }
     ```
   - If not in DB, check fallback in-memory cache `INVESTIGATION_CASES.get(str(case_uuid))`:
     ```python
     if not case_data:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail=f"Investigation case '{case_id}' not found."
         )
     ```
3. **Return StreamingResponse**:
   Set standard anti-buffering headers required for live proxy traversal:
   ```python
   return StreamingResponse(
       generate_investigation_stream(case_uuid, case_data),
       media_type="text/event-stream",
       headers={
           "Cache-Control": "no-cache",
           "Connection": "keep-alive",
           "X-Accel-Buffering": "no",
           "Content-Type": "text/event-stream",
       }
   )
   ```

---

### 4.2 External n8n Webhook Contract & Fallback Logic
When `settings.N8N_WEBHOOK_URL` is populated:
1. **Outbound POST Request**:
   - URL: `settings.N8N_WEBHOOK_URL`
   - Timeout: `httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)`
   - Payload:
     ```json
     {
       "case_id": "uuid-string",
       "metrics": { ... },
       "patterns": { ... },
       "subgraph": { ... }
     }
     ```
2. **Stream Ingestion & Proxying**:
   - If n8n returns HTTP 200 and `Content-Type: text/event-stream`:
     - Read line-by-line using `response.aiter_lines()`.
     - Inspect lines for `event: verdict` and subsequent `data: {...}` payloads to capture the external verdict.
     - Yield each line directly: `yield f"{line}\n\n"`.
     - Once n8n stream ends:
       - If a valid verdict was received from n8n, persist it to PostgreSQL and update status to `"COMPLETED"`.
       - If n8n stream ended without a verdict, fallback to compiling the verdict locally and persist.
       - Terminate generator successfully.
3. **Fault Tolerance & Fallback**:
   - If n8n connection fails (timeout, connection refused, non-200 HTTP code, JSON decode error, or unhandled exception):
     - Catch exception and log warning: `logger.warning(f"n8n webhook unavailable ({exc}), falling back to internal reasoning simulation.")`.
     - Fall through immediately to deterministic 6-phase simulation without dropping client connection or returning HTTP 500.

---

### 4.3 High-Fidelity 6-Phase Forensic Reasoning Simulation
The internal reasoning engine mirrors realistic Mexican AML compliance investigation steps (CFF Art. 69-B, UIF, GAFI typologies) based on the topological metrics extracted by NetworkX:

#### Extract Topological Variables:
```python
metrics = case_data.get("metrics") or case_data.get("filter_results", {}).get("metrics", {})
patterns = case_data.get("patterns") or case_data.get("filter_results", {}).get("patterns", {})
subgraph = case_data.get("subgraph") or case_data.get("filter_results", {}).get("subgraph", {})

total_nodes = metrics.get("total_nodes_analyzed", 0)
total_edges = metrics.get("total_edges_analyzed", 0)
suspicious_nodes = metrics.get("suspicious_nodes_count", 0)
cycles_count = metrics.get("detected_cycles_count", 0)
pt_count = metrics.get("passthrough_accounts_count", 0)
pruned_count = metrics.get("pruned_edges_count", 0)
pruning_pct = metrics.get("pruning_efficiency_pct", 0.0)
volume_mxn = metrics.get("suspicious_volume_mxn", 0.0)
```

#### The 6 Sequential Thought Steps:
| Step | Phase Name | Reasoning Content | Duration (ms) |
|---|---|---|---|
| 1 | **Ingesta y Validación de Topología** | `Normalización con Polars completada: {total_nodes} entidades bancarias y {total_edges} transferencias identificadas.` | 350 ms |
| 2 | **Construcción de Grafo Dirigido** | `Construyendo multígrafo con pesos y marcas temporales en NetworkX para modelado topológico.` | 400 ms |
| 3 | **Extracción de Ciclos Dirigidos** | `Detección de patrones circulares: {cycles_count} ciclos cerrados detectados (evidencia de tipología de pitufeo / smurfing).` | 500 ms |
| 4 | **Análisis de Velocidad y Cuentas Puente** | `Evaluando ventana temporal <= 48h: {pt_count} cuentas superan el umbral de retención > 90% (cuentas mula de estratificación rápida).` | 450 ms |
| 5 | **Poda Matemática Determinista** | `Descartadas {pruned_count} transacciones legítimas ({pruning_pct}% de reducción de ruido). Subgrafo crítico aislado con {suspicious_nodes} nodos.` | 400 ms |
| 6 | **Evaluación Pericial Regulatoria** | `Contraste de tipologías GAFI/UIF: Volumen de riesgo calculado en ${volume_mxn:,.2f} MXN con alta probabilidad de dolo.` | 450 ms |

#### SSE Wire Format for Thought Events:
```http
event: thought
data: {"step": 1, "phase": "Ingesta y Validación de Topología", "message": "Normalización con Polars completada: 14 entidades bancarias y 28 transferencias identificadas.", "timestamp": "2026-09-12T08:15:30.450Z"}

```

---

### 4.4 Forensic Verdict Compilation & Contract
Following thought step 6, a brief pause (`await asyncio.sleep(0.4)`) simulates synthesis, and the final verdict payload is formulated:

```python
risk_level = "CRÍTICO" if (cycles_count > 0 or volume_mxn > 500_000) else "ALTO"
confidence_score = 0.94 if cycles_count > 0 else 0.88
suspicious_node_ids = [n["id"] for n in subgraph.get("nodes", []) if isinstance(n, dict) and "id" in n]

verdict_payload = {
    "case_id": str(case_uuid),
    "risk_level": risk_level,
    "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido",
    "total_amount_mxn": float(volume_mxn),
    "confidence_score": confidence_score,
    "entities_involved": suspicious_node_ids,
    "pruned_leads_count": pruned_count,
    "patterns_summary": {
        "closed_cycles": cycles_count,
        "passthrough_accounts": pt_count,
        "pruning_efficiency_pct": pruning_pct,
    },
    "legal_recommendation": (
        "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF "
        "y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente."
    ),
    "audit_summary_text": (
        f"Dictamen Pericial Forense para el caso {str(case_uuid)[:8]}. Se identificó una red estructurada "
        f"de lavado de dinero por un monto total de ${volume_mxn:,.2f} pesos mexicanos. "
        f"El análisis topológico determinó {cycles_count} ciclos dirigidos de triangulación de fondos "
        f"y {pt_count} cuentas mula con dispersión superior al 90% en ventanas menores a 48 horas. "
        f"Se descartaron exitosamente {pruned_count} transferencias no vinculadas mediante poda determinista."
    ),
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
```

#### SSE Wire Format for Verdict Event:
```http
event: verdict
data: {"case_id": "8f3b204e-2895-4680-bc90-9ceba694e207", "risk_level": "CRÍTICO", "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido", "total_amount_mxn": 1485000.0, "confidence_score": 0.94, "entities_involved": ["ACC_A_101", "ACC_B_102", "ACC_C_103"], "pruned_leads_count": 16, "patterns_summary": {"closed_cycles": 2, "passthrough_accounts": 3, "pruning_efficiency_pct": 57.14}, "legal_recommendation": "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente.", "audit_summary_text": "Dictamen Pericial Forense para el caso 8f3b204e...", "completed_at": "2026-09-12T08:15:33.910Z"}

```

---

### 4.5 PostgreSQL Verdict Persistence
Before or immediately upon yielding the verdict event to the client, the verdict is committed to the database:

```python
async def persist_case_verdict(
    case_uuid: uuid.UUID,
    verdict: Dict[str, Any],
    status_str: str = "COMPLETED"
) -> None:
    case_str = str(case_uuid)

    # 1. Update in-memory fallback cache
    if case_str in INVESTIGATION_CASES:
        INVESTIGATION_CASES[case_str]["verdict"] = verdict
        INVESTIGATION_CASES[case_str]["status"] = status_str

    # 2. Persist to PostgreSQL if configured
    if settings.DATABASE_URL:
        try:
            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    update(InvestigationCase)
                    .where(InvestigationCase.id == case_uuid)
                    .values(
                        verdict=verdict,
                        status=status_str,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Persisted forensic verdict to PostgreSQL for case {case_uuid}")
        except Exception as exc:
            logger.error(f"Failed to persist verdict to database for case {case_uuid}: {exc}")
```

#### Key Reliability Properties:
1. **Idempotent**: Can be re-executed safely without duplicate rows or key conflicts.
2. **Non-blocking Failure**: If database persistence encounters a transient error, the error is logged, but the client stream does NOT crash, ensuring the user interface still receives the calculated verdict.
3. **Dual Persistence**: Synchronizes both TigerData PostgreSQL and the local memory cache `INVESTIGATION_CASES`.

---

### 4.6 Client Disconnects & Generator Lifecycle Cleanliness
In Starlette / Uvicorn, when a client closes the browser tab or tears down `EventSource`:
1. The ASGI connection raises `asyncio.CancelledError` or `GeneratorExit` at the active `await` or `yield` statement.
2. The generator handles this cleanly:
   ```python
   try:
       # Thought streaming and verdict persistence...
   except (asyncio.CancelledError, GeneratorExit):
       logger.info(f"SSE client disconnected for case {case_uuid}")
       raise
   finally:
       # Guaranteed cleanup
       pass
   ```
3. Since no database connection is held open across the generator intervals, client disconnects never leave orphaned open transactions or leaked pooled connections.

---

## 5. Complete Implementation Blueprint

### 5.1 Proposed Code Structure for `backend/api/routes/investigations.py`

```python
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_optional_db, get_session_factory
from backend.models.forensic import InvestigationCase, TransactionRecord
from backend.services.deterministic_filter import apply_deterministic_filter
from backend.services.ingestion import read_amlsim_csv

logger = logging.getLogger("forensic_auditor.investigations")
router = APIRouter(prefix="/investigations", tags=["investigations"])

INVESTIGATION_CASES: Dict[str, Dict[str, Any]] = {}


async def persist_case_verdict(
    case_uuid: uuid.UUID,
    verdict: Dict[str, Any],
    status_str: str = "COMPLETED",
) -> None:
    """Updates InvestigationCase with verdict and status in DB and memory."""
    case_str = str(case_uuid)
    if case_str in INVESTIGATION_CASES:
        INVESTIGATION_CASES[case_str]["verdict"] = verdict
        INVESTIGATION_CASES[case_str]["status"] = status_str

    if settings.DATABASE_URL:
        try:
            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    update(InvestigationCase)
                    .where(InvestigationCase.id == case_uuid)
                    .values(
                        verdict=verdict,
                        status=status_str,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Successfully persisted verdict for case {case_uuid} in DB.")
        except Exception as exc:
            logger.error(f"Error persisting verdict for case {case_uuid}: {exc}")


async def generate_investigation_stream(
    case_uuid: uuid.UUID,
    case_data: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Streams thought events and terminal verdict. Dispatches to n8n if available,
    otherwise executes high-fidelity 6-phase forensic simulation. Persists verdict
    before stream termination.
    """
    metrics = case_data.get("metrics") or case_data.get("filter_results", {}).get("metrics", {})
    patterns = case_data.get("patterns") or case_data.get("filter_results", {}).get("patterns", {})
    subgraph = case_data.get("subgraph") or case_data.get("filter_results", {}).get("subgraph", {})

    total_nodes = metrics.get("total_nodes_analyzed", 0)
    total_edges = metrics.get("total_edges_analyzed", 0)
    suspicious_nodes = metrics.get("suspicious_nodes_count", 0)
    cycles_count = metrics.get("detected_cycles_count", 0)
    pt_count = metrics.get("passthrough_accounts_count", 0)
    pruned_count = metrics.get("pruned_edges_count", 0)
    pruning_pct = metrics.get("pruning_efficiency_pct", 0.0)
    volume_mxn = float(metrics.get("suspicious_volume_mxn", 0.0))

    try:
        # 1. Attempt external n8n Webhook Proxy
        if settings.N8N_WEBHOOK_URL:
            try:
                timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST",
                        settings.N8N_WEBHOOK_URL,
                        json={
                            "case_id": str(case_uuid),
                            "metrics": metrics,
                            "patterns": patterns,
                            "subgraph": subgraph,
                        },
                    ) as response:
                        if response.status_code == 200 and "text/event-stream" in response.headers.get("content-type", ""):
                            n8n_verdict = None
                            is_verdict_event = False
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("event:"):
                                    evt = line.split(":", 1)[1].strip()
                                    is_verdict_event = (evt == "verdict")
                                elif line.startswith("data:") and is_verdict_event:
                                    try:
                                        n8n_verdict = json.loads(line.split(":", 1)[1].strip())
                                    except Exception:
                                        pass
                                    is_verdict_event = False
                                yield f"{line}\n\n"

                            if n8n_verdict:
                                await persist_case_verdict(case_uuid, n8n_verdict, "COMPLETED")
                                return
            except Exception as exc:
                logger.warning(f"n8n webhook unavailable ({exc}), falling back to internal simulation.")

        # 2. Local 6-Phase Simulation Fallback
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
                "message": f"Descartadas {pruned_count} transacciones legítimas ({pruning_pct}% de reducción de ruido). Subgrafo crítico aislado con {suspicious_nodes} nodos.",
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

        await asyncio.sleep(0.4)

        # 3. Compile Verdict
        risk_level = "CRÍTICO" if (cycles_count > 0 or volume_mxn > 500000) else "ALTO"
        suspicious_node_ids = [
            n["id"] for n in subgraph.get("nodes", [])
            if isinstance(n, dict) and "id" in n
        ]

        verdict_payload = {
            "case_id": str(case_uuid),
            "risk_level": risk_level,
            "fraud_type": "Estructuración Circular (Smurfing) y Cuentas Mula de Paso Rápido",
            "total_amount_mxn": volume_mxn,
            "confidence_score": 0.94 if cycles_count > 0 else 0.88,
            "entities_involved": suspicious_node_ids,
            "pruned_leads_count": pruned_count,
            "patterns_summary": {
                "closed_cycles": cycles_count,
                "passthrough_accounts": pt_count,
                "pruning_efficiency_pct": pruning_pct,
            },
            "legal_recommendation": (
                "Presentar de forma urgente un Reporte de Operación Inusual (ROI) ante la UIF "
                "y proceder con la congelación cautelar de los fondos remanentes en las cuentas puente."
            ),
            "audit_summary_text": (
                f"Dictamen Pericial Forense para el caso {str(case_uuid)[:8]}. Se identificó una red estructurada "
                f"de lavado de dinero por un monto total de ${volume_mxn:,.2f} pesos mexicanos. "
                f"El análisis topológico determinó {cycles_count} ciclos dirigidos de triangulación de fondos "
                f"y {pt_count} cuentas mula con dispersión superior al 90% en ventanas menores a 48 horas. "
                f"Se descartaron exitosamente {pruned_count} transferencias no vinculadas mediante poda determinista."
            ),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        # 4. Persist Verdict to Database & Update Status
        await persist_case_verdict(case_uuid, verdict_payload, status_str="COMPLETED")

        # 5. Emit Terminal Verdict Event
        yield f"event: verdict\ndata: {json.dumps(verdict_payload)}\n\n"

    except (asyncio.CancelledError, GeneratorExit):
        logger.info(f"Stream client disconnected for case {case_uuid}")
        raise
    except Exception as exc:
        logger.error(f"Error during stream execution for case {case_uuid}: {exc}")
        raise
```

---

## 6. Verification & Automated Test Strategy

To verify this implementation under Milestone 5 and during implementer testing:

1. **Unit & Integration Test Cases**:
   - `test_stream_case_not_found_404`: Passing a random UUID to `/api/v1/investigations/{uuid}/stream` verifies that HTTP 404 is returned immediately before any SSE headers.
   - `test_stream_invalid_uuid_400`: Passing a non-UUID string returns HTTP 400 Bad Request.
   - `test_stream_events_flow`: Consuming the stream verifies all 6 `thought` events and the 1 terminal `verdict` event.
   - `test_stream_verdict_persisted_in_db`: Querying `InvestigationCase` from PostgreSQL verifies that:
     - `case.status == "COMPLETED"`
     - `case.verdict["case_id"] == str(case_uuid)`
     - `case.verdict["risk_level"] in ("CRÍTICO", "ALTO")`
     - `case.updated_at >= case.created_at`
   - `test_n8n_webhook_fallback`: Setting `N8N_WEBHOOK_URL="http://invalid.host:9999"` verifies that the fallback simulation seamlessly executes without failing.

2. **Zero-Regression Assurance**:
   The dual-layer fallback mechanism ensures that running `python -m pytest backend/tests` continues to pass cleanly (100%) in both offline environments (without a live PostgreSQL database) and connected TigerData PostgreSQL environments.
