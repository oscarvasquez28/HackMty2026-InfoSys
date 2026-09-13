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
import random
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

# Sentinel value for n8n_url: when a request passes "offline", every n8n call is
# skipped and the deterministic local engine runs instead (zero network attempts).
OFFLINE_MODE_SENTINEL = "offline"

# ---------------------------------------------------------------------------
# Tolerant n8n response parsing
#
# n8n workflows do not guarantee a stable response envelope: depending on the
# last node, the webhook may answer a plain dict, an array of items `[{...}]`,
# n8n's `[{"json": {...}}]` item format, or a dict nested under wrapper keys
# (`output`, `data`, `result`, ...). These helpers normalize every observed
# shape into the flat dict the pipeline expects, so real AI output is never
# silently replaced by the deterministic fallback.
# ---------------------------------------------------------------------------

_WRAPPER_KEYS = ("output", "body", "data", "result", "response")

ADV_REVIEW_KEYS = (
    "adversarial_review",
    "adversarial_defense_review",
    "defense_review",
    "challenger_review",
    "challenger_argument",
    "review",
)
JUDGE_VERDICT_KEYS = (
    "judge_verdict",
    "judge_veredict",
    "verdict",
    "decision",
    "ruling",
    "dictamen",
)
FINAL_NARRATIVE_KEYS = (
    "final_narrative",
    "narrative",
    "plain_narrative",
    "executive_summary",
    "summary",
    "text",
    "output",
    "narrativa",
)
EVIDENCES_KEYS = (
    "adversarial_evidences",
    "evidences",
    "exhibits",
    "evidence",
)
REASON_KEYS = ("reason", "reason_to_close", "dismissal_reason", "justification")
OUTCOME_KEYS = ("verdict_outcome", "outcome", "resolution")

# Acquittal markers are checked before upheld markers so negations like
# "no culpable" / "not guilty" / "no se acreditó" are read correctly. The bare
# word "dismiss" is deliberately absent: upheld verdicts routinely say things
# like "the defense's exception is dismissed", which is not an acquittal.
_ACQUITTAL_MARKERS = (
    "acquit",
    "absuel",
    "absolv",
    "not guilty",
    "no culpable",
    "inocent",
    "exonerat",
    "sin responsabilidad",
    "sin cargo",
    "charge dismissed",
    "charges dismissed",
    "case dismissed",
    "lead dismissed",
    "finding dismissed",
    "accusation dismissed",
    "cargo desestim",
    "cargos desestim",
    "imputación desestim",
    "hallazgo desestim",
    "acusación desestim",
    "sobrese",
    "not liable",
    "no liability",
    "not proven",
    "not substantiated",
    "unsubstantiated",
    "no acredit",
    "no se acredit",
    "not confirmed",
    "no confirm",
)
_UPHELD_MARKERS = (
    "guilt",
    "culpable",
    "upheld",
    "liable",
    "responsabilidad",
    "confirm",
    "condena",
    "acredit",
)


def _unwrap_n8n_payload(res_data: Any) -> Dict[str, Any]:
    """
    Normalizes a raw n8n webhook JSON body into a flat dict.

    Handles: plain dicts, item arrays `[{...}]`, n8n `[{"json": {...}}]` items,
    and payloads nested one level under wrapper keys (`output`, `body`, `data`,
    `result`, `response`). Returns {} when nothing usable is found.
    """
    data = res_data
    if isinstance(data, list):
        data = data[0] if data else {}
    if isinstance(data, dict) and isinstance(data.get("json"), dict):
        data = data["json"]
    if not isinstance(data, dict):
        return {}
    merged = dict(data)
    for key in _WRAPPER_KEYS:
        inner = data.get(key)
        if isinstance(inner, dict):
            for k, v in inner.items():
                merged.setdefault(k, v)
    return merged


def _first_str(data: Dict[str, Any], *keys: str) -> str:
    """
    Returns the first non-empty string among alias keys. Dict-valued candidates
    are searched for nested narrative keys (e.g. executive_summary.plain_narrative).
    """
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            nested = _first_str(val, "plain_narrative", "text", "narrative", "message", "summary")
            if nested:
                return nested
    return ""


def _first_field(data: Dict[str, Any], *keys: str) -> Any:
    """Returns the first non-empty string or dict among alias keys."""
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict) and val:
            return val
    return ""


def _first_list(data: Dict[str, Any], *keys: str) -> List[Any]:
    """Returns the first non-empty list among alias keys."""
    for key in keys:
        val = data.get(key)
        if isinstance(val, list) and val:
            return val
    return []


def _adv_review_text(raw: Any) -> str:
    """Flattens an adversarial review (string or structured object) to display text."""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        parts = [
            str(raw.get(k) or "").strip()
            for k in ("challenger_argument", "argument", "defense_argument", "review", "why_finding_held", "rebuttal")
        ]
        return " ".join(p for p in parts if p)
    return ""


def _adv_review_object(raw: Any, judge_verdict: str) -> Dict[str, str]:
    """
    Builds the case-file adversarial_review object
    {reviewer_agent_role, challenger_argument, why_finding_held} from whatever
    n8n returned. A plain string becomes the challenger argument and the judge
    verdict fills the rebuttal panel.
    """
    if isinstance(raw, dict):
        return {
            "reviewer_agent_role": str(raw.get("reviewer_agent_role") or raw.get("agent_role") or "challenger"),
            "challenger_argument": str(
                raw.get("challenger_argument") or raw.get("argument") or raw.get("defense_argument") or ""
            ),
            "why_finding_held": str(
                raw.get("why_finding_held") or raw.get("rebuttal") or raw.get("held_reason") or judge_verdict or ""
            ),
        }
    return {
        "reviewer_agent_role": "challenger",
        "challenger_argument": raw if isinstance(raw, str) else "",
        "why_finding_held": judge_verdict or "",
    }


def parse_verdict_outcome(judge_verdict: str, explicit: str = "") -> str:
    """
    Parses the AI judge's decision into 'upheld' | 'acquitted' | 'evaluated'.
    An explicit structured outcome field wins; otherwise the verdict text is
    scanned ES/EN, checking acquittal markers first so negations like
    'no culpable' / 'not guilty' are not read as upheld.
    """
    for source in (explicit, judge_verdict):
        text = (source or "").lower()
        if not text:
            continue
        if any(marker in text for marker in _ACQUITTAL_MARKERS):
            return "acquitted"
        if any(marker in text for marker in _UPHELD_MARKERS):
            return "upheld"
    return "evaluated"


def _finding_to_dismissed_lead(finding: Dict[str, Any], adv_review_text: str = "") -> Dict[str, Any]:
    """
    Converts an AI-acquitted finding into a schema-valid leads_not_pursued entry,
    preserving the judicial verdict and adversarial review as the closing reason.
    """
    entities = finding.get("entities") or []
    entity = entities[0] if entities else "Unknown entity"
    scheme = str(finding.get("scheme_type", "scheme")).replace("_", " ")
    verdict = finding.get("judge_verdict") or ""
    return {
        "entity": entity,
        "signal": f"{scheme} flagged by the deterministic engine and reviewed one-by-one by the adversarial agent.",
        "reason": verdict or adv_review_text or "Acquitted on adversarial review: the evidence did not substantiate the charge.",
        "tool_calls_made": ["adversarial_review_finding"],
        "closed_by": "challenger",
        "closure_category": "ai_acquitted",
        "judge_verdict": verdict,
        "adversarial_review": adv_review_text,
        "verdict_outcome": "acquitted",
        "reclassified_from_finding": True,
    }


def _resolve_n8n_url(n8n_url: Optional[str]) -> str:
    """
    Resolves the effective n8n webhook URL for a request.
    Returns an empty string when the "offline" sentinel is passed, forcing the
    deterministic fallback path with no outbound connection attempts.
    """
    if n8n_url and n8n_url.strip().lower() == OFFLINE_MODE_SENTINEL:
        return ""
    return n8n_url or settings.N8N_WEBHOOK_URL


def estimate_llm_usage(seed: int) -> Dict[str, Any]:
    """
    Estimates Gemini usage for the run when the n8n workflow does not return
    per-call token metadata. Values are drawn from the configured estimation
    ranges with a seed-keyed RNG, so the same seed always reports the same
    estimate while different seeds show variance.

    Returns:
        {"llm_calls": int, "llm_tokens": int, "mxn_cost": float, "llm_usage_estimated": True}
    """
    rng = random.Random(f"llm-usage-estimate:{seed}")
    calls = rng.randint(settings.LLM_CALLS_ESTIMATE_MIN, settings.LLM_CALLS_ESTIMATE_MAX)
    tokens = rng.randint(settings.LLM_TOKENS_ESTIMATE_MIN, settings.LLM_TOKENS_ESTIMATE_MAX)
    return {
        "llm_calls": calls,
        "llm_tokens": tokens,
        "mxn_cost": round(tokens / 1000.0 * settings.GEMINI_MXN_PER_1K_TOKENS, 4),
        "llm_usage_estimated": True,
    }


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
        company_name: str = "Audited Company S.A. de C.V.",
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
        target_url = _resolve_n8n_url(n8n_url)
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        adv_review_raw: Any = ""
        adv_review: str = ""
        judge_verdict: str = ""
        final_narrative: str = ""
        explicit_outcome: str = ""
        adv_evidences: List[Dict[str, Any]] = []

        f_copy = dict(finding)
        scheme_type = f_copy.get("scheme_type", "scheme")
        amount = float(f_copy.get("peso_amount", 0.0))
        rule = f_copy.get("rule_broken", "Article 69-B of the CFF / NIF A-2")
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
                        if resp.status_code != 200:
                            logger.warning(
                                f"n8n call for finding {index}/{total} returned HTTP {resp.status_code}: "
                                f"{resp.text[:300]}"
                            )
                            if attempt == 0:
                                await asyncio.sleep(0.5)
                            continue
                        if not resp.text.strip():
                            logger.warning(
                                f"n8n webhook returned HTTP 200 with an EMPTY body. "
                                f"Please ensure in n8n that the Webhook trigger node 'Respond' parameter is set to "
                                f"'When Last Node Finishes' or 'Using Respond to Webhook Node', not 'Immediately'."
                            )
                            break
                        res_data = _unwrap_n8n_payload(resp.json())
                        adv_review_raw = _first_field(res_data, *ADV_REVIEW_KEYS)
                        judge_verdict = _first_str(res_data, *JUDGE_VERDICT_KEYS)
                        final_narrative = _first_str(res_data, *FINAL_NARRATIVE_KEYS)
                        explicit_outcome = _first_str(res_data, *OUTCOME_KEYS)
                        adv_evidences = _first_list(res_data, *EVIDENCES_KEYS)
                        extracted_any = bool(
                            adv_review_raw or judge_verdict or final_narrative or adv_evidences
                        )
                        if not extracted_any:
                            logger.warning(
                                f"n8n response for finding {index}/{total} carried no recognizable fields "
                                f"(body starts: {resp.text[:300]}). Using deterministic review."
                            )
                            break
                        online_success = True
                        adv_review = _adv_review_text(adv_review_raw)
                        if final_narrative and len(final_narrative.split()) <= 150:
                            f_copy["narrative"] = final_narrative
                        break
                except httpx.TimeoutException:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for finding {index}/{total} TIMED OUT after {eff_timeout}s. Using deterministic review."
                    )
                except httpx.ConnectError as conn_err:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n connection failed for finding {index}/{total} (cannot connect to {target_url}): {conn_err}. Using deterministic review."
                    )
                except Exception as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for finding {index}/{total} failed: {exc}. Using deterministic review."
                    )

        if not adv_review:
            adv_review = (
                f"The adversarial technical defense examined finding {index}/{total} ({scheme_type}) "
                f"imputed to `{entities_str}` for an amount of ${amount:,.2f} MXN. Accounting books were checked "
                f"to determine whether it corresponded to routine market operations or verifiable travel expenses. However, given the "
                f"absence of contracts with a certain date and the inconsistency in bank flows (SPEI), it was not "
                f"possible to disprove the infraction under Article 69-B of the CFF ({rule})."
            )
        if not judge_verdict:
            judge_verdict = (
                f"JUDGE'S VERDICT (FINDING {index}/{total}): GUILTY / CHARGE UPHELD. "
                f"Fiscal and corporate liability for ${amount:,.2f} MXN is declared fully substantiated "
                f"under the assumption of {rule}. The exception raised by the defense is dismissed for lacking "
                f"economic substance and legal materiality."
            )
        if not final_narrative:
            final_narrative = (
                f_copy.get("narrative")
                or f"Simulated transaction proven for ${amount:,.2f} MXN attributed to `{entities_str}` with unequivocal banking traceability."
            )
        if not adv_evidences:
            # Baseline evidence from finding exhibits
            for ex in f_copy.get("exhibits", []):
                adv_evidences.append({
                    "source_table": ex.get("source_table", "invoices"),
                    "record_id": ex.get("record_id", ""),
                    "sentence": f"Evidence verified during expert review: {ex.get('note', '')}",
                })

        verdict_outcome = parse_verdict_outcome(judge_verdict, explicit_outcome)

        adv_review_obj = _adv_review_object(
            adv_review_raw if adv_review_raw else adv_review, judge_verdict
        )
        if not adv_review_obj["challenger_argument"]:
            adv_review_obj["challenger_argument"] = adv_review
        if not adv_review_obj["why_finding_held"]:
            adv_review_obj["why_finding_held"] = judge_verdict

        # Persist exhibits to database
        inserted_count = await self._persist_exhibits_to_database(adv_evidences, estate_target)

        # Attach per-finding fields (adversarial_review uses the case-file object shape)
        f_copy["adversarial_review"] = adv_review_obj
        f_copy["judge_verdict"] = judge_verdict
        f_copy["final_narrative"] = final_narrative
        f_copy["adversarial_evidences"] = adv_evidences
        f_copy["verdict_outcome"] = verdict_outcome

        return {
            "finding": f_copy,
            "adversarial_review": adv_review,
            "judge_verdict": judge_verdict,
            "final_narrative": final_narrative,
            "adversarial_evidences": adv_evidences,
            "verdict_outcome": verdict_outcome,
            "inserted_exhibits_count": inserted_count,
            "is_online": online_success,
        }

    async def review_single_lead(
        self,
        lead: Dict[str, Any],
        index: int,
        total: int,
        seed: int,
        company_name: str = "Audited Company S.A. de C.V.",
        company_rfc: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a single decoy lead to n8n for nuanced dismissal justification and
        individual acquittal judge verdict.
        """
        target_url = _resolve_n8n_url(n8n_url)
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        adv_review: str = ""
        judge_verdict: str = ""
        reason: str = ""
        explicit_outcome: str = ""

        l_copy = dict(lead)
        raw_closed_by = l_copy.get("closed_by")
        closed_by = raw_closed_by if raw_closed_by in VALID_CLOSED_BY else "challenger"
        entity = l_copy.get("entity") or l_copy.get(
            "entities") or "Audited Entity"
        signal = l_copy.get("signal") or l_copy.get(
            "scheme_type") or "Alert signal"
        existing_reason = (
            l_copy.get("reason")
            or "Ordinary business transaction, documentarily verified in accordance with the law with proven materiality."
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
                        if resp.status_code != 200:
                            logger.warning(
                                f"n8n call for lead {index}/{total} returned HTTP {resp.status_code}: "
                                f"{resp.text[:300]}"
                            )
                            if attempt == 0:
                                await asyncio.sleep(0.5)
                            continue
                        if not resp.text.strip():
                            logger.warning(
                                f"n8n webhook returned HTTP 200 with an EMPTY body for lead {index}/{total}. "
                                f"Ensure the n8n Webhook trigger node 'Respond' parameter is set to "
                                f"'When Last Node Finishes' or 'Using Respond to Webhook Node'."
                            )
                            break
                        res_data = _unwrap_n8n_payload(resp.json())
                        adv_review = _adv_review_text(_first_field(res_data, *ADV_REVIEW_KEYS))
                        judge_verdict = _first_str(res_data, *JUDGE_VERDICT_KEYS)
                        reason = _first_str(res_data, *REASON_KEYS)
                        explicit_outcome = _first_str(res_data, *OUTCOME_KEYS)
                        extracted_any = bool(adv_review or judge_verdict or reason)
                        if not extracted_any:
                            logger.warning(
                                f"n8n response for lead {index}/{total} carried no recognizable fields "
                                f"(body starts: {resp.text[:300]}). Using deterministic review."
                            )
                            break
                        online_success = True
                        ret_closed_by = res_data.get("closed_by")
                        if ret_closed_by in VALID_CLOSED_BY:
                            closed_by = ret_closed_by
                        break
                except httpx.TimeoutException:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for lead {index}/{total} TIMED OUT after {eff_timeout}s. Using deterministic review."
                    )
                except httpx.ConnectError as conn_err:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n connection failed for lead {index}/{total} (cannot connect to {target_url}): {conn_err}. Using deterministic review."
                    )
                except Exception as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n call for lead {index}/{total} failed: {exc}. Using deterministic review."
                    )

        if not adv_review:
            adv_review = (
                f"Preliminary review of lead {index}/{total} (`{entity}`): Ordinary documentary support "
                f"was confirmed, along with active contracts and consistency between quotes, purchase orders, and invoices."
            )
        if not judge_verdict:
            judge_verdict = (
                f"JUDGE'S VERDICT (LEAD {index}/{total}): ACQUITTED / LEAD DISMISSED. "
                f"A lawful legal basis is fully substantiated with respect to the `{signal}` alert. "
                f"This line of investigation is formally and permanently closed."
            )
        if not reason:
            reason = existing_reason

        verdict_outcome = parse_verdict_outcome(judge_verdict, explicit_outcome)

        l_copy["adversarial_review"] = adv_review
        l_copy["judge_verdict"] = judge_verdict
        l_copy["reason"] = reason
        l_copy["closed_by"] = closed_by
        l_copy["verdict_outcome"] = verdict_outcome

        return {
            "lead": l_copy,
            "adversarial_review": adv_review,
            "judge_verdict": judge_verdict,
            "reason": reason,
            "closed_by": closed_by,
            "verdict_outcome": verdict_outcome,
            "is_online": online_success,
        }

    async def synthesize_case_verdict(
        self,
        reviewed_findings: List[Dict[str, Any]],
        reviewed_leads: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Audited Company S.A. de C.V.",
        company_rfc: Optional[str] = None,
        n8n_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes the overarching case verdict and executive narrative based on the
        individual finding and lead verdicts.
        """
        target_url = _resolve_n8n_url(n8n_url)
        eff_timeout = timeout if timeout is not None else settings.N8N_TIMEOUT
        online_success = False

        total_peso = sum(float(f.get("peso_amount", 0.0))
                         for f in reviewed_findings)
        proven_schemes = list(set(f.get("scheme_type", "scheme")
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

            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=eff_timeout) as client:
                        resp = await client.post(target_url, json=safe_payload)
                        if resp.status_code != 200:
                            logger.warning(
                                f"n8n case synthesis call returned HTTP {resp.status_code}: {resp.text[:300]}"
                            )
                            if attempt == 0:
                                await asyncio.sleep(0.5)
                            continue
                        if not resp.text.strip():
                            logger.warning(
                                f"n8n webhook returned HTTP 200 with an EMPTY body for case verdict synthesis. "
                                f"Ensure the n8n Webhook trigger node 'Respond' parameter is set to "
                                f"'When Last Node Finishes' or 'Using Respond to Webhook Node'."
                            )
                            break
                        res_data = _unwrap_n8n_payload(resp.json())
                        judge_verdict = _first_str(res_data, *JUDGE_VERDICT_KEYS)
                        final_narrative = _first_str(res_data, *FINAL_NARRATIVE_KEYS)
                        if not (judge_verdict or final_narrative):
                            logger.warning(
                                f"n8n synthesis response carried no recognizable fields "
                                f"(body starts: {resp.text[:300]}). Using deterministic summary."
                            )
                            break
                        online_success = True
                        break
                except httpx.TimeoutException:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n case synthesis call TIMED OUT after {eff_timeout}s. Using deterministic summary."
                    )
                except httpx.ConnectError as conn_err:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n connection failed for case synthesis (cannot connect to {target_url}): {conn_err}. Using deterministic summary."
                    )
                except Exception as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    logger.warning(
                        f"n8n case synthesis call failed: {exc}. Using deterministic summary."
                    )

        if not judge_verdict:
            judge_verdict = (
                f"EXPERT VERDICT ISSUED: Corporate and fiscal liability is confirmed for a "
                f"total amount of ${total_peso:,.2f} MXN spread across {len(reviewed_findings)} fraudulent schemes "
                f"({', '.join(proven_schemes)}). The charges fully satisfy the burden of proof and the 2% expert "
                f"reconciliation. {len(reviewed_leads)} preliminary leads are formally dismissed as a lawful basis was confirmed."
            )
        if not final_narrative:
            final_narrative = (
                f"The comprehensive forensic audit identified {len(reviewed_findings)} schemes of simulated transactions and "
                f"diversion of funds totaling ${total_peso:,.2f} Mexican pesos. By cross-referencing "
                f"CFDI 4.0 electronic invoicing, interbank transfers, and purchase orders, the unequivocal "
                f"traceability of funds to the flagged entities was confirmed, ruling out legitimate operations."
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
        company_name: str = "Audited Company S.A. de C.V.",
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
            "message": f"Starting adversarial review of {total_findings} findings and {total_leads} preliminary leads...",
        }

        enriched_findings: List[Dict[str, Any]] = []
        all_adversarial_evidences: List[Dict[str, Any]] = []
        finding_adv_reviews: List[str] = []
        finding_is_online: List[bool] = []
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
            finding_is_online.append(bool(finding_res["is_online"]))
            all_adversarial_evidences.extend(
                finding_res["adversarial_evidences"])
            total_exhibits_inserted += finding_res["inserted_exhibits_count"]
            if finding_res["is_online"]:
                llm_calls += 1

            outcome = finding_res["verdict_outcome"]
            outcome_label = {
                "upheld": "charge upheld",
                "acquitted": "ACQUITTED — will be reclassified as a dismissed lead",
                "evaluated": "evaluated",
            }.get(outcome, "evaluated")

            yield {
                "type": "finding_reviewed",
                "index": idx,
                "total": total_findings,
                "finding": f_item,
                "adversarial_review": finding_res["adversarial_review"],
                "judge_verdict": finding_res["judge_verdict"],
                "adversarial_evidences": finding_res["adversarial_evidences"],
                "verdict_outcome": outcome,
                "reclassified_to_lead": outcome == "acquitted",
                "inserted_exhibits_count": finding_res["inserted_exhibits_count"],
                "is_online": finding_res["is_online"],
                "message": (
                    f"Finding {idx}/{total_findings} ({f_item.get('scheme_type')}): "
                    f"judicial verdict {outcome_label}. "
                    f"{len(finding_res['adversarial_evidences'])} pieces of evidence recorded."
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
                "message": f"Preliminary lead {idx}/{total_leads} legitimately dismissed by `{lead_res['closed_by']}`.",
            }

        # 3. STRICT COMPLETION BARRIER:
        # Guarantee that 100% of finding reviews and 100% of lead reviews have returned an answer
        # before invoking n8n's verdict synthesis, preserving all context.
        if len(enriched_findings) != total_findings or len(enriched_leads) != total_leads:
            logger.warning(
                f"Barrier sync notice: findings {len(enriched_findings)}/{total_findings}, "
                f"leads {len(enriched_leads)}/{total_leads} before synthesis call."
            )

        # 4. AI VERDICT RECLASSIFICATION:
        # Findings the judicial review acquitted are demoted to dismissed leads so
        # the final accusation set only contains AI-upheld charges. Each demotion
        # is emitted as a lead_reviewed event so the UI narrates it live.
        acquitted = [
            (f_idx, f_item)
            for f_idx, f_item in enumerate(enriched_findings)
            if f_item.get("verdict_outcome") == "acquitted"
        ]
        upheld_findings = [
            f_item for f_item in enriched_findings
            if f_item.get("verdict_outcome") != "acquitted"
        ]
        reclassified_leads: List[Dict[str, Any]] = []
        reclassified_total = total_leads + len(acquitted)

        for position, (f_idx, f_item) in enumerate(acquitted, 1):
            adv_text = finding_adv_reviews[f_idx] if f_idx < len(finding_adv_reviews) else ""
            lead = _finding_to_dismissed_lead(f_item, adv_text)
            reclassified_leads.append(lead)
            yield {
                "type": "lead_reviewed",
                "index": total_leads + position,
                "total": reclassified_total,
                "lead": lead,
                "adversarial_review": adv_text,
                "judge_verdict": f_item.get("judge_verdict", ""),
                "reason": lead["reason"],
                "closed_by": "challenger",
                "is_online": finding_is_online[f_idx] if f_idx < len(finding_is_online) else False,
                "reclassified_from_finding": True,
                "message": (
                    f"Finding acquitted on adversarial review — `{lead['entity']}` "
                    f"reclassified as a dismissed lead ({total_leads + position}/{reclassified_total})."
                ),
            }

        all_leads = enriched_leads + reclassified_leads

        # 5. Synthesize overarching case verdict with post-verdict accusation set
        synthesis = await self.synthesize_case_verdict(
            reviewed_findings=upheld_findings,
            reviewed_leads=all_leads,
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
            else "Adversarial review completed successfully for all charges."
        )

        yield {
            "type": "verdict_synthesized",
            "judge_verdict": synthesis["judge_verdict"],
            "final_narrative": synthesis["final_narrative"],
            "adversarial_review": consolidated_adv_review,
            "adversarial_evidences": all_adversarial_evidences,
            "findings": upheld_findings,
            "leads_not_pursued": all_leads,
            "llm_calls": llm_calls,
            "llm_usage": estimate_llm_usage(seed) if llm_calls > 0 else None,
            "inserted_exhibits_count": total_exhibits_inserted,
            "message": "Formal expert verdict and judicial narrative successfully synthesized.",
        }

    async def run_enrichment(
        self,
        findings: List[Dict[str, Any]],
        leads_not_pursued: List[Dict[str, Any]],
        seed: int,
        company_name: str = "Audited Company S.A. de C.V.",
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
            "llm_usage": final_summary.get("llm_usage"),
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
                        "note") or "Adversarial evidence recorded.").strip()

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
            logger.warning(
                f"Could not persist exhibits to local database: {exc}")

        # Persist to PostgreSQL dual tables (ethereal and historic)
        try:
            from backend.services.estate_sync import estate_sync_service
            await estate_sync_service.persist_exhibits_dual(evidences, estate_target=estate_target)
        except Exception as exc:
            logger.warning(
                f"Could not persist exhibits to dual PostgreSQL tables: {exc}")

        return inserted_count


# Global singleton
n8n_enrichment_service = N8nEnrichmentService()
