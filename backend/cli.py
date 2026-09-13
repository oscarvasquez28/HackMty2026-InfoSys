"""
Command-Line Interface (CLI) for Forensic Auditor AML Engine.

Provides zero-network deterministic execution over financial data estates,
generating:
1. case_file.md (with interactive Mermaid transaction flowcharts)
2. submission.json (strictly compliant with submission_schema.json)
3. Automated format validation and per-table peso reconciliation.

Usage:
    python -m backend.cli --estate /path/to/estate.db --seed 42 --output-dir ./output
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from backend.services.case_file_generator import CaseFileGenerator, case_file_generator
from backend.services.deterministic_detectors import ForensicDetectorSuite, detector_suite
from backend.services.estate_connector import EstateConnector, estate_connector

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("forensic_auditor.cli")


def print_banner():
    print()
    print("=" * 75)
    print("      POLAR FORENSIC AUDITOR — AUTONOMOUS FRAUD INVESTIGATION")
    print("=" * 75)


def print_summary(
    seed: int,
    findings_count: int,
    leads_count: int,
    total_mxn: float,
    wall_clock_s: float,
    llm_calls: int,
    mxn_cost: float,
    case_file_path: Path,
    submission_path: Path,
    validation_passed: Optional[bool] = None,
    validation_errors: Optional[list] = None,
    run_id: Optional[str] = None,
):
    print()
    print("+" + "-" * 73 + "+")
    print(f"|  {'AUDIT EXECUTION METRICS':<71}|")
    print("+" + "-" * 73 + "+")
    if run_id:
        print(f"|  * Run ID:                    {run_id:<44}|")
    print(f"|  * Seed:                      {seed:<44}|")
    print(f"|  * Proven Fraud Schemes:      {findings_count:<44}|")
    print(f"|  * Cleared Decoys / Leads:    {leads_count:<44}|")
    print(f"|  * Total Suspicious Volume:   ${total_mxn:>14,.2f} MXN{'':<26}|")
    print(f"|  * Wall-Clock Seconds:        {wall_clock_s:>14.3f} s{'':<28}|")
    print(f"|  * LLM API Calls:             {llm_calls:<44}|")
    print(f"|  * Estimated Model Cost:      ${mxn_cost:>14.2f} MXN{'':<26}|")
    print("+" + "-" * 73 + "+")
    print(f"|  * Case File Output:          {str(case_file_path):<44}|")
    print(f"|  * Submission JSON:           {str(submission_path):<44}|")
    if validation_passed is not None:
        status_str = "PASS (0 format/reconciliation errors)" if validation_passed else f"FAIL ({len(validation_errors or [])} errors)"
        print("+" + "-" * 73 + "+")
        print(f"|  * Format Validation:         {status_str:<44}|")
    print("+" + "-" * 73 + "+")
    print()

    if validation_errors:
        print("=" * 75)
        print("  VALIDATION ERROR DETAILS:")
        print("=" * 75)
        for err in validation_errors:
            print(f"  [ERROR] {err}")
        print("=" * 75)


async def run_audit(
    estate_path: str,
    seed: int = 1,
    company_rfc: Optional[str] = None,
    company_name: str = "Audited Company S.A. de C.V.",
    output_dir: str = ".",
    file_prefix: str = "",
    validate: bool = True,
    n8n_url: Optional[str] = None,
) -> int:
    """Executes the full forensic audit pipeline and exports artifacts."""
    start_time = time.perf_counter()
    p_estate = Path(estate_path).resolve()

    if not p_estate.exists() and not estate_path.startswith("postgresql"):
        print(f"\n[ERROR] Estate database file not found at: {p_estate}\n", file=sys.stderr)
        return 1

    connector = EstateConnector()
    suite = ForensicDetectorSuite(connector=connector)
    generator = CaseFileGenerator()

    try:
        # 1. Run pipeline
        print(f"\n[*] Connecting to data estate: {p_estate.name if p_estate.is_file() else estate_path}")
        print(f"[*] Executing 5 deterministic typologies with seed {seed}...")

        submission = await suite.run_forensic_detection_pipeline(
            estate_target=p_estate if p_estate.is_file() else estate_path,
            seed=seed,
            company_rfc=company_rfc,
        )

        # 2. n8n LLM Enrichment (or offline rule-based fallback)
        from backend.services.n8n_enrichment import n8n_enrichment_service
        enrichment = await n8n_enrichment_service.run_enrichment(
            findings=submission.get("findings", []),
            leads_not_pursued=submission.get("leads_not_pursued", []),
            seed=seed,
            company_name=company_name,
            company_rfc=company_rfc,
            estate_target=p_estate if p_estate.is_file() else estate_path,
            n8n_url=n8n_url,
        )

        submission["findings"] = enrichment.get("findings", submission.get("findings", []))
        submission["leads_not_pursued"] = enrichment.get("leads_not_pursued", submission.get("leads_not_pursued", []))
        submission["adversarial_review"] = enrichment.get("adversarial_review", "")
        submission["judge_verdict"] = enrichment.get("judge_verdict", "")
        submission["final_narrative"] = enrichment.get("final_narrative", "")
        submission["adversarial_evidences"] = enrichment.get("adversarial_evidences", [])

        if enrichment.get("llm_calls", 0) > 0:
            submission["run_metadata"]["llm_calls"] = enrichment["llm_calls"]
            submission["run_metadata"]["deterministic"] = False

        # 3. Update company RFC if provided
        if company_rfc:
            for f in submission.get("findings", []):
                if not f.get("entities"):
                    f["entities"] = [f"RFC:{company_rfc}"]

        # 4. Export artifacts
        out_dir = Path(output_dir).resolve()
        case_file_path, submission_path = generator.export_artifacts(
            submission_data=submission,
            output_dir=out_dir,
            file_prefix=file_prefix,
            company_name=company_name,
        )

        elapsed = time.perf_counter() - start_time
        meta = submission.get("run_metadata", {})
        meta["wall_clock_seconds"] = round(elapsed, 3)

        # Re-write submission with finalized wall_clock_seconds
        import json
        submission_path.write_text(json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")

        # 4. Compute totals
        findings = submission.get("findings", [])
        leads = submission.get("leads_not_pursued", [])
        total_mxn = sum(float(f.get("peso_amount", 0)) for f in findings)

        # 5. Format validation
        validation_passed = None
        validation_errors = []
        if validate and p_estate.is_file():
            try:
                from tmp.validate_format import validate_against_estate, validate_structure
                validation_errors = validate_structure(submission)
                validation_errors += validate_against_estate(submission, str(p_estate))
                validation_passed = (len(validation_errors) == 0)
            except Exception as v_err:
                logger.warning(f"Could not run validate_format: {v_err}")

        # 6. Display metrics
        print_summary(
            seed=seed,
            findings_count=len(findings),
            leads_count=len(leads),
            total_mxn=total_mxn,
            wall_clock_s=elapsed,
            llm_calls=meta.get("llm_calls", 0),
            mxn_cost=meta.get("mxn_cost", 0.0),
            case_file_path=case_file_path,
            submission_path=submission_path,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            run_id=meta.get("run_id"),
        )

        if validation_passed is False:
            return 1
        return 0

    finally:
        await connector.dispose_all()


def main():
    parser = argparse.ArgumentParser(
        description="Polar Forensic AML Auditor — Deterministic Estate Fraud Investigation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--estate",
        required=True,
        help="Path to SQLite data estate file (.db) or database URI",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed for deterministic audit reproducibility",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Target directory to write case_file.md and submission.json",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional file prefix for exported artifacts (default writes 'case_file.md' and 'submission.json')",
    )
    parser.add_argument(
        "--company-rfc",
        default=None,
        help="RFC of the audited entity",
    )
    parser.add_argument(
        "--company-name",
        default="Audited Company S.A. de C.V.",
        help="Legal name of the audited company",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Disable automatic format and per-table reconciliation validation",
    )
    parser.add_argument(
        "--n8n-url",
        default=None,
        help="Optional URL of n8n webhook for LLM narrative enrichment",
    )

    args = parser.parse_args()
    print_banner()

    exit_code = asyncio.run(
        run_audit(
            estate_path=args.estate,
            seed=args.seed,
            company_rfc=args.company_rfc,
            company_name=args.company_name,
            output_dir=args.output_dir,
            file_prefix=args.prefix,
            validate=not args.no_validate,
            n8n_url=args.n8n_url,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
