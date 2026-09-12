#!/usr/bin/env python3
"""Forensic Data Estate Seeder (estate_schema.sql)

Generates realistic Mexican corporate accounting, banking, and commercial data
strictly adhering to estate_schema.sql (8 tables). Plants the 5 forensic AML/fraud
schemes, realistic decoys with documentary innocence, and outputs isolated ground truth.

Usage:
    # Single dataset using config defaults:
    python scripts/seed_estate.py

    # Single dataset with custom seed and outputs:
    python scripts/seed_estate.py --seed 1 --output data/estate_1.db --ground-truth data/ground_truth_1.json

    # Batch generate 5 disjoint datasets for evaluation:
    python scripts/seed_estate.py --batch 5 --start-seed 101 --output-dir data/datasets

    # Use a custom config file:
    python scripts/seed_estate.py --config config/seeder_config.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import random
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

# Exact DDL adhering to student-materials/forensic-auditor/estate_schema.sql
ESTATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vendors (
    rfc             TEXT PRIMARY KEY,
    legal_name      TEXT,
    registered_date TEXT,
    address         TEXT,
    bank_clabe      TEXT,
    category        TEXT,
    contact_email   TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    uuid          TEXT PRIMARY KEY,
    issuer_rfc    TEXT,
    receiver_rfc  TEXT,
    issue_date    TEXT,
    subtotal      REAL,
    iva           REAL,
    total         REAL,
    concepto_text TEXT,
    uso_cfdi      TEXT,
    forma_pago    TEXT,
    metodo_pago   TEXT,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS ledger (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT,
    account_code TEXT,
    account_name TEXT,
    debit        REAL,
    credit       REAL,
    description  TEXT,
    invoice_uuid TEXT,
    cost_center  TEXT,
    approver     TEXT
);

CREATE TABLE IF NOT EXISTS bank_txns (
    txn_id     TEXT PRIMARY KEY,
    date       TEXT,
    from_clabe TEXT,
    to_clabe   TEXT,
    amount     REAL,
    reference  TEXT,
    channel    TEXT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id       TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    date        TEXT,
    amount      REAL,
    requester   TEXT,
    approver    TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    start_date  TEXT,
    value       REAL,
    scope_text  TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    emp_id     TEXT PRIMARY KEY,
    name       TEXT,
    role       TEXT,
    bank_clabe TEXT,
    hire_date  TEXT
);

CREATE TABLE IF NOT EXISTS efos_list (
    rfc              TEXT PRIMARY KEY,
    legal_name       TEXT,
    status           TEXT,
    publication_date TEXT
);
"""

# Realistic Mexican names, corporate suffixes, and locations
FIRST_NAMES = [
    "Alejandro", "Sofia", "Carlos", "Mariana", "Roberto", "Daniela", "Fernando",
    "Valeria", "Eduardo", "Gabriela", "Javier", "Camila", "Ricardo", "Paulina",
    "Mauricio", "Andrea", "Hector", "Lucia", "Guillermo", "Natalia", "Arturo",
    "Patricia", "Jorge", "Adriana", "Diego", "Claudia", "Manuel", "Lorena"
]

LAST_NAMES = [
    "Hernandez", "Garcia", "Martinez", "Lopez", "Gonzalez", "Perez", "Rodriguez",
    "Sanchez", "Ramirez", "Cruz", "Flores", "Gomez", "Morales", "Vazquez",
    "Jimenez", "Reyes", "Diaz", "Torres", "Gutierrez", "Ruiz", "Mendoza",
    "Aguilar", "Ortiz", "Moreno", "Castillo", "Alvarez", "Mendez", "Chavez"
]

CORP_WORDS = [
    "Soluciones", "Servicios", "Consultores", "Logistica", "Tecnologia", "Distribuidora",
    "Constructora", "Comercializadora", "Mantenimiento", "Sistemas", "Asesores", "Redes"
]

CORP_MODIFIERS = [
    "del Norte", "Integrales", "Avanzadas", "Especializados", "del Centro", "Nacionales",
    "Industriales", "Corporativos", "Estrategicos", "del Bajio", "Globales", "del Golfo"
]

CORP_TYPES = ["SA de CV", "SAPI de CV", "SC", "S de RL de CV"]

STREETS = [
    "Av. Constitucion", "Av. Insurgentes Sur", "Paseo de la Reforma", "Av. Lazaro Cardenas",
    "Blvd. Manuel Avila Camacho", "Av. Juarez", "Av. Hidalgo", "Av. Eugenio Garza Sada",
    "Calzada del Valle", "Av. Revolucion", "Av. Chapultepec", "Av. Americas"
]

CITIES = [
    "Monterrey, NL", "Ciudad de Mexico, CDMX", "Guadalajara, JAL", "San Pedro Garza Garcia, NL",
    "Queretaro, QRO", "Puebla, PUE", "Tijuana, BC", "Toluca, MEX", "Saltillo, COAH"
]

USO_CFDI_CATALOG = ["G01", "G02", "G03", "I01", "I02", "I04", "I08"]
METODO_PAGO_CATALOG = ["PUE", "PPD"]
FORMA_PAGO_CATALOG = ["03", "03", "03", "01", "02"]  # 03 = Transferencia SPEI (most common)


class MexicanDataGenerator:
    """Generates valid RFCs, 18-digit CLABEs, names, addresses and catalog values."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def generate_person_name(self) -> str:
        first = self.rng.choice(FIRST_NAMES)
        last1 = self.rng.choice(LAST_NAMES)
        last2 = self.rng.choice(LAST_NAMES)
        return f"{first} {last1} {last2}"

    def generate_company_name(self) -> str:
        word = self.rng.choice(CORP_WORDS)
        mod = self.rng.choice(CORP_MODIFIERS)
        corp_type = self.rng.choice(CORP_TYPES)
        return f"{word} {mod} {corp_type}"

    def generate_address(self) -> str:
        street = self.rng.choice(STREETS)
        num = self.rng.randint(100, 4500)
        city = self.rng.choice(CITIES)
        return f"{street} {num}, {city}"

    def generate_person_rfc(self, name: str, birth_date: Optional[datetime.date] = None) -> str:
        parts = name.upper().split()
        if len(parts) >= 3:
            first, last1, last2 = parts[0], parts[1], parts[2]
        else:
            first, last1, last2 = parts[0], parts[1], "X"
        letters = (last1[:2] + last2[:1] + first[:1]).ljust(4, "X")[:4]
        if not birth_date:
            birth_date = datetime.date(
                self.rng.randint(1975, 1998),
                self.rng.randint(1, 12),
                self.rng.randint(1, 28)
            )
        date_str = birth_date.strftime("%y%m%d")
        homoclave = "".join(self.rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=3))
        return f"{letters}{date_str}{homoclave}"

    def generate_company_rfc(self, name: str) -> str:
        words = [w for w in name.upper().split() if w not in ("DE", "LA", "DEL", "Y", "SA", "CV", "SC", "RL")]
        if len(words) >= 3:
            letters = (words[0][:1] + words[1][:1] + words[2][:1])
        elif len(words) == 2:
            letters = (words[0][:2] + words[1][:1])
        elif len(words) == 1:
            letters = words[0][:3]
        else:
            letters = "EMP"
        letters = letters.ljust(3, "X")[:3]
        year = self.rng.randint(95, 99) if self.rng.random() < 0.3 else self.rng.randint(10, 24)
        month = self.rng.randint(1, 12)
        day = self.rng.randint(1, 28)
        date_str = f"{year:02d}{month:02d}{day:02d}"
        homoclave = "".join(self.rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=3))
        return f"{letters}{date_str}{homoclave}"

    def generate_clabe(self, bank_code: Optional[str] = None) -> str:
        if not bank_code:
            bank_code = self.rng.choice(["002", "012", "014", "021", "044", "072", "127"])
        plaza = f"{self.rng.randint(100, 999):03d}"
        account = f"{self.rng.randint(10000000000, 99999999999):011d}"
        # 18th digit is checksum
        digits = bank_code + plaza + account
        weights = [3, 7, 1] * 5 + [3, 7]
        weighted_sum = sum(int(d) * w for d, w in zip(digits, weights))
        check_digit = (10 - (weighted_sum % 10)) % 10
        return f"{digits}{check_digit}"

    def random_date_in_range(self, start: datetime.date, end: datetime.date) -> datetime.date:
        delta = (end - start).days
        if delta <= 0:
            return start
        return start + datetime.timedelta(days=self.rng.randint(0, delta))


class EstateSeeder:
    """Generates an SQLite data estate adhering strictly to estate_schema.sql."""

    def __init__(self, config: Dict[str, Any], seed: Optional[int] = None):
        self.config = config
        self.seed = seed if seed is not None else config.get("general", {}).get("seed", 42)
        self.rng = random.Random(self.seed)
        self.generator = MexicanDataGenerator(self.rng)

        # Extraction of general configuration
        gen = config.get("general", {})
        self.output_db_path = gen.get("output_db_path", "data/estate.db")
        self.ground_truth_path = gen.get("ground_truth_path", "data/ground_truth.json")
        self.submission_path = gen.get("submission_path", "data/submission.json")

        audit = gen.get("audit_period", {})
        self.start_date = datetime.date.fromisoformat(audit.get("start_date", "2025-01-01"))
        self.end_date = datetime.date.fromisoformat(audit.get("end_date", "2026-03-31"))

        comp = gen.get("company", {})
        self.company_rfc = comp.get("rfc", "EMP920101AB1")
        self.company_name = comp.get("legal_name", "Industrias Corporativas del Norte SA de CV")
        self.company_clabe = comp.get("primary_clabe", "000000000000000099")

        # Database state collections
        self.vendors: List[Dict[str, Any]] = []
        self.invoices: List[Dict[str, Any]] = []
        self.ledger: List[Dict[str, Any]] = []
        self.bank_txns: List[Dict[str, Any]] = []
        self.purchase_orders: List[Dict[str, Any]] = []
        self.contracts: List[Dict[str, Any]] = []
        self.employees: List[Dict[str, Any]] = []
        self.efos_list: List[Dict[str, Any]] = []

        # Tracking for Ground Truth & Evaluation
        self.ground_truth_schemes: List[Dict[str, Any]] = []
        self.ground_truth_decoys: List[Dict[str, Any]] = []
        self.sample_findings: List[Dict[str, Any]] = []
        self.sample_leads_not_pursued: List[Dict[str, Any]] = []

        # Counter sequence trackers
        self.ledger_entry_id = 1
        self.invoice_seq = 1
        self.txn_seq = 1
        self.po_seq = 1
        self.contract_seq = 1

    def create_database(self, db_path: str) -> sqlite3.Connection:
        """Initialize SQLite database with exact schema."""
        path = pathlib.Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(str(path))
        conn.executescript(ESTATE_SCHEMA_SQL)
        conn.commit()
        return conn

    def _next_invoice_uuid(self) -> str:
        uid = f"INV-{self.invoice_seq:05d}"
        self.invoice_seq += 1
        return uid

    def _next_txn_id(self) -> str:
        tid = f"BNK-{self.txn_seq:05d}"
        self.txn_seq += 1
        return tid

    def _next_po_id(self) -> str:
        poid = f"PO-{self.po_seq:05d}"
        self.po_seq += 1
        return poid

    def _next_contract_id(self) -> str:
        cid = f"CTR-{self.contract_seq:05d}"
        self.contract_seq += 1
        return cid

    def _add_ledger_pair(
        self,
        date_str: str,
        debit_code: str,
        debit_name: str,
        credit_code: str,
        credit_name: str,
        amount: float,
        description: str,
        invoice_uuid: Optional[str] = None,
        cost_center: str = "CC-100 Operaciones",
        approver: str = "A. Auditor"
    ):
        """Creates balanced double-entry accounting records."""
        # Debit entry
        self.ledger.append({
            "entry_id": self.ledger_entry_id,
            "date": date_str,
            "account_code": debit_code,
            "account_name": debit_name,
            "debit": amount,
            "credit": 0.0,
            "description": description,
            "invoice_uuid": invoice_uuid,
            "cost_center": cost_center,
            "approver": approver
        })
        self.ledger_entry_id += 1

        # Credit entry
        self.ledger.append({
            "entry_id": self.ledger_entry_id,
            "date": date_str,
            "account_code": credit_code,
            "account_name": credit_name,
            "debit": 0.0,
            "credit": amount,
            "description": description,
            "invoice_uuid": invoice_uuid,
            "cost_center": cost_center,
            "approver": approver
        })
        self.ledger_entry_id += 1

    # -------------------------------------------------------------------------
    # Baseline Operations Generator
    # -------------------------------------------------------------------------
    def seed_baseline_operations(self):
        """Generates realistic normal commercial, banking, and accounting transactions."""
        ops = self.config.get("baseline_operations", {})
        num_vendors = ops.get("num_normal_vendors", 25)
        num_employees = ops.get("num_normal_employees", 20)
        num_invoices = ops.get("num_normal_invoices", 60)
        num_pos = ops.get("num_normal_pos", 40)
        num_contracts = ops.get("num_normal_contracts", 10)
        categories = ops.get("vendor_categories", ["Consultoria", "Mantenimiento", "Logistica"])

        # 1. Employees
        roles = [
            "Director General", "Director de Finanzas", "Gerente de Compras", "Contador General",
            "Auditor Interno", "Gerente de Logistica", "Jefe de Almacen", "Analista de Tesoreria",
            "Especialista de Sistemas", "Coordinador de Calidad", "Supervisor de Produccion",
            "Abogado Corporativo", "Gerente de Recursos Humanos", "Analista Contable"
        ]
        for i in range(1, num_employees + 1):
            emp_id = f"EMP:{i:04d}"
            name = self.generator.generate_person_name()
            role = roles[(i - 1) % len(roles)]
            clabe = self.generator.generate_clabe()
            hire_date = self.generator.random_date_in_range(
                datetime.date(2018, 1, 1),
                datetime.date(2024, 12, 31)
            ).isoformat()
            self.employees.append({
                "emp_id": emp_id,
                "name": name,
                "role": role,
                "bank_clabe": clabe,
                "hire_date": hire_date
            })

        # 2. Vendors
        for i in range(1, num_vendors + 1):
            vname = self.generator.generate_company_name()
            vrfc = self.generator.generate_company_rfc(vname)
            # Ensure uniqueness
            while any(v["rfc"] == vrfc for v in self.vendors):
                vrfc = self.generator.generate_company_rfc(vname + f" {i}")
            vcat = categories[(i - 1) % len(categories)]
            reg_date = self.generator.random_date_in_range(
                datetime.date(2019, 1, 1),
                datetime.date(2024, 6, 30)
            ).isoformat()
            clabe = self.generator.generate_clabe()
            email = f"contacto@{vrfc.lower()[:8]}.com.mx"
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": reg_date,
                "address": self.generator.generate_address(),
                "bank_clabe": clabe,
                "category": vcat,
                "contact_email": email
            })

        # 3. Long-term Contracts for top vendors
        for i in range(min(num_contracts, len(self.vendors))):
            vendor = self.vendors[i]
            cid = self._next_contract_id()
            cval = round(self.rng.uniform(300000.0, 1500000.0), 2)
            cstart = self.generator.random_date_in_range(
                datetime.date(2024, 1, 1),
                datetime.date(2025, 3, 1)
            ).isoformat()
            self.contracts.append({
                "contract_id": cid,
                "vendor_rfc": vendor["rfc"],
                "start_date": cstart,
                "value": cval,
                "scope_text": f"Contrato marco de prestacion de servicios en {vendor['category']} con entregables mensuales"
            })

        # 4. Normal Purchase Orders
        approvers = [e["name"] for e in self.employees if "Gerente" in e["role"] or "Director" in e["role"]]
        requesters = [e["name"] for e in self.employees]
        for i in range(num_pos):
            vendor = self.rng.choice(self.vendors)
            po_id = self._next_po_id()
            po_date = self.generator.random_date_in_range(self.start_date, self.end_date).isoformat()
            po_amt = round(self.rng.uniform(20000.0, 150000.0), 2)
            self.purchase_orders.append({
                "po_id": po_id,
                "vendor_rfc": vendor["rfc"],
                "date": po_date,
                "amount": po_amt,
                "requester": self.rng.choice(requesters),
                "approver": self.rng.choice(approvers),
                "description": f"Suministro ordinario de {vendor['category'].lower()} conforme a requisicion"
            })

        # 5. Normal Invoices, Ledger Entries, and Bank Transactions
        amt_range = ops.get("invoice_amount_range", {"min": 15000.0, "max": 180000.0})
        for i in range(num_invoices):
            vendor = self.rng.choice(self.vendors)
            inv_uuid = self._next_invoice_uuid()
            subtotal = round(self.rng.uniform(amt_range["min"], amt_range["max"]), 2)
            iva = round(subtotal * 0.16, 2)
            total = round(subtotal + iva, 2)
            inv_date = self.generator.random_date_in_range(self.start_date, self.end_date)
            date_str = inv_date.isoformat()

            self.invoices.append({
                "uuid": inv_uuid,
                "issuer_rfc": vendor["rfc"],
                "receiver_rfc": self.company_rfc,
                "issue_date": date_str,
                "subtotal": subtotal,
                "iva": iva,
                "total": total,
                "concepto_text": f"Servicios y suministros operativos de {vendor['category'].lower()}",
                "uso_cfdi": self.rng.choice(USO_CFDI_CATALOG),
                "forma_pago": self.rng.choice(FORMA_PAGO_CATALOG),
                "metodo_pago": self.rng.choice(METODO_PAGO_CATALOG),
                "status": "vigente"
            })

            # Double-entry ledger: Expense creation
            self._add_ledger_pair(
                date_str=date_str,
                debit_code="5000",
                debit_name="Gastos operativos",
                credit_code="2100",
                credit_name="Cuentas por pagar",
                amount=total,
                description=f"Provision factura {inv_uuid} {vendor['legal_name'][:30]}",
                invoice_uuid=inv_uuid,
                cost_center=self.rng.choice(["CC-100 Operaciones", "CC-200 Administracion", "CC-300 Logistica"]),
                approver=self.rng.choice(approvers)
            )

            # Bank settlement payment (85% paid within 15-45 days, 15% pending)
            if self.rng.random() < 0.85:
                pay_days = self.rng.randint(7, 30)
                pay_date = inv_date + datetime.timedelta(days=pay_days)
                if pay_date <= self.end_date:
                    pay_date_str = pay_date.isoformat()
                    txn_id = self._next_txn_id()
                    self.bank_txns.append({
                        "txn_id": txn_id,
                        "date": pay_date_str,
                        "from_clabe": self.company_clabe,
                        "to_clabe": vendor["bank_clabe"],
                        "amount": total,
                        "reference": f"Pago SPEI {inv_uuid}",
                        "channel": "SPEI"
                    })

                    # Double-entry ledger: Settlement
                    self._add_ledger_pair(
                        date_str=pay_date_str,
                        debit_code="2100",
                        debit_name="Cuentas por pagar",
                        credit_code="1100",
                        credit_name="Bancos e inversiones",
                        amount=total,
                        description=f"Liquidacion SPEI {txn_id} factura {inv_uuid}",
                        invoice_uuid=inv_uuid,
                        approver=self.rng.choice(approvers)
                    )

        # 6. Periodic Payroll bank transactions & ledger entries
        if ops.get("include_payroll", True):
            for emp in self.employees[:10]:
                pay_date = datetime.date(2026, 1, 31).isoformat()
                salary = round(self.rng.uniform(22000.0, 65000.0), 2)
                tid = self._next_txn_id()
                self.bank_txns.append({
                    "txn_id": tid,
                    "date": pay_date,
                    "from_clabe": self.company_clabe,
                    "to_clabe": emp["bank_clabe"],
                    "amount": salary,
                    "reference": f"Dispersion nomina quincenal {emp['emp_id']}",
                    "channel": "SPEI"
                })
                self._add_ledger_pair(
                    date_str=pay_date,
                    debit_code="5100",
                    debit_name="Sueldos y salarios operativos",
                    credit_code="1100",
                    credit_name="Bancos e inversiones",
                    amount=salary,
                    description=f"Nomina quincenal ordinaria {emp['name']}",
                    cost_center="CC-200 Administracion",
                    approver="Director de Finanzas"
                )

    # -------------------------------------------------------------------------
    # Scheme 1: Phantom Vendor (EFOS 69-B)
    # -------------------------------------------------------------------------
    def plant_scheme_phantom_vendor(self):
        cfg = self.config.get("schemes", {}).get("phantom_vendor", {})
        if not cfg.get("enabled", True):
            return

        for idx in range(cfg.get("count", 1)):
            scheme_id = f"S1_phantom_vendor_{idx + 1}"
            vname = "Servicios Empresariales Fantasma SA de CV"
            vrfc = f"EFOS{self.rng.randint(10, 99):02d}0101AA{idx + 1}"
            clabe = self.generator.generate_clabe()
            pub_date = "2025-11-15"
            status = cfg.get("efos_status", "definitivo")

            # 1. Insert in efos_list
            self.efos_list.append({
                "rfc": vrfc,
                "legal_name": vname,
                "status": status,
                "publication_date": pub_date
            })

            # 2. Insert in vendors
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2025-01-10",
                "address": "Calle Falsa 123, Monterrey, NL",
                "bank_clabe": clabe,
                "category": "Consultoria Estrategica",
                "contact_email": f"contacto@{vrfc.lower()}.mx"
            })

            # 3. Generate fraudulent invoices without contracts or legitimate deliverables
            inv_count = cfg.get("invoices_count", 2)
            invoices_created: List[Dict[str, Any]] = []
            txns_created: List[Dict[str, Any]] = []
            total_scheme_pesos = 0.0

            base_amounts = [92800.0, 46400.0] if inv_count == 2 else [
                round(self.rng.uniform(cfg.get("min_amount", 60000.0), cfg.get("max_amount", 120000.0)), 2)
                for _ in range(inv_count)
            ]

            for j, inv_total in enumerate(base_amounts):
                subtotal = round(inv_total / 1.16, 2)
                iva = round(inv_total - subtotal, 2)
                total = round(subtotal + iva, 2)
                total_scheme_pesos += total

                inv_uuid = self._next_invoice_uuid()
                inv_date = datetime.date(2026, 2, 10 + j * 12).isoformat()
                inv_obj = {
                    "uuid": inv_uuid,
                    "issuer_rfc": vrfc,
                    "receiver_rfc": self.company_rfc,
                    "issue_date": inv_date,
                    "subtotal": subtotal,
                    "iva": iva,
                    "total": total,
                    "concepto_text": cfg.get("service_concept", "Asesoria estrategica en optimizacion de infraestructura intangible"),
                    "uso_cfdi": "G03",
                    "forma_pago": "03",
                    "metodo_pago": "PUE",
                    "status": "vigente"
                }
                self.invoices.append(inv_obj)
                invoices_created.append(inv_obj)

                # Ledger record without formal PO sign-off
                self._add_ledger_pair(
                    date_str=inv_date,
                    debit_code="5000",
                    debit_name="Gastos operativos",
                    credit_code="2100",
                    credit_name="Cuentas por pagar",
                    amount=total,
                    description=f"Registro factura fantasma {inv_uuid}",
                    invoice_uuid=inv_uuid,
                    cost_center="CC-999 General",
                    approver="SIN_AUTORIZACION"
                )

                # Bank payment via SPEI
                pay_date = datetime.date(2026, 2, 14 + j * 12).isoformat()
                txn_id = self._next_txn_id()
                txn_obj = {
                    "txn_id": txn_id,
                    "date": pay_date,
                    "from_clabe": self.company_clabe,
                    "to_clabe": clabe,
                    "amount": total,
                    "reference": f"Liquidacion {inv_uuid}",
                    "channel": "SPEI"
                }
                self.bank_txns.append(txn_obj)
                txns_created.append(txn_obj)

                self._add_ledger_pair(
                    date_str=pay_date,
                    debit_code="2100",
                    debit_name="Cuentas por pagar",
                    credit_code="1100",
                    credit_name="Bancos e inversiones",
                    amount=total,
                    description=f"Transferencia SPEI a EFOS {txn_id}",
                    invoice_uuid=inv_uuid,
                    approver="SIN_AUTORIZACION"
                )

            # Record Ground Truth
            self.ground_truth_schemes.append({
                "scheme_id": scheme_id,
                "type": "phantom_vendor",
                "entities": [f"RFC:{vrfc}"],
                "supporting_invoices": [inv["uuid"] for inv in invoices_created],
                "supporting_txns": [txn["txn_id"] for txn in txns_created],
                "peso_amount": round(total_scheme_pesos, 2),
                "difficulty": cfg.get("difficulty", "easy")
            })

            # Sample Finding for validation
            exhibits = []
            for k, inv in enumerate(invoices_created):
                exhibits.append({
                    "exhibit_id": f"EX-{k+1:02d}",
                    "source_table": "invoices",
                    "record_id": inv["uuid"],
                    "note": f"Factura {inv['uuid']} expedida por proveedor fantasma con concepto intangible."
                })
            exhibits.append({
                "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                "source_table": "vendors",
                "record_id": vrfc,
                "note": f"Registro de proveedor fantasma {vrfc} sin infraestructura."
            })
            exhibits.append({
                "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                "source_table": "efos_list",
                "record_id": vrfc,
                "note": f"Listado definitivo publicado por el SAT bajo el Articulo 69-B del CFF."
            })
            for k, txn in enumerate(txns_created):
                exhibits.append({
                    "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                    "source_table": "bank_txns",
                    "record_id": txn["txn_id"],
                    "note": f"Transferencia SPEI {txn['txn_id']} por ${txn['amount']:,.2f} a la CLABE del EFOS."
                })

            money_trail = []
            for k, txn in enumerate(txns_created):
                money_trail.append({
                    "from": self.company_rfc,
                    "to": f"RFC:{vrfc}",
                    "amount": txn["amount"],
                    "date": txn["date"],
                    "exhibit_id": f"EX-{k+1:02d}"
                })

            self.sample_findings.append({
                "scheme_type": "phantom_vendor",
                "entities": [f"RFC:{vrfc}"],
                "rule_broken": "SAT Articulo 69-B del Codigo Fiscal de la Federacion (Operaciones Inexistentes)",
                "narrative": (
                    f"El proveedor {vrfc} fue publicado en la lista definitiva de EFOS del SAT conforme "
                    "al Articulo 69-B del CFF por simular operaciones y carecer de activos, personal o infraestructura. "
                    f"La empresa liquido ${total_scheme_pesos:,.2f} MXN por supuestos servicios de consultoria intangible "
                    "sin contratos ni evidencia material de entrega."
                ),
                "peso_amount": round(total_scheme_pesos, 2),
                "confidence": "proven",
                "money_trail": money_trail,
                "exhibits": exhibits
            })

    # -------------------------------------------------------------------------
    # Scheme 2: Kickback Scheme
    # -------------------------------------------------------------------------
    def plant_scheme_kickback(self):
        cfg = self.config.get("schemes", {}).get("kickback", {})
        if not cfg.get("enabled", True):
            return

        for idx in range(cfg.get("count", 1)):
            scheme_id = f"S2_kickback_{idx + 1}"
            # Select or create an accomplice employee
            corrupt_emp = self.employees[4]  # e.g. Gerente de Compras
            emp_id = corrupt_emp["emp_id"]

            vname = "Soluciones Industriales Coludidas SA de CV"
            vrfc = f"KICK{self.rng.randint(10, 99):02d}0202BB{idx + 1}"
            vendor_clabe = self.generator.generate_clabe()

            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2024-03-15",
                "address": "Av. Parque Industrial 400, Monterrey, NL",
                "bank_clabe": vendor_clabe,
                "category": "Mantenimiento Industrial",
                "contact_email": f"ventas@{vrfc.lower()}.mx"
            })

            # PO approved by the accomplice employee
            total_peso = cfg.get("invoice_amount", 125000.0)
            subtotal = round(total_peso / 1.16, 2)
            iva = round(total_peso - subtotal, 2)
            total = round(subtotal + iva, 2)

            po_id = self._next_po_id()
            self.purchase_orders.append({
                "po_id": po_id,
                "vendor_rfc": vrfc,
                "date": "2026-02-01",
                "amount": total,
                "requester": corrupt_emp["name"],
                "approver": corrupt_emp["name"],
                "description": "Servicios de mantenimiento correctivo de alta prioridad"
            })

            # Invoice
            inv_uuid = self._next_invoice_uuid()
            inv_date = "2026-02-05"
            inv_obj = {
                "uuid": inv_uuid,
                "issuer_rfc": vrfc,
                "receiver_rfc": self.company_rfc,
                "issue_date": inv_date,
                "subtotal": subtotal,
                "iva": iva,
                "total": total,
                "concepto_text": "Mantenimiento preventivo mayor y calibracion de turbinas",
                "uso_cfdi": "G03",
                "forma_pago": "03",
                "metodo_pago": "PUE",
                "status": "vigente"
            }
            self.invoices.append(inv_obj)

            # Company pays vendor
            pay_txn_id = self._next_txn_id()
            pay_date = "2026-02-08"
            self.bank_txns.append({
                "txn_id": pay_txn_id,
                "date": pay_date,
                "from_clabe": self.company_clabe,
                "to_clabe": vendor_clabe,
                "amount": total,
                "reference": f"Pago factura {inv_uuid}",
                "channel": "SPEI"
            })

            # Vendor kicks back 20% to employee's bank_clabe 2 days later
            kickback_pct = cfg.get("kickback_percentage", 0.20)
            kickback_amount = round(total * kickback_pct, 2)
            kickback_txn_id = self._next_txn_id()
            kick_date = "2026-02-10"
            self.bank_txns.append({
                "txn_id": kickback_txn_id,
                "date": kick_date,
                "from_clabe": vendor_clabe,
                "to_clabe": corrupt_emp["bank_clabe"],
                "amount": kickback_amount,
                "reference": "Comision retorno honorarios",
                "channel": "SPEI"
            })

            # Ground truth
            self.ground_truth_schemes.append({
                "scheme_id": scheme_id,
                "type": "kickback",
                "entities": [f"RFC:{vrfc}", emp_id],
                "supporting_invoices": [inv_uuid],
                "supporting_txns": [pay_txn_id, kickback_txn_id],
                "peso_amount": total,
                "difficulty": cfg.get("difficulty", "medium")
            })

            # Sample Finding
            exhibits = [
                {
                    "exhibit_id": "EX-01",
                    "source_table": "invoices",
                    "record_id": inv_uuid,
                    "note": f"Factura sobrevaluada {inv_uuid} emitida por {vrfc} por ${total:,.2f} MXN."
                },
                {
                    "exhibit_id": "EX-02",
                    "source_table": "purchase_orders",
                    "record_id": po_id,
                    "note": f"Orden de compra autorizada unilateralmente por {corrupt_emp['name']} ({emp_id})."
                },
                {
                    "exhibit_id": "EX-03",
                    "source_table": "employees",
                    "record_id": emp_id,
                    "note": f"Ficha de empleado de {corrupt_emp['name']} identificando su CLABE bancaria personal."
                },
                {
                    "exhibit_id": "EX-04",
                    "source_table": "bank_txns",
                    "record_id": pay_txn_id,
                    "note": f"Pago corporativo SPEI {pay_txn_id} por ${total:,.2f} a la cuenta del proveedor."
                },
                {
                    "exhibit_id": "EX-05",
                    "source_table": "bank_txns",
                    "record_id": kickback_txn_id,
                    "note": f"Retorno ilicito (kickback) SPEI {kickback_txn_id} de ${kickback_amount:,.2f} a la cuenta personal del empleado."
                }
            ]

            money_trail = [
                {
                    "from": self.company_rfc,
                    "to": f"RFC:{vrfc}",
                    "amount": total,
                    "date": pay_date,
                    "exhibit_id": "EX-01"
                },
                {
                    "from": f"RFC:{vrfc}",
                    "to": emp_id,
                    "amount": kickback_amount,
                    "date": kick_date,
                    "exhibit_id": "EX-05"
                }
            ]

            self.sample_findings.append({
                "scheme_type": "kickback",
                "entities": [f"RFC:{vrfc}", emp_id],
                "rule_broken": "Codigo Penal Federal Articulo 222 (Cohecho) y Politica Anticorrupcion Corporativa",
                "narrative": (
                    f"El empleado {corrupt_emp['name']} ({emp_id}) autorizo compras sobrevaluadas al proveedor {vrfc} "
                    f"por ${total:,.2f} MXN. Dos dias despues del cobro corporativo, el proveedor efectuo una transferencia "
                    f"SPEI directa por ${kickback_amount:,.2f} MXN (20% del contrato) a la cuenta bancaria personal del empleado."
                ),
                "peso_amount": total,
                "confidence": "proven",
                "money_trail": money_trail,
                "exhibits": exhibits
            })

    # -------------------------------------------------------------------------
    # Scheme 3: Round Tripping
    # -------------------------------------------------------------------------
    def plant_scheme_round_tripping(self):
        cfg = self.config.get("schemes", {}).get("round_tripping", {})
        if not cfg.get("enabled", True):
            return

        for idx in range(cfg.get("count", 1)):
            scheme_id = f"S3_round_tripping_{idx + 1}"
            cycle_amount = cfg.get("cycle_amount", 250000.0)

            # Node A: Intermediary Vendor
            name_a = "Intermediaria de Capitales SA de CV"
            rfc_a = f"RNDA{self.rng.randint(10, 99):02d}0303CC{idx + 1}"
            clabe_a = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": rfc_a,
                "legal_name": name_a,
                "registered_date": "2024-05-10",
                "address": "Paseo de la Sierra 300, Monterrey, NL",
                "bank_clabe": clabe_a,
                "category": "Consultoria Financiera",
                "contact_email": f"info@{rfc_a.lower()}.mx"
            })

            # Node B: Subcontractor / Conduit Vendor
            name_b = "Servicios de Flujo Circular SC"
            rfc_b = f"RNDB{self.rng.randint(10, 99):02d}0404DD{idx + 1}"
            clabe_b = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": rfc_b,
                "legal_name": name_b,
                "registered_date": "2024-06-12",
                "address": "Av. Valle Oriente 700, San Pedro, NL",
                "bank_clabe": clabe_b,
                "category": "Servicios Especializados",
                "contact_email": f"operaciones@{rfc_b.lower()}.mx"
            })

            # Step 1: Company -> Node A
            inv_uuid_1 = self._next_invoice_uuid()
            subtotal_1 = round(cycle_amount / 1.16, 2)
            iva_1 = round(cycle_amount - subtotal_1, 2)
            total_1 = round(subtotal_1 + iva_1, 2)

            date_step1 = "2026-03-01"
            self.invoices.append({
                "uuid": inv_uuid_1,
                "issuer_rfc": rfc_a,
                "receiver_rfc": self.company_rfc,
                "issue_date": date_step1,
                "subtotal": subtotal_1,
                "iva": iva_1,
                "total": total_1,
                "concepto_text": "Honorarios por estructuracion financiera y asesoria corporativa",
                "uso_cfdi": "G03",
                "forma_pago": "03",
                "metodo_pago": "PUE",
                "status": "vigente"
            })

            txn_id_1 = self._next_txn_id()
            self.bank_txns.append({
                "txn_id": txn_id_1,
                "date": date_step1,
                "from_clabe": self.company_clabe,
                "to_clabe": clabe_a,
                "amount": total_1,
                "reference": f"Transferencia capital {inv_uuid_1}",
                "channel": "SPEI"
            })

            # Step 2: Node A -> Node B (98% pass-through within 24-48h)
            date_step2 = "2026-03-02"
            amt_step2 = round(total_1 * (1.0 - cfg.get("retention_loss_pct", 0.02)), 2)
            txn_id_2 = self._next_txn_id()
            self.bank_txns.append({
                "txn_id": txn_id_2,
                "date": date_step2,
                "from_clabe": clabe_a,
                "to_clabe": clabe_b,
                "amount": amt_step2,
                "reference": "Subcontratacion de servicios",
                "channel": "SPEI"
            })

            # Step 3: Node B -> Company (returns funds within 48h, closing the loop)
            date_step3 = "2026-03-03"
            txn_id_3 = self._next_txn_id()
            self.bank_txns.append({
                "txn_id": txn_id_3,
                "date": date_step3,
                "from_clabe": clabe_b,
                "to_clabe": self.company_clabe,
                "amount": amt_step2,
                "reference": "Devolucion de anticipo / inversion",
                "channel": "SPEI"
            })

            # Ground truth
            self.ground_truth_schemes.append({
                "scheme_id": scheme_id,
                "type": "round_tripping",
                "entities": [f"RFC:{rfc_a}", f"RFC:{rfc_b}"],
                "supporting_invoices": [inv_uuid_1],
                "supporting_txns": [txn_id_1, txn_id_2, txn_id_3],
                "peso_amount": total_1,
                "difficulty": cfg.get("difficulty", "hard")
            })

            # Sample Finding
            exhibits = [
                {
                    "exhibit_id": "EX-01",
                    "source_table": "invoices",
                    "record_id": inv_uuid_1,
                    "note": f"Factura inicial {inv_uuid_1} emitida por {rfc_a} por ${total_1:,.2f} MXN."
                },
                {
                    "exhibit_id": "EX-02",
                    "source_table": "bank_txns",
                    "record_id": txn_id_1,
                    "note": f"Transferencia de salida SPEI {txn_id_1} a la cuenta del nodo A."
                },
                {
                    "exhibit_id": "EX-03",
                    "source_table": "bank_txns",
                    "record_id": txn_id_2,
                    "note": f"Transferencia puente SPEI {txn_id_2} del nodo A al nodo B en menos de 24 horas."
                },
                {
                    "exhibit_id": "EX-04",
                    "source_table": "bank_txns",
                    "record_id": txn_id_3,
                    "note": f"Retorno ciclico SPEI {txn_id_3} del nodo B a la cuenta de la empresa, cerrando el ciclo."
                }
            ]

            money_trail = [
                {
                    "from": self.company_rfc,
                    "to": f"RFC:{rfc_a}",
                    "amount": total_1,
                    "date": date_step1,
                    "exhibit_id": "EX-01"
                },
                {
                    "from": f"RFC:{rfc_a}",
                    "to": f"RFC:{rfc_b}",
                    "amount": amt_step2,
                    "date": date_step2,
                    "exhibit_id": "EX-03"
                },
                {
                    "from": f"RFC:{rfc_b}",
                    "to": self.company_rfc,
                    "amount": amt_step2,
                    "date": date_step3,
                    "exhibit_id": "EX-04"
                }
            ]

            self.sample_findings.append({
                "scheme_type": "round_tripping",
                "entities": [f"RFC:{rfc_a}", f"RFC:{rfc_b}"],
                "rule_broken": "Ley Federal para la Prevencion e Identificacion de Operaciones con Recursos de Procedencia Ilicita (LFPIORPI Art. 17)",
                "narrative": (
                    f"Se identifico un esquema de flujo circular de fondos (round-tripping) por ${total_1:,.2f} MXN. "
                    f"La empresa transfirio fondos a {rfc_a}, quien en menos de 24 horas desvio el 98% a {rfc_b}, y este "
                    "reintegro el capital a la cuenta corporativa simulando una cancelacion de anticipos sin sustancia de negocio."
                ),
                "peso_amount": total_1,
                "confidence": "proven",
                "money_trail": money_trail,
                "exhibits": exhibits
            })

    # -------------------------------------------------------------------------
    # Scheme 4: Threshold Splitting (Smurfing / Structuring)
    # -------------------------------------------------------------------------
    def plant_scheme_threshold_splitting(self):
        cfg = self.config.get("schemes", {}).get("threshold_splitting", {})
        if not cfg.get("enabled", True):
            return

        for idx in range(cfg.get("count", 1)):
            scheme_id = f"S4_threshold_splitting_{idx + 1}"
            vname = "Comercializadora de Suministros Fraccionados SA de CV"
            vrfc = f"SPLT{self.rng.randint(10, 99):02d}0505EE{idx + 1}"
            clabe = self.generator.generate_clabe()

            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2024-02-18",
                "address": "Av. San Jeronimo 500, Monterrey, NL",
                "bank_clabe": clabe,
                "category": "Papeleria y Suministros",
                "contact_email": f"ventas@{vrfc.lower()}.mx"
            })

            split_count = cfg.get("split_count", 4)
            amount_per_split = cfg.get("amount_per_split", 48600.0)
            threshold_limit = cfg.get("threshold_limit", 50000.0)
            total_peso = round(amount_per_split * split_count, 2)

            invoices_created: List[Dict[str, Any]] = []
            txns_created: List[Dict[str, Any]] = []
            pos_created: List[Dict[str, Any]] = []

            for s in range(split_count):
                split_date = (datetime.date(2026, 2, 20) + datetime.timedelta(days=s)).isoformat()
                subtotal = round(amount_per_split / 1.16, 2)
                iva = round(amount_per_split - subtotal, 2)
                total = round(subtotal + iva, 2)

                # Purchase order
                po_id = self._next_po_id()
                self.purchase_orders.append({
                    "po_id": po_id,
                    "vendor_rfc": vrfc,
                    "date": split_date,
                    "amount": total,
                    "requester": "J. Comprador",
                    "approver": "J. Comprador",  # Self-approved below threshold limit
                    "description": f"Suministros de oficina lote fraccionado {s+1}/{split_count}"
                })
                pos_created.append(po_id)

                # Invoice
                inv_uuid = self._next_invoice_uuid()
                inv_obj = {
                    "uuid": inv_uuid,
                    "issuer_rfc": vrfc,
                    "receiver_rfc": self.company_rfc,
                    "issue_date": split_date,
                    "subtotal": subtotal,
                    "iva": iva,
                    "total": total,
                    "concepto_text": f"Entrega de papeleria y consumibles administrativos entrega {s+1}",
                    "uso_cfdi": "G03",
                    "forma_pago": "03",
                    "metodo_pago": "PUE",
                    "status": "vigente"
                }
                self.invoices.append(inv_obj)
                invoices_created.append(inv_obj)

                # Payment
                txn_id = self._next_txn_id()
                txn_obj = {
                    "txn_id": txn_id,
                    "date": split_date,
                    "from_clabe": self.company_clabe,
                    "to_clabe": clabe,
                    "amount": total,
                    "reference": f"Pago factura fraccionada {inv_uuid}",
                    "channel": "SPEI"
                }
                self.bank_txns.append(txn_obj)
                txns_created.append(txn_obj)

            # Ground truth
            self.ground_truth_schemes.append({
                "scheme_id": scheme_id,
                "type": "threshold_splitting",
                "entities": [f"RFC:{vrfc}"],
                "supporting_invoices": [inv["uuid"] for inv in invoices_created],
                "supporting_txns": [txn["txn_id"] for txn in txns_created],
                "peso_amount": total_peso,
                "difficulty": cfg.get("difficulty", "easy")
            })

            # Sample Finding
            exhibits = []
            for k, inv in enumerate(invoices_created):
                exhibits.append({
                    "exhibit_id": f"EX-{k+1:02d}",
                    "source_table": "invoices",
                    "record_id": inv["uuid"],
                    "note": f"Factura {inv['uuid']} estructurada por ${inv['total']:,.2f} MXN justo por debajo del umbral de ${threshold_limit:,.2f}."
                })
            exhibits.append({
                "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                "source_table": "vendors",
                "record_id": vrfc,
                "note": f"Proveedor recurrente {vrfc} receptor de las operaciones fraccionadas."
            })
            for k, po_id in enumerate(pos_created):
                exhibits.append({
                    "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                    "source_table": "purchase_orders",
                    "record_id": po_id,
                    "note": f"Orden de compra fraccionada {po_id} para evadir aprobacion directiva."
                })

            money_trail = []
            for k, txn in enumerate(txns_created):
                money_trail.append({
                    "from": self.company_rfc,
                    "to": f"RFC:{vrfc}",
                    "amount": txn["amount"],
                    "date": txn["date"],
                    "exhibit_id": f"EX-{k+1:02d}"
                })

            self.sample_findings.append({
                "scheme_type": "threshold_splitting",
                "entities": [f"RFC:{vrfc}"],
                "rule_broken": "Politica de Control Interno Art. 4.2 y NIF A-2 (Fraccionamiento de Compras y Delegacion de Facultades)",
                "narrative": (
                    f"El proveedor {vrfc} facturo ${total_peso:,.2f} MXN divididos artificialmente en {split_count} facturas "
                    f"consecutivas de ${amount_per_split:,.2f} MXN en un lapso de 4 dias. La subdivision se realizo para eludir "
                    f"el umbral estatutario de control interno de ${threshold_limit:,.2f} MXN que exige aprobacion de Direccion."
                ),
                "peso_amount": total_peso,
                "confidence": "proven",
                "money_trail": money_trail,
                "exhibits": exhibits
            })

    # -------------------------------------------------------------------------
    # Scheme 5: Revenue Inflation (Fictitious Revenue / Circular Sales)
    # -------------------------------------------------------------------------
    def plant_scheme_revenue_inflation(self):
        cfg = self.config.get("schemes", {}).get("revenue_inflation", {})
        if not cfg.get("enabled", True):
            return

        for idx in range(cfg.get("count", 1)):
            scheme_id = f"S5_revenue_inflation_{idx + 1}"
            target_amount = cfg.get("invoice_amount", 320000.0)
            inv_count = cfg.get("invoices_count", 2)
            amount_per_inv = round(target_amount / inv_count, 2)
            total_peso = round(amount_per_inv * inv_count, 2)

            client_name = "Corporacion Comercial Fantasma del Golfo SA de CV"
            client_rfc = f"REVI{self.rng.randint(10, 99):02d}0606FF{idx + 1}"
            client_clabe = self.generator.generate_clabe()

            # Client listed in vendors
            self.vendors.append({
                "rfc": client_rfc,
                "legal_name": client_name,
                "registered_date": "2025-08-20",
                "address": "Blvd. Costero 800, Tampico, TAMPS",
                "bank_clabe": client_clabe,
                "category": "Distribuidor Mayorista",
                "contact_email": f"tesoreria@{client_rfc.lower()}.mx"
            })

            invoices_created: List[Dict[str, Any]] = []
            # Company issues sales invoices right before quarter/period end
            for j in range(inv_count):
                inv_date = (datetime.date(2026, 3, 28) + datetime.timedelta(days=j)).isoformat()
                subtotal = round(amount_per_inv / 1.16, 2)
                iva = round(amount_per_inv - subtotal, 2)
                total = round(subtotal + iva, 2)

                inv_uuid = self._next_invoice_uuid()
                inv_obj = {
                    "uuid": inv_uuid,
                    "issuer_rfc": self.company_rfc,  # Company issues fictitious sales invoice
                    "receiver_rfc": client_rfc,
                    "issue_date": inv_date,
                    "subtotal": subtotal,
                    "iva": iva,
                    "total": total,
                    "concepto_text": "Venta al por mayor de licencias de software y soporte corporativo anual",
                    "uso_cfdi": "G01",
                    "forma_pago": "03",
                    "metodo_pago": "PPD",
                    "status": "vigente"
                }
                self.invoices.append(inv_obj)
                invoices_created.append(inv_obj)

                # Ledger entry: Debit Cuentas por Cobrar (1200), Credit Ventas (4000)
                self._add_ledger_pair(
                    date_str=inv_date,
                    debit_code="1200",
                    debit_name="Clientes y cuentas por cobrar",
                    credit_code="4000",
                    credit_name="Ingresos por ventas",
                    amount=total,
                    description=f"Registro de venta a credito fin de trimestre {inv_uuid}",
                    invoice_uuid=inv_uuid,
                    cost_center="CC-400 Comercial",
                    approver="Director de Finanzas"
                )

            # Ground truth
            self.ground_truth_schemes.append({
                "scheme_id": scheme_id,
                "type": "revenue_inflation",
                "entities": [f"RFC:{client_rfc}"],
                "supporting_invoices": [inv["uuid"] for inv in invoices_created],
                "supporting_txns": [],
                "peso_amount": total_peso,
                "difficulty": cfg.get("difficulty", "medium")
            })

            # Sample Finding
            exhibits = []
            for k, inv in enumerate(invoices_created):
                exhibits.append({
                    "exhibit_id": f"EX-{k+1:02d}",
                    "source_table": "invoices",
                    "record_id": inv["uuid"],
                    "note": f"Factura de venta extemporanea {inv['uuid']} por ${inv['total']:,.2f} MXN registrada previo al cierre contable."
                })
            exhibits.append({
                "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                "source_table": "vendors",
                "record_id": client_rfc,
                "note": f"Entidad ficticia receptora {client_rfc} sin historial crediticio ni recepcion de bienes."
            })
            exhibits.append({
                "exhibit_id": f"EX-{len(exhibits)+1:02d}",
                "source_table": "ledger",
                "record_id": str(self.ledger_entry_id - 2),
                "note": "Asiento contable de reconocimiento indebido de ingresos por ventas a credito sin cobranza."
            })

            money_trail = []
            for k, inv in enumerate(invoices_created):
                money_trail.append({
                    "from": self.company_rfc,
                    "to": f"RFC:{client_rfc}",
                    "amount": inv["total"],
                    "date": inv["issue_date"],
                    "exhibit_id": f"EX-{k+1:02d}"
                })

            self.sample_findings.append({
                "scheme_type": "revenue_inflation",
                "entities": [f"RFC:{client_rfc}"],
                "rule_broken": "NIF D-1 y NIF D-2 (Ingresos por Contratos con Clientes y Reconocimiento de Cuentas por Cobrar)",
                "narrative": (
                    f"Al cierre del trimestre contable se registraron facturas de ingresos ficticias por ${total_peso:,.2f} MXN "
                    f"a favor del receptor {client_rfc}. Dichas operaciones carecen de contratos de prestacion de servicios, no "
                    "cuentan con evidencia de entrega de licencias y no se liquido la cuenta por cobrar correspondiente."
                ),
                "peso_amount": total_peso,
                "confidence": "proven",
                "money_trail": money_trail,
                "exhibits": exhibits
            })

    # -------------------------------------------------------------------------
    # Decoys Generator (Innocent entities that look suspicious on the surface)
    # -------------------------------------------------------------------------
    def plant_decoys(self):
        decoy_cfg = self.config.get("decoys", {})
        if not decoy_cfg.get("enabled", True):
            return

        types = decoy_cfg.get("types", {})

        # Decoy 1: Split urgent orders with documented logistics rationale
        if types.get("split_urgent_order", {}).get("enabled", True):
            vname = "Transportes y Fletes Expresos del Norte SA de CV"
            vrfc = f"DECY{self.rng.randint(10, 99):02d}0101AA1"
            clabe = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2023-04-10",
                "address": "Av. Alfonso Reyes 2200, Monterrey, NL",
                "bank_clabe": clabe,
                "category": "Logistica y Transporte",
                "contact_email": f"logistica@{vrfc.lower()}.mx"
            })
            # 3 split POs and invoices
            d_invs = []
            for s in range(3):
                poid = self._next_po_id()
                inv_uuid = self._next_invoice_uuid()
                d_invs.append(inv_uuid)
                self.purchase_orders.append({
                    "po_id": poid,
                    "vendor_rfc": vrfc,
                    "date": f"2026-01-1{s+1}",
                    "amount": 47000.0,
                    "requester": "Gerente de Logistica",
                    "approver": "Director de Finanzas",
                    "description": "Flete urgente dividido por restriccion de tonelaje de transporte (NOM-012-SCT)"
                })
                self.invoices.append({
                    "uuid": inv_uuid,
                    "issuer_rfc": vrfc,
                    "receiver_rfc": self.company_rfc,
                    "issue_date": f"2026-01-1{s+1}",
                    "subtotal": 40517.24,
                    "iva": 6482.76,
                    "total": 47000.0,
                    "concepto_text": f"Servicio de flete urgente Monterrey-Laredo viaje {s+1}",
                    "uso_cfdi": "G03",
                    "forma_pago": "03",
                    "metodo_pago": "PUE",
                    "status": "vigente"
                })

            self.ground_truth_decoys.append({
                "entity": f"RFC:{vrfc}",
                "signal": "threshold_splitting_detector",
                "why_innocent": "La division de embarques responde a restricciones tecnicas de tonelaje de la NOM-012-SCT y cuenta con aprobacion previa de Direccion en cada orden de compra.",
                "invoices": d_invs
            })
            self.sample_leads_not_pursued.append({
                "entity": f"RFC:{vrfc}",
                "signal": "threshold_splitting_detector",
                "reason": "La division de facturacion ($47,000 x 3) responde a la limitacion de peso vehicular conforme a la NOM-012-SCT justificada documentalmente en las POs.",
                "tool_calls_made": ["get_vendor_details", "get_purchase_order_details"],
                "closed_by": "investigator"
            })

        # Decoy 2: High value purchase with board approval
        if types.get("high_value_board_approved", {}).get("enabled", True):
            vname = "Maquinaria Pesada y Montacargas de Mexico SA de CV"
            vrfc = f"DECY{self.rng.randint(10, 99):02d}0202BB2"
            clabe = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2022-01-15",
                "address": "Carretera Miguel Aleman Km 14, Apodaca, NL",
                "bank_clabe": clabe,
                "category": "Mantenimiento Industrial",
                "contact_email": f"ventas@{vrfc.lower()}.mx"
            })
            inv_uuid = self._next_invoice_uuid()
            po_id = self._next_po_id()
            cid = self._next_contract_id()
            self.contracts.append({
                "contract_id": cid,
                "vendor_rfc": vrfc,
                "start_date": "2025-10-01",
                "value": 450000.0,
                "scope_text": "Adquisicion de montacargas electricos para almacen central"
            })
            self.purchase_orders.append({
                "po_id": po_id,
                "vendor_rfc": vrfc,
                "date": "2025-10-15",
                "amount": 450000.0,
                "requester": "Jefe de Almacen",
                "approver": "Consejo de Administracion",
                "description": "Compra autorizada mediante Acta de Consejo No. 58"
            })
            self.invoices.append({
                "uuid": inv_uuid,
                "issuer_rfc": vrfc,
                "receiver_rfc": self.company_rfc,
                "issue_date": "2025-10-20",
                "subtotal": 387931.03,
                "iva": 62068.97,
                "total": 450000.0,
                "concepto_text": "Montacargas electrico trifasico de 3 toneladas modelo 2025",
                "uso_cfdi": "I04",
                "forma_pago": "03",
                "metodo_pago": "PUE",
                "status": "vigente"
            })
            self.ground_truth_decoys.append({
                "entity": f"RFC:{vrfc}",
                "signal": "outlier_amount_detector",
                "why_innocent": "La compra de activo fijo cuenta con resolucion formal y autorizacion del Consejo de Administracion en el Acta No. 58 y contrato firmado.",
                "invoices": [inv_uuid]
            })
            self.sample_leads_not_pursued.append({
                "entity": f"RFC:{vrfc}",
                "signal": "outlier_amount_detector",
                "reason": "La operacion por $450,000 MXN corresponde a un activo fijo respaldado por el contrato CTR-00002 y autorizacion formal del Consejo de Administracion.",
                "tool_calls_made": ["get_contract_details", "get_invoice_details"],
                "closed_by": "validator"
            })

        # Decoy 3: High-velocity logistics intermediary with long-term framework contract
        if types.get("high_velocity_logistics", {}).get("enabled", True):
            vname = "Logistica Multimodal Aduanal SA de CV"
            vrfc = f"DECY{self.rng.randint(10, 99):02d}0303CC3"
            clabe = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2021-08-11",
                "address": "Av. Las Americas 100, Nuevo Laredo, TAMPS",
                "bank_clabe": clabe,
                "category": "Logistica y Transporte",
                "contact_email": f"aduanas@{vrfc.lower()}.mx"
            })
            cid = self._next_contract_id()
            self.contracts.append({
                "contract_id": cid,
                "vendor_rfc": vrfc,
                "start_date": "2024-01-01",
                "value": 1200000.0,
                "scope_text": "Contrato marco trianual de intermediacion aduanal y logistica multimodal"
            })
            self.ground_truth_decoys.append({
                "entity": f"RFC:{vrfc}",
                "signal": "passthrough_velocity_detector",
                "why_innocent": "Agente aduanal certificado con contrato marco trianual y opinion de cumplimiento positiva 32-D del SAT.",
                "invoices": []
            })
            self.sample_leads_not_pursued.append({
                "entity": f"RFC:{vrfc}",
                "signal": "passthrough_velocity_detector",
                "reason": "El flujo acelerado corresponde a operaciones aduanales de despacho exterior amparadas bajo el contrato marco trianual con solvencia fiscal acreditada.",
                "tool_calls_made": ["get_contract_details", "check_efos_status"],
                "closed_by": "challenger"
            })

        # Decoy 4: Employee relocation bonus
        if types.get("employee_relocation_bonus", {}).get("enabled", True):
            emp = self.employees[8]
            bonus_amt = 55000.0
            tid = self._next_txn_id()
            self.bank_txns.append({
                "txn_id": tid,
                "date": "2026-01-15",
                "from_clabe": self.company_clabe,
                "to_clabe": emp["bank_clabe"],
                "amount": bonus_amt,
                "reference": "Reembolso reubicacion ejecutiva",
                "channel": "SPEI"
            })
            self._add_ledger_pair(
                date_str="2026-01-15",
                debit_code="5100",
                debit_name="Sueldos y prestaciones laborales",
                credit_code="1100",
                credit_name="Bancos e inversiones",
                amount=bonus_amt,
                description=f"Prestacion de traslado y reubicacion aprobada RH {emp['name']}",
                cost_center="CC-200 Administracion",
                approver="Gerente de Recursos Humanos"
            )
            self.ground_truth_decoys.append({
                "entity": emp["emp_id"],
                "signal": "unusual_employee_transfer_detector",
                "why_innocent": "Transferencia de prestaciones de reubicacion laboral y mudanza autorizada expresamente por la Gerencia de Recursos Humanos en contabilidad.",
                "invoices": []
            })
            self.sample_leads_not_pursued.append({
                "entity": emp["emp_id"],
                "signal": "unusual_employee_transfer_detector",
                "reason": "La transferencia de $55,000 MXN al empleado corresponde a un bono de reubicacion geografica debidamente contabilizado en la cuenta 5100 con visto bueno de RH.",
                "tool_calls_made": ["get_employee_details", "get_ledger_entries_by_account"],
                "closed_by": "investigator"
            })

        # Decoy 5: Vendor with similar name or branch to an EFOS, but clean SAT status
        if types.get("similar_name_clean_tax", {}).get("enabled", True):
            vname = "Servicios Empresariales Monterrey SA de CV"
            vrfc = f"DECY{self.rng.randint(10, 99):02d}0505EE5"
            clabe = self.generator.generate_clabe()
            self.vendors.append({
                "rfc": vrfc,
                "legal_name": vname,
                "registered_date": "2020-09-01",
                "address": "Av. Simon Bolivar 1200, Monterrey, NL",
                "bank_clabe": clabe,
                "category": "Servicios Legales y Fiscales",
                "contact_email": f"contacto@{vrfc.lower()}.mx"
            })
            self.ground_truth_decoys.append({
                "entity": f"RFC:{vrfc}",
                "signal": "efos_proximity_detector",
                "why_innocent": "Entidad independiente con razon social similar a un tercero listado, pero con RFC disjunto y constancia de situacion fiscal vigente sin irregularidades.",
                "invoices": []
            })
            self.sample_leads_not_pursued.append({
                "entity": f"RFC:{vrfc}",
                "signal": "efos_proximity_detector",
                "reason": "Coincidencia lexica en razon social con un RFC no vinculado; cuenta con constancia fiscal SAT vigente y no figura en la lista definitiva del 69-B.",
                "tool_calls_made": ["check_efos_status", "get_vendor_details"],
                "closed_by": "validator"
            })

    # -------------------------------------------------------------------------
    # Execution & Export
    # -------------------------------------------------------------------------
    def run(self) -> Tuple[str, str, str]:
        """Runs the entire generation pipeline and outputs files."""
        # 1. Populate tables
        self.seed_baseline_operations()
        self.plant_scheme_phantom_vendor()
        self.plant_scheme_kickback()
        self.plant_scheme_round_tripping()
        self.plant_scheme_threshold_splitting()
        self.plant_scheme_revenue_inflation()
        self.plant_decoys()

        # 2. Write SQLite Database
        conn = self.create_database(self.output_db_path)
        cur = conn.cursor()

        # Insert records into tables
        for row in self.vendors:
            cur.execute(
                "INSERT INTO vendors VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["rfc"], row["legal_name"], row["registered_date"], row["address"],
                 row["bank_clabe"], row["category"], row["contact_email"])
            )
        for row in self.invoices:
            cur.execute(
                "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["uuid"], row["issuer_rfc"], row["receiver_rfc"], row["issue_date"],
                 row["subtotal"], row["iva"], row["total"], row["concepto_text"],
                 row["uso_cfdi"], row["forma_pago"], row["metodo_pago"], row["status"])
            )
        for row in self.ledger:
            cur.execute(
                "INSERT INTO ledger (entry_id, date, account_code, account_name, debit, credit, description, invoice_uuid, cost_center, approver) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["entry_id"], row["date"], row["account_code"], row["account_name"],
                 row["debit"], row["credit"], row["description"], row["invoice_uuid"],
                 row["cost_center"], row["approver"])
            )
        for row in self.bank_txns:
            cur.execute(
                "INSERT INTO bank_txns VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["txn_id"], row["date"], row["from_clabe"], row["to_clabe"],
                 row["amount"], row["reference"], row["channel"])
            )
        for row in self.purchase_orders:
            cur.execute(
                "INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["po_id"], row["vendor_rfc"], row["date"], row["amount"],
                 row["requester"], row["approver"], row["description"])
            )
        for row in self.contracts:
            cur.execute(
                "INSERT INTO contracts VALUES (?, ?, ?, ?, ?)",
                (row["contract_id"], row["vendor_rfc"], row["start_date"],
                 row["value"], row["scope_text"])
            )
        for row in self.employees:
            cur.execute(
                "INSERT INTO employees VALUES (?, ?, ?, ?, ?)",
                (row["emp_id"], row["name"], row["role"], row["bank_clabe"], row["hire_date"])
            )
        for row in self.efos_list:
            cur.execute(
                "INSERT INTO efos_list VALUES (?, ?, ?, ?)",
                (row["rfc"], row["legal_name"], row["status"], row["publication_date"])
            )

        conn.commit()
        conn.close()

        # 3. Write Ground Truth JSON (adhering strictly to ground_truth_schema.json)
        gt_obj = {
            "ground_truth": {
                "seed": self.seed,
                "company_rfc": self.company_rfc,
                "schemes": self.ground_truth_schemes,
                "decoys": self.ground_truth_decoys
            }
        }
        gt_path = pathlib.Path(self.ground_truth_path)
        gt_path.parent.mkdir(parents=True, exist_ok=True)
        gt_path.write_text(json.dumps(gt_obj, indent=2, ensure_ascii=False), encoding="utf-8")

        # 4. Write Submission JSON (adhering strictly to submission_schema.json)
        sub_obj = {
            "seed": self.seed,
            "findings": self.sample_findings,
            "leads_not_pursued": self.sample_leads_not_pursued,
            "run_metadata": {
                "llm_calls": 0,
                "mxn_cost": 0.0,
                "wall_clock_seconds": 1.25,
                "cost_by_role": {
                    "investigator": 0.0,
                    "challenger": 0.0,
                    "validator": 0.0
                },
                "deterministic": True
            }
        }
        sub_path = pathlib.Path(self.submission_path)
        sub_path.parent.mkdir(parents=True, exist_ok=True)
        sub_path.write_text(json.dumps(sub_obj, indent=2, ensure_ascii=False), encoding="utf-8")

        return str(self.output_db_path), str(self.ground_truth_path), str(self.submission_path)


def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """Loads configuration file with fallback to default values."""
    default_config_file = pathlib.Path("config/seeder_config.json")
    if config_path and pathlib.Path(config_path).exists():
        target = pathlib.Path(config_path)
    elif default_config_file.exists():
        target = default_config_file
    else:
        target = None

    if target and target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Error loading {target}: {e}. Falling back to default settings.")

    # In-memory default config
    return {
        "general": {
            "seed": 42,
            "output_db_path": "data/estate.db",
            "ground_truth_path": "data/ground_truth.json",
            "submission_path": "data/submission.json",
            "audit_period": {"start_date": "2025-01-01", "end_date": "2026-03-31"},
            "company": {"rfc": "EMP920101AB1", "legal_name": "Industrias del Norte SA de CV", "primary_clabe": "000000000000000099"}
        },
        "baseline_operations": {"num_normal_vendors": 25, "num_normal_employees": 20, "num_normal_invoices": 60, "num_normal_pos": 40, "num_normal_contracts": 10, "include_payroll": True},
        "schemes": {
            "phantom_vendor": {"enabled": True, "count": 1},
            "kickback": {"enabled": True, "count": 1},
            "round_tripping": {"enabled": True, "count": 1},
            "threshold_splitting": {"enabled": True, "count": 1},
            "revenue_inflation": {"enabled": True, "count": 1}
        },
        "decoys": {"enabled": True, "planted_count": 5}
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forensic Data Estate Seeder (estate_schema.sql)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", "-c", help="Path to custom seeder_config.json")
    parser.add_argument("--seed", "-s", type=int, help="Deterministic RNG seed (overrides config)")
    parser.add_argument("--output", "-o", help="Target SQLite database path (e.g. data/estate.db)")
    parser.add_argument("--ground-truth", "-g", help="Target ground truth JSON path")
    parser.add_argument("--submission", help="Target submission JSON path")
    parser.add_argument("--batch", "-b", type=int, help="Batch mode: Number of datasets to generate")
    parser.add_argument("--start-seed", type=int, default=101, help="Starting seed for batch mode (default: 101)")
    parser.add_argument("--output-dir", default="data/datasets", help="Directory for batch outputs")

    args = parser.parse_args()
    config = load_config(args.config)

    # 1. Batch mode
    if args.batch and args.batch > 0:
        out_dir = pathlib.Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        print("=" * 70)
        print(f"  FORENSIC AUDITOR - BATCH DATA ESTATE SEEDER ({args.batch} DATASETS)")
        print("=" * 70)
        print(f"  Starting Seed: {args.start_seed}  |  Output Directory: {out_dir}")
        print("-" * 70)

        for i in range(args.batch):
            current_seed = args.start_seed + i
            seed_dir = out_dir / f"seed_{current_seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)

            batch_config = json.loads(json.dumps(config))
            batch_config["general"]["seed"] = current_seed
            batch_config["general"]["output_db_path"] = str(seed_dir / "estate.db")
            batch_config["general"]["ground_truth_path"] = str(seed_dir / "ground_truth.json")
            batch_config["general"]["submission_path"] = str(seed_dir / "submission.json")

            seeder = EstateSeeder(batch_config, seed=current_seed)
            db_p, gt_p, sub_p = seeder.run()
            n_schemes = len(seeder.ground_truth_schemes)
            n_decoys = len(seeder.ground_truth_decoys)
            print(f"  [OK] Seed {current_seed:4d} -> {seed_dir.name} (Schemes: {n_schemes}, Decoys: {n_decoys}, Invoices: {len(seeder.invoices)})")

        print("=" * 70)
        print(f"  BATCH COMPLETED: {args.batch} datasets ready in {out_dir}")
        print("=" * 70)
        return 0

    # 2. Single dataset mode
    if args.seed is not None:
        config["general"]["seed"] = args.seed
    if args.output:
        config["general"]["output_db_path"] = args.output
    if args.ground_truth:
        config["general"]["ground_truth_path"] = args.ground_truth
    if args.submission:
        config["general"]["submission_path"] = args.submission

    active_seed = config["general"]["seed"]
    seeder = EstateSeeder(config, seed=active_seed)

    print("=" * 70)
    print("  FORENSIC AUDITOR - DATA ESTATE SEEDER")
    print("=" * 70)
    print(f"  Seed: {active_seed}  |  Company: {seeder.company_rfc} ({seeder.company_name})")
    print(f"  Target DB: {seeder.output_db_path}")
    print("-" * 70)

    db_p, gt_p, sub_p = seeder.run()

    print(f"  [OK] SQLite Database created: {db_p}")
    print(f"       Vendors:         {len(seeder.vendors):4d}")
    print(f"       Invoices:        {len(seeder.invoices):4d}")
    print(f"       Ledger entries:  {len(seeder.ledger):4d}")
    print(f"       Bank Txns:       {len(seeder.bank_txns):4d}")
    print(f"       Purchase Orders: {len(seeder.purchase_orders):4d}")
    print(f"       Contracts:       {len(seeder.contracts):4d}")
    print(f"       Employees:       {len(seeder.employees):4d}")
    print(f"       EFOS listed:     {len(seeder.efos_list):4d}")
    print("-" * 70)
    print(f"  [OK] Ground Truth saved: {gt_p} (Schemes: {len(seeder.ground_truth_schemes)}, Decoys: {len(seeder.ground_truth_decoys)})")
    print(f"  [OK] Submission saved:   {sub_p} (Findings: {len(seeder.sample_findings)})")
    print("=" * 70)
    print("  To validate format & arithmetic reconciliation, run:")
    print(f"  python student-materials/forensic-auditor/validate_format.py --submission {sub_p} --estate {db_p}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
