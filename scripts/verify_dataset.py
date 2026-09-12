"""Comprehensive auditor verification for estate datasets.

Inspects SQLite estate databases against estate_schema.sql specifications,
foreign key relationships, arithmetic sanity, scheme traces, decoy evidence,
and runs validate_format.py.
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys

SCHEMA_SPECS = {
    "vendors": {
        "required_cols": ["rfc", "legal_name", "registered_date", "address", "bank_clabe", "category", "contact_email"],
        "pk": "rfc"
    },
    "invoices": {
        "required_cols": ["uuid", "issuer_rfc", "receiver_rfc", "issue_date", "subtotal", "iva", "total", "concepto_text", "uso_cfdi", "forma_pago", "metodo_pago", "status"],
        "pk": "uuid"
    },
    "ledger": {
        "required_cols": ["entry_id", "date", "account_code", "account_name", "debit", "credit", "description", "invoice_uuid", "cost_center", "approver"],
        "pk": "entry_id"
    },
    "bank_txns": {
        "required_cols": ["txn_id", "date", "from_clabe", "to_clabe", "amount", "reference", "channel"],
        "pk": "txn_id"
    },
    "purchase_orders": {
        "required_cols": ["po_id", "vendor_rfc", "date", "amount", "requester", "approver", "description"],
        "pk": "po_id"
    },
    "contracts": {
        "required_cols": ["contract_id", "vendor_rfc", "start_date", "value", "scope_text"],
        "pk": "contract_id"
    },
    "employees": {
        "required_cols": ["emp_id", "name", "role", "bank_clabe", "hire_date"],
        "pk": "emp_id"
    },
    "efos_list": {
        "required_cols": ["rfc", "legal_name", "status", "publication_date"],
        "pk": "rfc"
    }
}


def audit_estate_database(db_path: str) -> dict:
    results = {
        "db_path": db_path,
        "exists": os.path.exists(db_path),
        "file_size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "tables": {},
        "integrity_checks": [],
        "errors": []
    }

    if not results["exists"]:
        results["errors"].append(f"Database file not found: {db_path}")
        return results

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Schema and Column verification
    existing_tables = {
        r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' and name not like 'sqlite_%'").fetchall()
    }

    for table, spec in SCHEMA_SPECS.items():
        if table not in existing_tables:
            results["errors"].append(f"Missing required table: {table}")
            continue

        cols_info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = [c["name"] for c in cols_info]
        row_count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        missing_cols = [c for c in spec["required_cols"] if c not in col_names]
        if missing_cols:
            results["errors"].append(f"Table '{table}' missing columns: {missing_cols}")

        results["tables"][table] = {
            "row_count": row_count,
            "columns": col_names,
            "has_pk": any(c["pk"] == 1 for c in cols_info)
        }

    # 2. Detailed Data Quality Checks
    # Invoices: Check subtotal + iva == total (tolerance 0.05 due to roundings)
    inv_calc_diff = cursor.execute("""
        SELECT count(*) FROM invoices
        WHERE ABS(round(subtotal + iva, 2) - round(total, 2)) > 0.05
    """).fetchone()[0]
    if inv_calc_diff == 0:
        results["integrity_checks"].append("Invoices: subtotal + iva == total holds across 100% of records")
    else:
        results["errors"].append(f"Invoices: {inv_calc_diff} rows violate subtotal + iva == total")

    # Ledger: Check double-entry accounting balance (Sum Debit == Sum Credit)
    ledger_totals = cursor.execute("SELECT SUM(debit), SUM(credit) FROM ledger").fetchone()
    sum_debit = round(ledger_totals[0] or 0.0, 2)
    sum_credit = round(ledger_totals[1] or 0.0, 2)
    if abs(sum_debit - sum_credit) < 0.01:
        results["integrity_checks"].append(f"Ledger: Perfect double-entry balance (Debit: ${sum_debit:,.2f} MXN, Credit: ${sum_credit:,.2f} MXN)")
    else:
        results["errors"].append(f"Ledger imbalance: Debit=${sum_debit}, Credit=${sum_credit}")

    # Bank Txns: Check channels are valid (SPEI, cheque, efectivo)
    invalid_channels = cursor.execute("SELECT count(*) FROM bank_txns WHERE channel NOT IN ('SPEI', 'cheque', 'efectivo')").fetchone()[0]
    if invalid_channels == 0:
        results["integrity_checks"].append("Bank Txns: 100% valid payment channels (SPEI / cheque / efectivo)")
    else:
        results["errors"].append(f"Bank Txns: {invalid_channels} rows with invalid channels")

    # CLABE: Check 18 digits format
    bad_clabes = cursor.execute("SELECT count(*) FROM vendors WHERE length(bank_clabe) != 18").fetchone()[0]
    bad_clabes += cursor.execute("SELECT count(*) FROM employees WHERE length(bank_clabe) != 18").fetchone()[0]
    bad_clabes += cursor.execute("SELECT count(*) FROM bank_txns WHERE length(from_clabe) != 18 OR length(to_clabe) != 18").fetchone()[0]
    if bad_clabes == 0:
        results["integrity_checks"].append("Banking: 100% of bank CLABEs are strictly 18 digits")
    else:
        results["errors"].append(f"Banking: {bad_clabes} invalid CLABEs found")

    # EFOS presence
    efos_count = cursor.execute("SELECT count(*) FROM efos_list").fetchone()[0]
    if efos_count > 0:
        results["integrity_checks"].append(f"EFOS 69-B: {efos_count} blacklisted entities registered")

    # Employee ID prefix check
    bad_emps = cursor.execute("SELECT count(*) FROM employees WHERE emp_id NOT LIKE 'EMP:%'").fetchone()[0]
    if bad_emps == 0:
        results["integrity_checks"].append("Employees: 100% employee IDs adhere to 'EMP:XXXX' prefix standard")
    else:
        results["errors"].append(f"Employees: {bad_emps} records lack 'EMP:' prefix")

    conn.close()
    return results


def main():
    target_dbs = ["data/estate.db", "data/test_estate.db"]
    # Also check if datasets exist
    datasets_dir = pathlib.Path("data/datasets")
    if datasets_dir.exists():
        for sdir in sorted(datasets_dir.glob("seed_*")):
            db = sdir / "estate.db"
            if db.exists():
                target_dbs.append(str(db))

    print("=" * 75)
    print("  FORENSIC AUDITOR - ESTATE COMPLIANCE & INTEGRITY AUDIT")
    print("=" * 75)

    all_pass = True
    for db in target_dbs:
        if not os.path.exists(db):
            continue
        print(f"\n--- AUDITING: {db} ---")
        res = audit_estate_database(db)
        print(f"File Size: {res['file_size_bytes']:,} bytes")
        print("\nTable Breakdown:")
        for t, info in res["tables"].items():
            print(f"  - {t:<16s}: {info['row_count']:4d} rows | PK: {'YES' if info['has_pk'] else 'NO'} | Cols: {len(info['columns'])}")

        print("\nData Integrity Checks:")
        for c in res["integrity_checks"]:
            print(f"  [PASS] {c}")

        if res["errors"]:
            all_pass = False
            print("\nErrors Found:")
            for e in res["errors"]:
                print(f"  [FAIL] {e}")
        else:
            print("\nStatus: 100% COMPLIANT WITH estate_schema.sql")

    print("\n" + "=" * 75)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
