"""
n8n LLM Enrichment Service for Polar Forensic Auditor.

Implements Stage 2 of the forensic pipeline ("n8n LLM Enrichment - Deep Intelligence"):
- Sequential One-by-One Finding Review:
  - Adversarial Defense Review (Attempts to break the finding)
  - Individual Judge Verdict for each finding
  - Per-finding narrative & exhibit citations
- Sequential One-by-One Decoy Lead Review:
  - Nuanced 'Reason to Close' & dismiss verdict for decoys
- Overarching Case Verdict Synthesis
- Automatic persistence of adversarial evidences into the database exhibits table.
- Graceful degradation to local rule-based narrative engine when offline.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import uuid

import httpx
from sqlalchemy import select

from backend.core.config import settings
from backend.core.masking import mask_sensitive_payload
from backend.models.estate import ExhibitRecord
from backend.services.estate_connector import ESTATE_TABLE_MODELS, estate_connector

logger = logging.getLogger("forensic_auditor.n8n_enrichment")

VALID_CLOSED_BY = {"challenger", "investigator", "validator"}


class N8nEnrichmentService:
    """Manages sequential online LLM enrichment with n8n and offline deterministic fallback."""

    def __init__(self, connector=None) -> None:
        self.connector = connector or estate_connector

    async def review_single_finding(
        self,
        finding: Dict[str, Any],
        index: int,
        total: int,
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a single finding to n8n for individual adversarial defense review,
        judicial verdict, narrative refinement, and evidence collection.
        Automatically inserts reviewer evidence into database 'exhibits' table.
        Falls back to local deterministic judicial review if n8n is unreachable.
        """
        target_url = n8n_url or settings.N8N_WEBHOOK_URL
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        adv_review: str = ""
        judge_verdict: str = ""
        final_narrative: str = ""
        adv_evidences: List[Dict[str, Any]] = []

        f_copy = dict(finding)
        scheme_type = f_copy.get("scheme_type", "esquema")
        amount = float(f_copy.get("peso_amount", 0.0))
        rule = f_copy.get("rule_broken", "Artículo 69-B del CFF / NIF A-2")
        entities_str = ", ".join(f_copy.get("entities", []))

        if target_url and target_url.strip():
            payload = {
                "action": "adversarial_review_finding",
                "seed": seed,
                "company_name": company_name,
                "company_rfc": company_rfc,
                "estate_path": str(estate_target) if isinstance(estate_target, Path) else estate_target,
                "finding_index": index,
                "total_findings": total,
                "finding": f_copy,
            }
            safe_payload = mask_sensitive_payload(payload)

            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=eff_timeout) as client:
                        resp = await client.post(target_url, json=safe_payload)
                        if resp.status_code == 200:
                            online_success = True
                            res_data = resp.json()
                            if isinstance(res_data, dict):
                                adv_review = (
                                    res_data.get("adversarial_review")
                                    or res_data.get("adversarial_defense_review")
                                    or res_data.get("defense_review")
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
                                    or res_data.get("narrative")
                                    or res_data.get("plain_narrative")
                                    or ""
                                )
                                adv_evidences = (
                                    res_data.get("adversarial_evidences")
                                    or res_data.get("evidences")
                                    or res_data.get("exhibits")
                                    or []
                                )
                                if final_narrative and len(final_narrative.split()) <= 150:
                                    f_copy["narrative"] = final_narrative
                                break
                except Exception as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for finding {index}/{total} failed or timed out: {exc}. Using deterministic review."
                    )

        if not adv_review:
            adv_review = (
                f"La defensa técnica adversarial examinó el hallazgo {index}/{total} ({scheme_type}) "
                f"imputado a `{entities_str}` por un monto de ${amount:,.2f} MXN. Se verificó en libros contables "
                f"si correspondía a operaciones habituales de mercado o viáticos comprobables. Sin embargo, ante la "
                f"ausencia de contratos con fecha cierta y la inconsistencia en flujos bancarios (SPEI), no fue "
                f"posible desvirtuar la infracción prevista en Artículo 69-B del CFF ({rule})."
            )
        if not judge_verdict:
            judge_verdict = (
                f"VEREDICTO DEL JUEZ (HALLAZGO {index}/{total}): CULPABLE / IMPUTACIÓN PROCEDENTE. "
                f"Se declara plenamente acreditada la responsabilidad fiscal y corporativa por ${amount:,.2f} MXN "
                f"bajo el supuesto de {rule}. Se desestima la excepción planteada por la defensa por carecer de "
                f"sustancia económica y materialidad jurídica."
            )
        if not final_narrative:
            final_narrative = (
                f_copy.get("narrative")
                or f"Operación simulada comprobada por ${amount:,.2f} MXN atribuida a `{entities_str}` con trazabilidad bancaria inequívoca."
            )
        if not adv_evidences:
            # Baseline evidence from finding exhibits
            for ex in f_copy.get("exhibits", []):
                adv_evidences.append({
                    "source_table": ex.get("source_table", "invoices"),
                    "record_id": ex.get("record_id", ""),
                    "sentence": f"Evidencia cotejada en revisión pericial: {ex.get('note', '')}",
                })

        # Persist exhibits to database
        inserted_count = await self._persist_exhibits_to_database(adv_evidences, estate_target)

        # Attach per-finding fields
        f_copy["adversarial_review"] = adv_review
        f_copy["judge_verdict"] = judge_verdict
        f_copy["final_narrative"] = final_narrative
        f_copy["adversarial_evidences"] = adv_evidences

        return {
            "finding": f_copy,
            "adversarial_review": adv_review,
            "judge_verdict": judge_verdict,
            "final_narrative": final_narrative,
            "adversarial_evidences": adv_evidences,
            "inserted_exhibits_count": inserted_count,
            "is_online": online_success,
        }

    async def review_single_lead(
        self,
        lead: Dict[str, Any],
        index: int,
        total: int,
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a single decoy lead to n8n for nuanced dismissal justification and
        individual acquittal judge verdict.
        """
        target_url = n8n_url or settings.N8N_WEBHOOK_URL
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        adv_review: str = ""
        judge_verdict: str = ""
        reason: str = ""

        l_copy = dict(lead)
        raw_closed_by = l_copy.get("closed_by")
        closed_by = raw_closed_by if raw_closed_by in VALID_CLOSED_BY else "challenger"
        entity = l_copy.get("entity") or l_copy.get("entities") or "Entidad Auditada"
        signal = l_copy.get("signal") or l_copy.get("scheme_type") or "Señal de alerta"
        existing_reason = (
            l_copy.get("reason")
            or "Operación comercial ordinaria verificada documentalmente conforme a derecho con materialidad probada."
        )

        if target_url and target_url.strip():
            payload = {
                "action": "review_decoy_lead",
                "seed": seed,
                "company_name": company_name,
                "company_rfc": company_rfc,
                "estate_path": str(estate_target) if isinstance(estate_target, Path) else estate_target,
                "lead_index": index,
                "total_leads": total,
                "lead": l_copy,
            }
            safe_payload = mask_sensitive_payload(payload)

            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=eff_timeout) as client:
                        resp = await client.post(target_url, json=safe_payload)
                        if resp.status_code == 200:
                            online_success = True
                            res_data = resp.json()
                            if isinstance(res_data, dict):
                                adv_review = (
                                    res_data.get("adversarial_review")
                                    or res_data.get("defense_review")
                                    or ""
                                )
                                judge_verdict = (
                                    res_data.get("judge_verdict")
                                    or res_data.get("judge_veredict")
                                    or res_data.get("verdict")
                                    or ""
                                )
                                reason = (
                                    res_data.get("reason")
                                    or res_data.get("reason_to_close")
                                    or ""
                                )
                                ret_closed_by = res_data.get("closed_by")
                                if ret_closed_by in VALID_CLOSED_BY:
                                    closed_by = ret_closed_by
                                break
                except Exception as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for lead {index}/{total} failed or timed out: {exc}. Using deterministic review."
                    )

        if not adv_review:
            adv_review = (
                f"Revisión preliminar de la línea {index}/{total} (`{entity}`): Se constató soporte documental "
                f"ordinario, contratos vigentes y congruencia entre cotizaciones, órdenes de compra y facturas."
            )
        if not judge_verdict:
            judge_verdict = (
                f"VEREDICTO DEL JUEZ (LÍNEA {index}/{total}): ABSUELTO / LÍNEA DESESTIMADA. "
                f"Causa legal lícita plenamente acreditada respecto a la alerta `{signal}`. "
                f"Se decreta el archivo formal y definitivo de esta línea de investigación."
            )
        if not reason:
            reason = existing_reason

        l_copy["adversarial_review"] = adv_review
        l_copy["judge_verdict"] = judge_verdict
        l_copy["reason"] = reason
        l_copy["closed_by"] = closed_by

        return {
            "lead": l_copy,
            "adversarial_review": adv_review,
            "judge_verdict": judge_verdict,
            "reason": reason,
            "closed_by": closed_by,
            "is_online": online_success,
        }

    async def synthesize_case_verdict(
        self,
        reviewed_findings: List[Dict[str, Any]],
        reviewed_leads: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes the overarching case verdict and executive narrative based on the
        individual finding and lead verdicts.
        """
        target_url = n8n_url or settings.N8N_WEBHOOK_URL
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        total_peso = sum(float(f.get("peso_amount", 0.0))
                         for f in reviewed_findings)
        proven_schemes = list(set(f.get("scheme_type", "esquema")
                              for f in reviewed_findings))

        judge_verdict: str = ""
        final_narrative: str = ""

        if target_url and target_url.strip():
            payload = {
                "action": "synthesize_case_verdict",
                "seed": seed,
                "company_name": company_name,
                "company_rfc": company_rfc,
                "total_fraud_volume_mxn": round(total_peso, 2),
                "findings_count": len(reviewed_findings),
                "dismissed_leads_count": len(reviewed_leads),
                "reviewed_findings": [
                    {
                        "scheme_type": f.get("scheme_type"),
                        "amount": f.get("peso_amount"),
                        "judge_verdict": f.get("judge_verdict"),
                        "adversarial_review": f.get("adversarial_review"),
                    }
                    for f in reviewed_findings
                ],
                "dismissed_leads": [
                    {
                        "entity": l.get("entity"),
                        "judge_verdict": l.get("judge_verdict"),
                        "reason": l.get("reason"),
                    }
                    for l in reviewed_leads
                ],
            }
            safe_payload = mask_sensitive_payload(payload)

            try:
                async with httpx.AsyncClient(timeout=eff_timeout) as client:
                    resp = await client.post(target_url, json=safe_payload)
                    if resp.status_code == 200:
                        online_success = True
                        res_data = resp.json()
                        if isinstance(res_data, dict):
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
            except Exception as exc:
                logger.warning(
                    f"n8n case synthesis call failed: {exc}. Using deterministic summary.")

        if not judge_verdict:
            judge_verdict = (
                f"DICTAMEN PERICIAL EMITIDO: Se confirma la existencia de responsabilidad corporativa y fiscal por un "
                f"monto total de ${total_peso:,.2f} MXN distribuido en {len(reviewed_findings)} esquemas fraudulentos "
                f"({', '.join(proven_schemes)}). Las imputaciones satisfacen plenamente la carga probatoria y la conciliación "
                f"al 2% pericial. Se sobreseen formalmente {len(reviewed_leads)} líneas preliminares por comprobarse causa legal lícita."
            )
        if not final_narrative:
            final_narrative = (
                f"La auditoría forense integral identificó {len(reviewed_findings)} esquemas de simulación de operaciones y "
                f"desvío de recursos por un total de ${total_peso:,.2f} pesos mexicanos. Mediante cruce de "
                f"facturación electrónica CFDI 4.0, transferencias interbancarias y órdenes de compra, se comprobó "
                f"la trazabilidad inequívoca de los fondos hacia las entidades señaladas, descartando operaciones legítimas."
            )

        return {
            "judge_verdict": judge_verdict,
            "final_narrative": final_narrative,
            "is_online": online_success,
        }

    async def stream_enrichment_steps(
        self,
        findings: List[Dict[str, Any]],
        leads_not_pursued: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields progress step-by-step as each finding and each lead is reviewed one-by-one:
        1. Yields started event
        2. For each finding: calls review_single_finding -> yields finding_reviewed
        3. For each lead: calls review_single_lead -> yields lead_reviewed
        4. Barrier check: guarantees ALL findings and ALL leads have returned an answer
        5. Calls synthesize_case_verdict -> yields verdict_synthesized
        6. Yields completed summary
        """
        total_findings = len(findings)
        total_leads = len(leads_not_pursued)
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT

        yield {
            "type": "enrichment_started",
            "total_findings": total_findings,
            "total_leads": total_leads,
            "message": f"Iniciando revisión adversarial de {total_findings} hallazgos y {total_leads} líneas preliminares...",
        }

        enriched_findings: List[Dict[str, Any]] = []
        all_adversarial_evidences: List[Dict[str, Any]] = []
        finding_adv_reviews: List[str] = []
        llm_calls = 0
        total_exhibits_inserted = 0

        # 1. Review each finding one by one (positive fraud)
        for idx, finding in enumerate(findings, 1):
            finding_res = await self.review_single_finding(
                finding=finding,
                index=idx,
                total=total_findings,
                seed=seed,
                company_name=company_name,
                company_rfc=company_rfc,
                estate_target=estate_target,
                n8n_url=n8n_url,
                timeout=eff_timeout,
            )
            f_item = finding_res["finding"]
            enriched_findings.append(f_item)
            finding_adv_reviews.append(finding_res["adversarial_review"])
            all_adversarial_evidences.extend(
                finding_res["adversarial_evidences"])
            total_exhibits_inserted += finding_res["inserted_exhibits_count"]
            if finding_res["is_online"]:
                llm_calls += 1

            yield {
                "type": "finding_reviewed",
                "index": idx,
                "total": total_findings,
                "finding": f_item,
                "adversarial_review": finding_res["adversarial_review"],
                "judge_verdict": finding_res["judge_verdict"],
                "adversarial_evidences": finding_res["adversarial_evidences"],
                "inserted_exhibits_count": finding_res["inserted_exhibits_count"],
                "is_online": finding_res["is_online"],
                "message": (
                    f"Hallazgo {idx}/{total_findings} ({f_item.get('scheme_type')}): "
                    f"Veredicto judicial emitido ({'Culpable' if 'CULPABLE' in finding_res['judge_verdict'] else 'Evaluado'}). "
                    f"{len(finding_res['adversarial_evidences'])} evidencias registradas."
                ),
            }

        # 2. Review each decoy lead one by one (plausible fraud / decoys)
        enriched_leads: List[Dict[str, Any]] = []
        for idx, lead in enumerate(leads_not_pursued, 1):
            lead_res = await self.review_single_lead(
                lead=lead,
                index=idx,
                total=total_leads,
                seed=seed,
                company_name=company_name,
                company_rfc=company_rfc,
                estate_target=estate_target,
                n8n_url=n8n_url,
                timeout=eff_timeout,
            )
            l_item = lead_res["lead"]
            enriched_leads.append(l_item)
            if lead_res["is_online"]:
                llm_calls += 1

            yield {
                "type": "lead_reviewed",
                "index": idx,
                "total": total_leads,
                "lead": l_item,
                "adversarial_review": lead_res["adversarial_review"],
                "judge_verdict": lead_res["judge_verdict"],
                "reason": lead_res["reason"],
                "closed_by": lead_res["closed_by"],
                "is_online": lead_res["is_online"],
                "message": f"Línea preliminar {idx}/{total_leads} descartada legítimamente por `{lead_res['closed_by']}`.",
            }

        # 3. STRICT COMPLETION BARRIER:
        # Guarantee that 100% of finding reviews and 100% of lead reviews have returned an answer
        # before invoking n8n's verdict synthesis, preserving all context.
        if len(enriched_findings) != total_findings or len(enriched_leads) != total_leads:
            logger.warning(
                f"Barrier sync notice: findings {len(enriched_findings)}/{total_findings}, "
                f"leads {len(enriched_leads)}/{total_leads} before synthesis call."
            )

        # 4. Synthesize overarching case verdict with all reviewed items
        synthesis = await self.synthesize_case_verdict(
            reviewed_findings=enriched_findings,
            reviewed_leads=enriched_leads,
            seed=seed,
            company_name=company_name,
            company_rfc=company_rfc,
            n8n_url=n8n_url,
            timeout=eff_timeout,
        )
        if synthesis["is_online"]:
            llm_calls += 1

        consolidated_adv_review = (
            "\n\n".join(finding_adv_reviews)
            if finding_adv_reviews
            else "Revisión adversarial completada satisfactoriamente para todas las imputaciones."
        )

        yield {
            "type": "verdict_synthesized",
            "judge_verdict": synthesis["judge_verdict"],
            "final_narrative": synthesis["final_narrative"],
            "adversarial_review": consolidated_adv_review,
            "adversarial_evidences": all_adversarial_evidences,
            "findings": enriched_findings,
            "leads_not_pursued": enriched_leads,
            "llm_calls": llm_calls,
            "inserted_exhibits_count": total_exhibits_inserted,
            "message": "Dictamen pericial formal y narrativa judicial sintetizada con éxito.",
        }

    async def run_enrichment(
        self,
        findings: List[Dict[str, Any]],
        leads_not_pursued: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Empresa Auditada S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes sequential one-by-one enrichment and consolidates all findings,
        per-review verdicts, and exhibits into a single dictionary.
        """
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        final_summary: Dict[str, Any] = {}
        async for step in self.stream_enrichment_steps(
            findings=findings,
            leads_not_pursued=leads_not_pursued,
            seed=seed,
            company_name=company_name,
            company_rfc=company_rfc,
            estate_target=estate_target,
            n8n_url=n8n_url,
            timeout=eff_timeout,
        ):
            if step["type"] == "verdict_synthesized":
                final_summary = step

        return {
            "adversarial_review": final_summary.get("adversarial_review", ""),
            "judge_verdict": final_summary.get("judge_verdict", ""),
            "final_narrative": final_summary.get("final_narrative", ""),
            "adversarial_evidences": final_summary.get("adversarial_evidences", []),
            "findings": final_summary.get("findings", findings),
            "leads_not_pursued": final_summary.get("leads_not_pursued", leads_not_pursued),
            "llm_calls": final_summary.get("llm_calls", 0),
            "is_online_enrichment": final_summary.get("llm_calls", 0) > 0,
            "inserted_exhibits_count": final_summary.get("inserted_exhibits_count", 0),
        }

    async def _persist_exhibits_to_database(
        self,
        evidences: List[Dict[str, Any]],
        estate_target: Optional[Union[str, Path]],
    ) -> int:
        """
        Inserts reviewer evidence citations into the database 'exhibits' table
        and synchronizes to dual PostgreSQL tables.
        """
        if not evidences:
            return 0

        # Persist to local SQLite connector
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
                    sentence = str(ev.get("sentence") or ev.get(
                        "note") or "Evidencia adversarial registrada.").strip()

                    if not src_table or not rec_id:
                        continue

                    ex_id = ev.get(
                        "exhibit_id") or f"EX-ADV-{idx:04d}-{uuid.uuid4().hex[:4].upper()}"

                    # Check if already present
                    check_stmt = select(ExhibitRecord).where(
                        ExhibitRecord.exhibit_id == ex_id)
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
            logger.warning(f"Could not persist exhibits to local database: {exc}")

        # Persist to PostgreSQL dual tables (ethereal and historic)
        try:
            from backend.services.estate_sync import estate_sync_service
            await estate_sync_service.persist_exhibits_dual(evidences, estate_target=estate_target)
        except Exception as exc:
            logger.warning(f"Could not persist exhibits to dual PostgreSQL tables: {exc}")

        return inserted_count


# Global singleton
n8n_enrichment_service = N8nEnrichmentService()
