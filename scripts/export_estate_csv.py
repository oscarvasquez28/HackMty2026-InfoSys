#!/usr/bin/env python3
"""
Exports all 8 tables from an SQLite data estate database into individual CSV files.

Usage:
    python scripts/export_estate_csv.py --db tmp/test_estate.db --output-dir data/csv_estate
"""
import argparse
from pathlib import Path
import sqlite3
import polars as pl

ESTATE_TABLES = [
    "vendors",
    "invoices",
    "ledger",
    "bank_txns",
    "purchase_orders",
    "contracts",
    "employees",
    "efos_list",
]

def export_db_to_csv(db_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    
    print(f"[*] Exporting tables from {db_path} to {output_dir}/ ...")
    exported = 0
    for table in ESTATE_TABLES:
        try:
            df = pl.read_database(f"SELECT * FROM {table}", conn)
            out_file = output_dir / f"{table}.csv"
            df.write_csv(out_file)
            print(f"    [OK] {table:<16} -> {out_file.name} ({len(df)} rows)")
            exported += 1
        except Exception as e:
            print(f"    [SKIP] {table}: {e}")
            
    conn.close()
    print(f"[+] Done! Exported {exported} tables to {output_dir.resolve()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export estate SQLite database to CSV files")
    parser.add_argument("--db", default="tmp/test_estate.db", help="Path to estate SQLite DB")
    parser.add_argument("--output-dir", default="data/csv_estate", help="Directory to save CSVs")
    args = parser.parse_args()
    
    export_db_to_csv(Path(args.db), Path(args.output_dir))
