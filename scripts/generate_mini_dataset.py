#!/usr/bin/env python3
"""Generate ultra-small forensic auditor datasets for fast testing and verification.

Creates:
- mini_dataset_2x2 (2 findings, 2 leads, minimal baseline)
- mini_dataset_3x3 (3 findings, 3 leads, minimal baseline)

Each dataset includes:
- estate.db (SQLite database conforming to estate_schema.sql)
- submission.json (Official submission schema, verified with validate_format.py)
- ground_truth.json (Official ground truth schema)
- case_file.json (Rich case file for Next.js viewer /investigate)
- csv/ (Export of all 8 tables as CSV files)
"""
from __future__ import annotations

import csv
import json
import os
import pathlib
import sqlite3
import sys

# Ensure repository root and student-materials are in sys.path
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
STUDENT_MATERIALS_DIR = ROOT_DIR / "student-materials" / "forensic-auditor"

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(STUDENT_MATERIALS_DIR))

from scripts.seed_estate import EstateSeeder, load_config
import validate_format


def export_sqlite_to_csv(db_path: str, csv_dir: str) -> None:
    """Exports all non-internal tables from an SQLite database to CSV files."""
    out_dir = pathlib.Path(csv_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]

    for table in tables:
        rows = cursor.execute(f"SELECT * FROM {table}").fetchall()
        csv_file = out_dir / f"{table}.csv"
        if rows:
            headers = rows[0].keys()
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in rows:
                    writer.writerow([r[h] for h in headers])
        else:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                f.write("")

    conn.close()


def enrich_case_file_for_viewer(
    sub_data: dict,
    estate_db_path: str,
    seed: int,
    company_name: str = "Industrias Corporativas del Norte SA de CV",
    company_rfc: str = "EMP920101AB1",
) -> dict:
    """Enriches a bare submission JSON into a full CaseFileDocument for the Next.js viewer."""
    findings = sub_data.get("findings", [])
    leads = sub_data.get("leads_not_pursued", [])

    total_exposure = sum(f.get("peso_amount", 0.0) for f in findings)

    # Gather entity names from estate vendors and employees
    entity_names = {
        f"RFC:{company_rfc}": company_name,
        company_rfc: company_name,
    }

    if os.path.exists(estate_db_path):
        conn = sqlite3.connect(estate_db_path)
        conn.row_factory = sqlite3.Row
        for v in conn.execute("SELECT rfc, legal_name FROM vendors").fetchall():
            entity_names[f"RFC:{v['rfc']}"] = v["legal_name"]
            entity_names[v["rfc"]] = v["legal_name"]
        for e in conn.execute("SELECT emp_id, name, role FROM employees").fetchall():
            entity_names[f"EMP:{e['emp_id']}"] = f"{e['name']} ({e['role']})"
            entity_names[e["emp_id"]] = f"{e['name']} ({e['role']})"
        conn.close()

    enriched_findings = []
    for i, f in enumerate(findings):
        finding_id = f"F-{i+1:02d}"
        f_copy = dict(f)
        f_copy["finding_id"] = finding_id

        # Rule detail mapping
        st = f.get("scheme_type")
        if st == "phantom_vendor":
            f_copy["rule_detail"] = {
                "code": "SAT_ART_69B",
                "authority": "Servicio de Administración Tributaria (SAT)",
                "article": "Artículo 69-B del Código Fiscal de la Federación",
                "legal_text_citation": "Las operaciones amparadas por comprobantes fiscales emitidos por contribuyentes listados como definitivos se consideran inexistentes para efectos fiscales.",
            }
            f_copy["adversarial_review"] = {
                "reviewer_agent_role": "challenger",
                "challenger_argument": "El proveedor emitió facturas con sello digital vigente y los pagos salieron formalmente de la cuenta corporativa.",
                "why_finding_held": "El proveedor carece de infraestructura, personal y activos comprobables; figura en la lista definitiva del 69-B del SAT y no existe entregable material del servicio.",
            }
        elif st == "kickback":
            f_copy["rule_detail"] = {
                "code": "CPF_ART_222",
                "authority": "Código Penal Federal / Control Interno",
                "article": "Artículo 222 (Cohecho) y Art. 388 (Administración Fraudulenta)",
                "legal_text_citation": "Se sanciona al colaborador o administrador que reciba beneficios económicos directos de proveedores como contraprestación por la asignación de contratos u órdenes de compra.",
            }
            f_copy["adversarial_review"] = {
                "reviewer_agent_role": "challenger",
                "challenger_argument": "La transferencia personal del proveedor hacia el empleado podría responder a un préstamo mercantil privado entre particulares.",
                "why_finding_held": "La transferencia ocurrió inmediatamente después de la liquidación de la orden de compra y representa un porcentaje exacto de la operación corporativa sin contrato de mutuo.",
            }
        elif st == "round_tripping":
            f_copy["rule_detail"] = {
                "code": "LFPIORPI_ART_17",
                "authority": "UIF / SHCP - LFPIORPI",
                "article": "Artículo 17 de la LFPIORPI y Código Penal Federal Art. 400-Bis",
                "legal_text_citation": "Simulación de dispersión y retorno circular de activos financieros sin propósito mercantil legítimo para falsear liquidez o disimular el origen de fondos.",
            }
            f_copy["adversarial_review"] = {
                "reviewer_agent_role": "challenger",
                "challenger_argument": "El retorno de capital fue registrado contablemente como una devolución y cancelación de anticipos entre empresas afiliadas.",
                "why_finding_held": "El ciclo se completó en un lapso menor a 48 horas a través de dos empresas fachada reteniendo únicamente un 2% de comisión de tránsito, sin actividad comercial real.",
            }

        # Build reconciliation object
        claimed = float(f.get("peso_amount", 0.0))
        f_copy["reconciliation"] = {
            "claimed_pesos": claimed,
            "exhibits_sum": claimed,
            "variance_percentage": 0.0,
            "matched_table": "invoices" if st != "kickback" else "purchase_orders",
            "per_table_breakdown": [
                {"table": "invoices", "subtotal": claimed},
                {"table": "bank_txns", "subtotal": claimed},
            ],
        }
        enriched_findings.append(f_copy)

    enriched_leads = []
    for l in leads:
        l_copy = dict(l)
        if "closure_category" not in l_copy:
            l_copy["closure_category"] = "materiality_verified"
        enriched_leads.append(l_copy)

    case_file = {
        "seed": seed,
        "header": {
            "company": company_name,
            "company_rfc": company_rfc,
            "audit_period": {"start": "2025-01-01", "end": "2026-03-31"},
        },
        "executive_summary": {
            "plain_narrative": (
                f"Auditoría forense sobre {company_name}. Se detectaron {len(findings)} hallazgos confirmados "
                f"con una exposición total estimada en ${total_exposure:,.2f} MXN. Se analizaron y descartaron "
                f"{len(leads)} alertas sospechosas tras constatar su respaldo documental y comercial."
            )
        },
        "entity_names": entity_names,
        "findings": enriched_findings,
        "leads_not_pursued": enriched_leads,
        "run_metadata": sub_data.get(
            "run_metadata",
            {
                "llm_calls": 8,
                "mxn_cost": 2.45,
                "wall_clock_seconds": 1.15,
                "cost_by_role": {"investigator": 1.5, "challenger": 0.65, "validator": 0.3},
                "deterministic": True,
            },
        ),
        "method_and_limits": {
            "architecture_summary": "Ingesta de datos contables y bancarios, aplicación de detectores deterministas de topología de grafos (NetworkX) y verificación forense con agentes adversarial y validador.",
            "out_of_scope": [
                "Nómina física fuera de las transferencias registradas en empleados.",
                "Comunicaciones no documentadas por mensajería privada.",
            ],
            "undetectable_fraud_types": [
                "Pagos en efectivo fuera del sistema financiero bancario.",
                "Sobornos liquidados mediante transferencias offshore no declaradas.",
            ],
            "reproducibility_steps": [
                f"Ejecutar seeder con semilla {seed}.",
                "Validar con validate_format.py --submission submission.json --estate estate.db",
            ],
        },
    }

    return case_file


def generate_dataset(
    name: str,
    schemes_cfg: dict,
    decoys_cfg: dict,
    seed: int = 42,
    output_base_dir: str = "data",
) -> dict:
    """Generates a complete dataset with estate, ground truth, submission, case file, and CSVs."""
    target_dir = pathlib.Path(output_base_dir) / name
    target_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(target_dir / "estate.db")
    gt_path = str(target_dir / "ground_truth.json")
    sub_path = str(target_dir / "submission.json")
    case_path = str(target_dir / "case_file.json")
    csv_dir = str(target_dir / "csv")

    base_config = load_config(None)
    cfg = json.loads(json.dumps(base_config))

    cfg["general"]["seed"] = seed
    cfg["general"]["output_db_path"] = db_path
    cfg["general"]["ground_truth_path"] = gt_path
    cfg["general"]["submission_path"] = sub_path

    # Minimal operations
    cfg["baseline_operations"] = {
        "num_normal_vendors": 3,
        "num_normal_employees": 5,
        "num_normal_invoices": 3,
        "num_normal_pos": 3,
        "num_normal_contracts": 1,
        "include_payroll": False,
    }

    cfg["schemes"] = schemes_cfg
    cfg["decoys"] = decoys_cfg

    print(f"\n=======================================================")
    print(f" Generating {name} (seed={seed})...")
    print(f"=======================================================")

    seeder = EstateSeeder(cfg, seed=seed)
    seeder.run()

    # Load submission and validate
    sub_data = json.loads(pathlib.Path(sub_path).read_text(encoding="utf-8"))
    struct_errs = validate_format.validate_structure(sub_data)
    estate_errs = validate_format.validate_against_estate(sub_data, db_path)

    if struct_errs or estate_errs:
        print(f"[ERROR] Validation failed for {name}:")
        for e in struct_errs + estate_errs:
            print(f"  - {e}")
        raise ValueError(f"Validation failed for {name}")

    print(f"  [OK] Validated 0 errors:")
    print(f"       - Findings count: {len(sub_data['findings'])}")
    print(f"       - Leads count:    {len(sub_data['leads_not_pursued'])}")

    # Enrich case file
    case_file = enrich_case_file_for_viewer(
        sub_data=sub_data,
        estate_db_path=db_path,
        seed=seed,
    )
    pathlib.Path(case_path).write_text(
        json.dumps(case_file, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [OK] Saved rich case_file.json ({len(case_file['findings'])} findings)")

    # Export CSVs
    export_sqlite_to_csv(db_path, csv_dir)
    print(f"  [OK] Exported 8 CSV tables to {csv_dir}")

    return {
        "name": name,
        "dir": str(target_dir),
        "db": db_path,
        "submission": sub_path,
        "ground_truth": gt_path,
        "case_file": case_path,
        "csv_dir": csv_dir,
        "findings_count": len(sub_data["findings"]),
        "leads_count": len(sub_data["leads_not_pursued"]),
    }


def main():
    # 1. Dataset 2x2: Ultra-minimal (2 findings, 2 leads)
    schemes_2x2 = {
        "phantom_vendor": {"enabled": True, "count": 1, "difficulty": "easy"},
        "kickback": {"enabled": True, "count": 1, "difficulty": "medium"},
        "round_tripping": {"enabled": False},
        "threshold_splitting": {"enabled": False},
        "revenue_inflation": {"enabled": False},
    }
    decoys_2x2 = {
        "enabled": True,
        "types": {
            "split_urgent_order": {"enabled": True},
            "high_value_board_approved": {"enabled": True},
            "high_velocity_logistics": {"enabled": False},
            "employee_relocation_bonus": {"enabled": False},
            "similar_name_clean_tax": {"enabled": False},
        },
    }
    res_2x2 = generate_dataset("mini_dataset_2x2", schemes_2x2, decoys_2x2, seed=202)

    # 2. Dataset 3x3: (3 findings, 3 leads)
    schemes_3x3 = {
        "phantom_vendor": {"enabled": True, "count": 1, "difficulty": "easy"},
        "kickback": {"enabled": True, "count": 1, "difficulty": "medium"},
        "round_tripping": {"enabled": True, "count": 1, "difficulty": "hard"},
        "threshold_splitting": {"enabled": False},
        "revenue_inflation": {"enabled": False},
    }
    decoys_3x3 = {
        "enabled": True,
        "types": {
            "split_urgent_order": {"enabled": True},
            "high_value_board_approved": {"enabled": True},
            "high_velocity_logistics": {"enabled": True},
            "employee_relocation_bonus": {"enabled": False},
            "similar_name_clean_tax": {"enabled": False},
        },
    }
    res_3x3 = generate_dataset("mini_dataset_3x3", schemes_3x3, decoys_3x3, seed=303)

    print("\n" + "=" * 60)
    print(" SUMMARY OF GENERATED MINI DATASETS")
    print("=" * 60)
    for res in [res_2x2, res_3x3]:
        print(f"Dataset: {res['name']}")
        print(f"  Directory:    {res['dir']}")
        print(f"  Findings:     {res['findings_count']}")
        print(f"  Leads:        {res['leads_count']}")
        print(f"  Files:        estate.db, submission.json, ground_truth.json, case_file.json, csv/")
    print("=" * 60)


if __name__ == "__main__":
    main()
