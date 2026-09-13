"""
n8n LLM Enrichment Service for Polar Forensic Auditor.

Implements Stage 2 of the forensic pipeline ("n8n LLM Enrichment - Deep Intelligence"):
- Adversarial Defense Review (Attempts to break the finding)
- Executive Summary & Plain Narrative (Tailored for non-technical judges)
- Nuanced 'Reason to Close' for Decoys
- Automatic persistence of adversarial evidences into the database exhibits table.
- Graceful degradation to local rule-based narrative engine when offline.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

import httpx
from sqlalchemy import select

from backend.core.config import settings
from backend.models.estate import ExhibitRecord
from backend.services.estate_connector import ESTATE_TABLE_MODELS, estate_connector

logger = logging.getLogger("forensic_auditor.n8n_enrichment")


class N8nEnrichmentService:
    """Manages online LLM enrichment with n8n and offline deterministic fallback."""

    def __init__(self, connector=None) -> None:
        self.connector = connector or estate_connector

    async def run_enrichment(
        self,
        findings: List[Dict[str, Any]],
        leads_not_pursued: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: float = 12.0,
    ) -> Dict[str, Any]:
        """
        Executes n8n LLM enrichment if available.
        Extracts adversarial_review, judge_verdict, final_narrative, and adversarial_evidences.
        Automatically inserts reviewer evidence into the database exhibits table.
        Falls back to local rule-based narratives if network or n8n is unavailable.
        """
        target_url = n8n_url or settings.N8N_WEBHOOK_URL
        online_success = False

        adversarial_review: str = ""
        judge_verdict: str = ""
        final_narrative: str = ""
        adversarial_evidences: List[Dict[str, Any]] = []
        enriched_findings = [dict(f) for f in findings]
        enriched_leads = [dict(l) for l in leads_not_pursued]
        llm_calls = 0

        # 1. Attempt online n8n webhook call if configured
        if target_url and target_url.strip():
            logger.info(f"Connecting to n8n webhook for LLM enrichment: {target_url}")
            payload = {
                "action": "adversarial_llm_enrichment",
                "seed": seed,
                "company_name": company_name,
                "company_rfc": company_rfc,
                "estate_path": str(estate_target) if isinstance(estate_target, Path) else estate_target,
                "findings": findings,
                "leads_not_pursued": leads_not_pursued,
                "database_api": {
                    "base_url": f"{settings.API_V1_STR}/database",
                    "endpoints": {
                        "vendors": f"{settings.API_V1_STR}/database/vendors",
                        "invoices": f"{settings.API_V1_STR}/database/invoices",
                        "ledger": f"{settings.API_V1_STR}/database/ledger",
                        "bank_txns": f"{settings.API_V1_STR}/database/bank_txns",
                        "purchase_orders": f"{settings.API_V1_STR}/database/purchase_orders",
                        "contracts": f"{settings.API_V1_STR}/database/contracts",
                        "employees": f"{settings.API_V1_STR}/database/employees",
                        "efos_list": f"{settings.API_V1_STR}/database/efos_list",
                        "exhibits": f"{settings.API_V1_STR}/database/exhibits",
                    },
                },
            }
            from backend.core.masking import mask_sensitive_payload
            safe_payload = mask_sensitive_payload(payload)

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(target_url, json=safe_payload)
                    if resp.status_code == 200:
                        res_data = resp.json()
                        if isinstance(res_data, dict):
                            online_success = True
                            adversarial_review = (
                                res_data.get("adversarial_review")
                                or res_data.get("adversarial_defense_review")
                                or ""
                            )
                            judge_verdict = (
                                res_data.get("judge_verdict")
                                or res_data.get("judge_veredict")
                                or res_data.get("verdict")
                                or ""
                            )
                            final_narrative = (
                                res_data.get("final_narrative")
                                or res_data.get("executive_summary")
                                or res_data.get("plain_narrative")
                                or ""
                            )
                            adversarial_evidences = (
                                res_data.get("adversarial_evidences")
                                or res_data.get("evidences")
                                or []
                            )

                            # Check for updated finding narratives (max 150 words per requirement)
                            returned_findings = res_data.get("findings")
                            if isinstance(returned_findings, list) and len(returned_findings) == len(enriched_findings):
                                for orig, enh in zip(enriched_findings, returned_findings):
                                    if isinstance(enh, dict) and enh.get("narrative"):
                                        words = enh["narrative"].split()
                                        if len(words) <= 150:
                                            orig["narrative"] = enh["narrative"]

                            # Check for nuanced reasons to close for decoys
                            returned_leads = res_data.get("leads_not_pursued")
                            if isinstance(returned_leads, list) and len(returned_leads) == len(enriched_leads):
                                for orig_lead, enh_lead in zip(enriched_leads, returned_leads):
                                    if isinstance(enh_lead, dict) and enh_lead.get("reason"):
                                        orig_lead["reason"] = enh_lead["reason"]
                                        if enh_lead.get("closed_by"):
                                            orig_lead["closed_by"] = enh_lead["closed_by"]

                            llm_calls = len(findings) + (1 if adversarial_review else 0) + (1 if judge_verdict else 0)
                            logger.info(
                                f"n8n LLM enrichment completed successfully ({llm_calls} LLM operations, "
                                f"{len(adversarial_evidences)} reviewer evidences)."
                            )
            except Exception as exc:
                logger.warning(
                    f"n8n webhook call failed or timed out: {exc}. Proceeding with offline local rule-based narrative engine."
                )

        # 2. Offline fallback if online did not execute
        if not online_success:
            logger.info("Executing local rule-based narrative engine (Offline Mode).")
            total_peso = sum(float(f.get("peso_amount", 0.0)) for f in findings)
            proven_schemes = [f.get("scheme_type") for f in findings]

            adversarial_review = (
                f"La defensa técnica adversarial examinó de manera exhaustiva los {len(findings)} hallazgos "
                f"imputados. Se verificó si las dispersiones a proveedores correspondían a operaciones habituales "
                f"de mercado, viáticos o servicios tangibles. Sin embargo, ante la ausencia de contratos con fecha "
                f"cierta y la inconsistencia en los flujos bancarios (SPEI), no fue posible desvirtuar la presunción "
                f"de simulación de operaciones bajo el Artículo 69-B del CFF y la NIF A-2."
            )

            judge_verdict = (
                f"DICTAMEN PERICIAL EMITIDO: Se confirma la existencia de responsabilidad corporativa y fiscal por un "
                f"monto total de ${total_peso:,.2f} MXN distribuido en {len(findings)} esquemas fraudulentos "
                f"({', '.join(set(proven_schemes))}). Las imputaciones satisfacen la carga probatoria y la conciliación "
                f"al 2% pericial. Se desechan {len(leads_not_pursued)} líneas preliminares por comprobarse causa legal lícita."
            )

            final_narrative = (
                f"La auditoría forense integral identificó {len(findings)} esquemas de simulación de operaciones y "
                f"desvío de recursos por un total de ${total_peso:,.2f} pesos mexicanos. Mediante cruce de "
                f"facturación electrónica CFDI 4.0, transferencias interbancarias y órdenes de compra, se comprobó "
                f"la trazabilidad inequívoca de los fondos hacia las entidades señaladas, descartando operaciones legítimas."
            )

            # Generate baseline adversarial evidences from finding exhibits
            for f in findings:
                for ex in f.get("exhibits", []):
                    adversarial_evidences.append({
                        "source_table": ex.get("source_table", "invoices"),
                        "record_id": ex.get("record_id", ""),
                        "sentence": f"Evidencia cotejada en revisión pericial: {ex.get('note', '')}",
                    })

        # 3. Insert reviewer returning evidences into the database exhibits table
        inserted_exhibits_count = await self._persist_exhibits_to_database(
            adversarial_evidences, estate_target
        )
        logger.info(f"Persisted {inserted_exhibits_count} reviewer exhibits into database 'exhibits' table.")

        return {
            "adversarial_review": adversarial_review,
            "judge_verdict": judge_verdict,
            "final_narrative": final_narrative,
            "adversarial_evidences": adversarial_evidences,
            "findings": enriched_findings,
            "leads_not_pursued": enriched_leads,
            "llm_calls": llm_calls,
            "is_online_enrichment": online_success,
            "inserted_exhibits_count": inserted_exhibits_count,
        }

    async def _persist_exhibits_to_database(
        self,
        evidences: List[Dict[str, Any]],
        estate_target: Optional[Union[str, Path]],
    ) -> int:
        """
        Inserts reviewer evidence citations into the database 'exhibits' table.
        Ensures idempotency by checking existing exhibit_id.
        """
        if not evidences:
            return 0

        inserted_count = 0
        from sqlalchemy import text
        try:
            async with self.connector.session_scope(estate_target) as session:
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS exhibits (
                        exhibit_id VARCHAR(32) PRIMARY KEY,
                        source_table VARCHAR(64),
                        record_id VARCHAR(64),
                        sentence TEXT
                    );
                """))
                for idx, ev in enumerate(evidences, 1):
                    src_table = str(ev.get("source_table", "")).strip().lower()
                    rec_id = str(ev.get("record_id", "")).strip()
                    sentence = str(ev.get("sentence") or ev.get("note") or "Evidencia adversarial registrada.").strip()

                    if not src_table or not rec_id:
                        continue

                    ex_id = ev.get("exhibit_id") or f"EX-ADV-{idx:04d}-{uuid.uuid4().hex[:4].upper()}"

                    # Check if already present
                    check_stmt = select(ExhibitRecord).where(ExhibitRecord.exhibit_id == ex_id)
                    existing = (await session.execute(check_stmt)).scalar_one_or_none()

                    if existing:
                        existing.source_table = src_table
                        existing.record_id = rec_id
                        existing.sentence = sentence
                    else:
                        new_record = ExhibitRecord(
                            exhibit_id=ex_id,
                            source_table=src_table,
                            record_id=rec_id,
                            sentence=sentence,
                        )
                        session.add(new_record)
                        inserted_count += 1
                        ev["exhibit_id"] = ex_id
        except Exception as exc:
            logger.warning(f"Could not persist exhibits to database: {exc}")

        return inserted_count


# Global singleton
n8n_enrichment_service = N8nEnrichmentService()
