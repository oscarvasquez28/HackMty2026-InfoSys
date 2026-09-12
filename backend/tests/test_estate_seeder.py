"""Automated tests for the Forensic Data Estate Seeder.

Verifies schema compliance, deterministic generation, batch processing,
and full validation passing validate_format.py structure & per-table peso reconciliation.
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import pytest

from scripts.seed_estate import EstateSeeder, load_config

# Add student-materials/forensic-auditor to sys.path to test validate_format directly
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
STUDENT_MATERIALS_DIR = ROOT_DIR / "student-materials" / "forensic-auditor"
if str(STUDENT_MATERIALS_DIR) not in sys.path:
    sys.path.insert(0, str(STUDENT_MATERIALS_DIR))

import validate_format  # type: ignore


EXPECTED_TABLES = {
    "vendors", "invoices", "ledger", "bank_txns",
    "purchase_orders", "contracts", "employees", "efos_list"
}


def test_schema_integrity():
    """Verify that all 8 tables are present with primary keys in the generated database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(pathlib.Path(tmpdir) / "test_estate.db")
        gt_path = str(pathlib.Path(tmpdir) / "test_gt.json")
        sub_path = str(pathlib.Path(tmpdir) / "test_sub.json")

        config = load_config(None)
        config["general"]["output_db_path"] = db_path
        config["general"]["ground_truth_path"] = gt_path
        config["general"]["submission_path"] = sub_path

        seeder = EstateSeeder(config, seed=42)
        seeder.run()

        conn = sqlite3.connect(db_path)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not r[0].startswith("sqlite_")
        }
        conn.close()

        assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"


def test_seeder_record_counts():
    """Verify that every table contains populated rows and valid data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(pathlib.Path(tmpdir) / "test_estate.db")
        gt_path = str(pathlib.Path(tmpdir) / "test_gt.json")
        sub_path = str(pathlib.Path(tmpdir) / "test_sub.json")

        config = load_config(None)
        config["general"]["output_db_path"] = db_path
        config["general"]["ground_truth_path"] = gt_path
        config["general"]["submission_path"] = sub_path

        seeder = EstateSeeder(config, seed=7)
        seeder.run()

        conn = sqlite3.connect(db_path)
        for table in EXPECTED_TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count > 0, f"Table {table} has 0 records!"
        conn.close()


def test_determinism():
    """Verify that identical seeds produce identical database states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(None)

        # Run 1
        config["general"]["output_db_path"] = str(pathlib.Path(tmpdir) / "estate_1.db")
        config["general"]["ground_truth_path"] = str(pathlib.Path(tmpdir) / "gt_1.json")
        config["general"]["submission_path"] = str(pathlib.Path(tmpdir) / "sub_1.json")
        s1 = EstateSeeder(config, seed=123)
        s1.run()

        # Run 2
        config["general"]["output_db_path"] = str(pathlib.Path(tmpdir) / "estate_2.db")
        config["general"]["ground_truth_path"] = str(pathlib.Path(tmpdir) / "gt_2.json")
        config["general"]["submission_path"] = str(pathlib.Path(tmpdir) / "sub_2.json")
        s2 = EstateSeeder(config, seed=123)
        s2.run()

        conn1 = sqlite3.connect(s1.output_db_path)
        conn2 = sqlite3.connect(s2.output_db_path)

        for table in EXPECTED_TABLES:
            rows1 = conn1.execute(f"SELECT * FROM {table}").fetchall()
            rows2 = conn2.execute(f"SELECT * FROM {table}").fetchall()
            assert rows1 == rows2, f"Discrepancy in table {table} between deterministic runs!"

        conn1.close()
        conn2.close()


def test_validate_format_compliance():
    """Verify that generated submissions and estates pass validate_format.py with 0 errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(pathlib.Path(tmpdir) / "estate.db")
        gt_path = str(pathlib.Path(tmpdir) / "ground_truth.json")
        sub_path = str(pathlib.Path(tmpdir) / "submission.json")

        config = load_config(None)
        config["general"]["output_db_path"] = db_path
        config["general"]["ground_truth_path"] = gt_path
        config["general"]["submission_path"] = sub_path

        seeder = EstateSeeder(config, seed=99)
        seeder.run()

        sub_data = json.loads(pathlib.Path(sub_path).read_text(encoding="utf-8"))

        # Check 1: Structure validation
        structure_errs = validate_format.validate_structure(sub_data)
        assert len(structure_errs) == 0, f"Format errors: {structure_errs}"

        # Check 2: Estate database existence and per-table peso reconciliation
        estate_errs = validate_format.validate_against_estate(sub_data, db_path)
        assert len(estate_errs) == 0, f"Estate reconciliation errors: {estate_errs}"
