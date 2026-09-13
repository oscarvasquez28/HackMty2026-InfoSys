"""
Evaluation Harness for Forensic AML Auditor.

Measures recall, false-accusation rate, peso reconciliation, and latency
across >= 5 held-out seeds, generating the exact Results table matching
results_table_template.csv.

RULES:
- Ground truth is strictly isolated in this evaluation harness and never imported into backend/
- Calculates Recall AND False-Accusation Rate across held-out seeds
- Verifies 2% peso reconciliation

Usage:
    python -m eval.eval_harness --seeds 101,102,103,104,105 --output tmp/results_eval.csv
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from eval.estate_generator import build_estate_database
from backend.services.deterministic_detectors import ForensicDetectorSuite
from backend.services.estate_connector import EstateConnector

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("forensic_auditor.eval")


async def evaluate_single_seed(
    seed: int,
    data_dir: Path,
) -> Dict[str, Any]:
    """Runs evaluation on a single seed estate against ground truth."""
    db_path = data_dir / f"estate_seed_{seed}.db"
    company_rfc = f"AUD{seed:04d}01AB1"[:13]

    # 1. Generate estate and ground truth
    gt_container = build_estate_database(
        seed=seed,
        db_path=db_path,
        company_rfc=company_rfc,
    )
    gt = gt_container["ground_truth"]

    # 2. Run detector suite
    connector = EstateConnector()
    suite = ForensicDetectorSuite(connector=connector)

    try:
        t0 = time.perf_counter()
        submission = await suite.run_forensic_detection_pipeline(
            estate_target=db_path,
            seed=seed,
        )
        wall_clock = time.perf_counter() - t0

        findings = submission.get("findings", [])
        meta = submission.get("run_metadata", {})

        # 3. Match schemes found
        schemes_planted = gt.get("schemes", [])
        schemes_found = 0

        for scheme in schemes_planted:
            s_type = scheme["type"]
            s_entities = set(scheme.get("entities", []))

            # Look for a matching finding
            matched = False
            for f in findings:
                if f.get("scheme_type") == s_type:
                    f_entities = set(f.get("entities", []))
                    if s_entities.intersection(f_entities):
                        matched = True
                        break
            if matched:
                schemes_found += 1

        recall_pct = (schemes_found / len(schemes_planted) * 100.0) if schemes_planted else 100.0

        # 4. Check decoy false accusations
        decoys_planted = gt.get("decoys", [])
        decoys_accused = 0
        all_accused_entities = set()
        for f in findings:
            for ent in f.get("entities", []):
                all_accused_entities.add(ent)

        for decoy in decoys_planted:
            d_ent = decoy["entity"]
            if d_ent in all_accused_entities:
                decoys_accused += 1

        false_accusation_rate_pct = (
            (decoys_accused / len(decoys_planted) * 100.0) if decoys_planted else 0.0
        )

        # 5. Peso reconciliation
        peso_claimed = sum(float(f.get("peso_amount", 0)) for f in findings)
        peso_actual = sum(float(s.get("peso_amount", 0)) for s in schemes_planted)
        diff = abs(peso_claimed - peso_actual)
        reconciles = "yes" if diff <= (0.02 * max(peso_actual, 1.0)) else "no"

        return {
            "seed": seed,
            "schemes_planted": len(schemes_planted),
            "schemes_found": schemes_found,
            "recall_pct": round(recall_pct, 1),
            "decoys_planted": len(decoys_planted),
            "decoys_accused": decoys_accused,
            "false_accusation_rate_pct": round(false_accusation_rate_pct, 1),
            "peso_claimed": round(peso_claimed, 2),
            "peso_actual": round(peso_actual, 2),
            "peso_reconciles": reconciles,
            "llm_calls": meta.get("llm_calls", 0),
            "mxn_cost": meta.get("mxn_cost", 0.0),
            "wall_clock_s": round(wall_clock, 3),
        }

    finally:
        await connector.dispose_all()


async def run_evaluation(
    seeds: List[int],
    output_csv: Path,
    data_dir: Path,
):
    data_dir.mkdir(parents=True, exist_ok=True)
    results = []

    print(f"\n[*] Commencing evaluation benchmark across {len(seeds)} seeds: {seeds}")
    print("-" * 78)

    for s in seeds:
        print(f"[*] Benchmarking Seed {s}...", end="", flush=True)
        res = await evaluate_single_seed(s, data_dir)
        results.append(res)
        print(f" Done! Found {res['schemes_found']}/{res['schemes_planted']} schemes, "
              f"{res['decoys_accused']}/{res['decoys_planted']} decoys accused, "
              f"in {res['wall_clock_s']}s.")

    # Calculate TOTAL row
    total_schemes_planted = sum(r["schemes_planted"] for r in results)
    total_schemes_found = sum(r["schemes_found"] for r in results)
    total_recall = (total_schemes_found / total_schemes_planted * 100.0) if total_schemes_planted else 0.0

    total_decoys_planted = sum(r["decoys_planted"] for r in results)
    total_decoys_accused = sum(r["decoys_accused"] for r in results)
    total_false_acc = (total_decoys_accused / total_decoys_planted * 100.0) if total_decoys_planted else 0.0

    total_claimed = sum(r["peso_claimed"] for r in results)
    total_actual = sum(r["peso_actual"] for r in results)
    total_reconciles = "yes" if abs(total_claimed - total_actual) <= (0.02 * max(total_actual, 1.0)) else "no"

    total_llm = sum(r["llm_calls"] for r in results)
    total_cost = sum(r["mxn_cost"] for r in results)
    total_wall_clock = sum(r["wall_clock_s"] for r in results)

    total_row = {
        "seed": "TOTAL",
        "schemes_planted": total_schemes_planted,
        "schemes_found": total_schemes_found,
        "recall_pct": round(total_recall, 1),
        "decoys_planted": total_decoys_planted,
        "decoys_accused": total_decoys_accused,
        "false_accusation_rate_pct": round(total_false_acc, 1),
        "peso_claimed": round(total_claimed, 2),
        "peso_actual": round(total_actual, 2),
        "peso_reconciles": total_reconciles,
        "llm_calls": total_llm,
        "mxn_cost": round(total_cost, 2),
        "wall_clock_s": round(total_wall_clock, 3),
    }

    fieldnames = [
        "seed",
        "schemes_planted",
        "schemes_found",
        "recall_pct",
        "decoys_planted",
        "decoys_accused",
        "false_accusation_rate_pct",
        "peso_claimed",
        "peso_actual",
        "peso_reconciles",
        "llm_calls",
        "mxn_cost",
        "wall_clock_s",
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
        writer.writerow(total_row)

    print()
    print("=" * 115)
    print("                              EVALUATION BENCHMARK RESULTS")
    print("=" * 115)
    header_fmt = "{:<6} | {:<15} | {:<13} | {:<10} | {:<14} | {:<14} | {:<10} | {:<10} | {:<12}"
    print(header_fmt.format(
        "Seed", "Schemes (F/P)", "Recall (%)", "Decoys (A/P)", "False Acc (%)", "Claimed MXN", "Reconciles", "LLM Calls", "Time (s)"
    ))
    print("-" * 115)

    row_fmt = "{:<6} | {:<15} | {:<13.1f} | {:<10} | {:<14.1f} | ${:<13,.2f} | {:<10} | {:<10} | {:<12.3f}"
    for r in results:
        print(row_fmt.format(
            str(r["seed"]),
            f"{r['schemes_found']} / {r['schemes_planted']}",
            r["recall_pct"],
            f"{r['decoys_accused']} / {r['decoys_planted']}",
            r["false_accusation_rate_pct"],
            r["peso_claimed"],
            r["peso_reconciles"],
            r["llm_calls"],
            r["wall_clock_s"],
        ))
    print("=" * 115)
    print(row_fmt.format(
        str(total_row["seed"]),
        f"{total_row['schemes_found']} / {total_row['schemes_planted']}",
        total_row["recall_pct"],
        f"{total_row['decoys_accused']} / {total_row['decoys_planted']}",
        total_row["false_accusation_rate_pct"],
        total_row["peso_claimed"],
        total_row["peso_reconciles"],
        total_row["llm_calls"],
        total_row["wall_clock_s"],
    ))
    print("=" * 115)
    print(f"[+] Output CSV written to: {output_csv.resolve()}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Forensic Auditor Multi-Seed Benchmark & Evaluation Harness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--seeds",
        default="101,102,103,104,105",
        help="Comma-separated list of >= 5 held-out seeds to benchmark",
    )
    parser.add_argument(
        "--output",
        default="tmp/results_eval.csv",
        help="Path to output CSV results file",
    )
    parser.add_argument(
        "--data-dir",
        default="eval/generated_estates",
        help="Directory to store generated SQLite estates",
    )

    args = parser.parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    asyncio.run(
        run_evaluation(
            seeds=seeds,
            output_csv=Path(args.output),
            data_dir=Path(args.data_dir),
        )
    )


if __name__ == "__main__":
    main()

