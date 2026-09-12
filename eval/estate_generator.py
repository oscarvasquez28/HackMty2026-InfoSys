"""
Synthetic Financial Estate Generator for Forensic AML Evaluation.

Generates realistic SQLite data estates compliant with estate_schema.sql,
planting the 5 competition fraud typologies and innocent decoys,
while producing an isolated ground truth JSON file conforming to ground_truth_schema.json.

NOTE: This file is part of the evaluation harness only and is NEVER imported by backend/ or agent tools.
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple


def generate_rfc(name_seed: str, is_person: bool = False) -> str:
    letters = "".join(c for c in name_seed.upper() if c.isalpha())[:3 if not is_person else 4].ljust(3 if not is_person else 4, "X")
    digits = f"{random.randint(70, 99):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
    homoclave = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=3))
    return f"{letters}{digits}{homoclave}"


def generate_clabe(bank_code: str = "012") -> str:
    plaza = f"{random.randint(100, 999):03d}"
    account = f"{random.randint(10000000000, 99999999999):011d}"
    control = f"{random.randint(0, 9)}"
    return f"{bank_code}{plaza}{account}{control}"[:18]


def build_estate_database(
    seed: int,
    db_path: Path,
    company_rfc: str = "AUD920101AB1",
    company_name: str = "Empresa Auditada S.A. de C.V.",
) -> Dict[str, Any]:
    """
    Creates an SQLite estate database at db_path and returns the paired ground truth dictionary.
    """
    import sqlite3
    random.seed(seed)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Provision schema matching estate_schema - polar.sql
    cur.executescript("""
    CREATE TABLE vendors (
        rfc             TEXT PRIMARY KEY,
        legal_name      TEXT,
        registered_date TEXT,
        address         TEXT,
        bank_clabe      TEXT,
        category        TEXT,
        contact_email   TEXT
    );

    CREATE TABLE invoices (
        uuid          TEXT PRIMARY KEY,
        issuer_rfc    TEXT,
        receiver_rfc  TEXT,
        issue_date    TEXT,
        subtotal      NUMERIC(15,2),
        iva           NUMERIC(15,2),
        total         NUMERIC(15,2),
        concepto_text TEXT,
        uso_cfdi      TEXT,
        forma_pago    TEXT,
        metodo_pago   TEXT,
        status        TEXT
    );

    CREATE TABLE ledger (
        entry_id     INTEGER PRIMARY KEY,
        date         TEXT,
        account_code TEXT,
        account_name TEXT,
        debit        NUMERIC(15,2),
        credit       NUMERIC(15,2),
        description  TEXT,
        invoice_uuid TEXT,
        cost_center  TEXT,
        approver     TEXT
    );

    CREATE TABLE bank_txns (
        txn_id     TEXT PRIMARY KEY,
        date       TEXT,
        from_clabe TEXT,
        to_clabe   TEXT,
        amount     NUMERIC(15,2),
        reference  TEXT,
        channel    TEXT
    );

    CREATE TABLE purchase_orders (
        po_id       TEXT PRIMARY KEY,
        vendor_rfc  TEXT,
        date        TEXT,
        amount      NUMERIC(15,2),
        requester   TEXT,
        approver    TEXT,
        description TEXT
    );

    CREATE TABLE contracts (
        contract_id TEXT PRIMARY KEY,
        vendor_rfc  TEXT,
        start_date  TEXT,
        value       NUMERIC(15,2),
        scope_text  TEXT
    );

    CREATE TABLE employees (
        emp_id     TEXT PRIMARY KEY,
        name       TEXT,
        role       TEXT,
        bank_clabe TEXT,
        hire_date  TEXT
    );

    CREATE TABLE efos_list (
        rfc              TEXT PRIMARY KEY,
        legal_name       TEXT,
        status           TEXT,
        publication_date TEXT
    );

    CREATE TABLE exhibits (
        exhibit_id      TEXT PRIMARY KEY,
        source_table    TEXT,
        record_id       TEXT,
        sentence        TEXT
    );
    """)

    schemes_planted: List[Dict[str, Any]] = []
    decoys_planted: List[Dict[str, Any]] = []

    company_clabe = "012180000000000099"

    # Base innocent employees
    employees = [
        ("EMP:0001", "Director General", "Direccion", generate_clabe(), "2018-01-15"),
        ("EMP:0002", "Gerente de Finanzas", "Finanzas", generate_clabe(), "2019-03-01"),
        ("EMP:0003", "Gerente de Compras", "Compras", generate_clabe(), "2021-06-10"),
        ("EMP:0004", "Analista Contable", "Contabilidad", generate_clabe(), "2023-02-01"),
    ]
    cur.executemany("INSERT INTO employees (emp_id, name, role, bank_clabe, hire_date) VALUES (?,?,?,?,?)", employees)

    # -------------------------------------------------------------------------
    # SCHEME 1: Phantom Vendor (EFOS definitivo with invoices and payments)
    # -------------------------------------------------------------------------
    pv_rfc = f"FANT{seed:04d}0101AA1"[:13]
    pv_name = f"Servicios Fantasma del Norte {seed} SA de CV"
    pv_clabe = generate_clabe()
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (pv_rfc, pv_name, "2025-05-10", "Calle Olvido 10", pv_clabe, "Consultoria", "contacto@fantasma.mx"))
    cur.execute("INSERT INTO efos_list (rfc, legal_name, status, publication_date) VALUES (?,?,?,?)",
                (pv_rfc, pv_name, "definitivo", "2025-08-01"))

    pv_subtotal = round(Decimal(random.randint(60000, 150000)), 2)
    pv_iva = round(pv_subtotal * Decimal("0.16"), 2)
    pv_total = pv_subtotal + pv_iva
    pv_uuid = f"INV-PV-{seed:04d}-001"
    cur.execute("INSERT INTO invoices (uuid, issuer_rfc, receiver_rfc, issue_date, subtotal, iva, total, concepto_text, uso_cfdi, forma_pago, metodo_pago, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
        pv_uuid, pv_rfc, company_rfc, "2026-01-15", float(pv_subtotal), float(pv_iva), float(pv_total), "Servicios de gestion y consultoria", "G03", "03", "PUE", "vigente"
    ))
    pv_bnk = f"BNK-PV-{seed:04d}-001"
    cur.execute("INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)", (
        pv_bnk, "2026-01-18", company_clabe, pv_clabe, float(pv_total), f"Pago factura {pv_uuid}", "SPEI"
    ))
    pv_po = f"PO-PV-{seed:04d}-001"
    cur.execute("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?)", (
        pv_po, pv_rfc, "2026-01-12", float(pv_total), "Gerente de Compras", "Director General", "Servicios de consultoria"
    ))

    schemes_planted.append({
        "scheme_id": f"S1_phantom_vendor_{seed}",
        "type": "phantom_vendor",
        "entities": [f"RFC:{pv_rfc}"],
        "supporting_invoices": [pv_uuid],
        "supporting_txns": [pv_bnk],
        "peso_amount": float(pv_total),
        "difficulty": "easy",
    })

    # -------------------------------------------------------------------------
    # SCHEME 2: Kickback (Colluding vendor paying procurement employee)
    # -------------------------------------------------------------------------
    kb_rfc = f"COLL{seed:04d}0202BB2"[:13]
    kb_name = f"Constructora Coludida {seed} SA"
    kb_clabe = generate_clabe()
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (kb_rfc, kb_name, "2024-03-12", "Av. Soborno 404", kb_clabe, "Construccion", "coludida@example.mx"))

    kb_amount = round(Decimal(random.randint(200000, 450000)), 2)
    bribe_amount = round(kb_amount * Decimal("0.10"), 2)
    kb_po = f"PO-KB-{seed:04d}-001"
    cur.execute("INSERT INTO purchase_orders (po_id, vendor_rfc, date, amount, requester, approver, description) VALUES (?,?,?,?,?,?,?)", (
        kb_po, kb_rfc, "2026-02-01", float(kb_amount), "Gerente de Compras", "Gerente de Compras", "Mantenimiento general de oficinas"
    ))
    kb_contract = f"CTR-KB-{seed:04d}-001"
    cur.execute("INSERT INTO contracts (contract_id, vendor_rfc, start_date, value, scope_text) VALUES (?,?,?,?,?)", (
        kb_contract, kb_rfc, "2026-01-20", float(kb_amount), "Contrato de obra"
    ))
    # Bribe transaction directly to procurement employee (EMP:0003)
    emp_proc_clabe = employees[2][3]
    kb_bnk = f"BNK-KB-{seed:04d}-001"
    cur.execute("INSERT INTO bank_txns (txn_id, date, from_clabe, to_clabe, amount, reference, channel) VALUES (?,?,?,?,?,?,?)", (
        kb_bnk, "2026-02-10", kb_clabe, emp_proc_clabe, float(bribe_amount), "Comision por asesoria", "SPEI"
    ))

    schemes_planted.append({
        "scheme_id": f"S2_kickback_{seed}",
        "type": "kickback",
        "entities": [f"RFC:{kb_rfc}", "EMP:0003"],
        "supporting_invoices": [],
        "supporting_txns": [kb_bnk],
        "peso_amount": float(bribe_amount),
        "difficulty": "medium",
    })

    # -------------------------------------------------------------------------
    # SCHEME 3: Round-Tripping (Cycle bank transfers)
    # -------------------------------------------------------------------------
    rt_amount = round(Decimal(random.randint(120000, 300000)), 2)
    clabe_a = generate_clabe("012")
    clabe_b = generate_clabe("002")
    clabe_c = generate_clabe("014")

    # Add vendor accounts for A, B, C
    rfc_a = f"RTA{seed:04d}0303AA3"[:13]
    rfc_b = f"RTB{seed:04d}0303BB3"[:13]
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (rfc_a, f"Comercializadora A {seed}", "2023-01-01", "Calle A", clabe_a, "Comercio", "a@example.mx"))
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (rfc_b, f"Logistica B {seed}", "2023-01-01", "Calle B", clabe_b, "Transporte", "b@example.mx"))

    rt_bnk1 = f"BNK-RT-{seed:04d}-001"
    rt_bnk2 = f"BNK-RT-{seed:04d}-002"
    rt_bnk3 = f"BNK-RT-{seed:04d}-003"
    cur.execute("INSERT INTO bank_txns (txn_id, date, from_clabe, to_clabe, amount, reference, channel) VALUES (?,?,?,?,?,?,?)", (rt_bnk1, "2026-03-01", clabe_a, clabe_b, float(rt_amount), "Transferencia operacion 1", "SPEI"))
    cur.execute("INSERT INTO bank_txns (txn_id, date, from_clabe, to_clabe, amount, reference, channel) VALUES (?,?,?,?,?,?,?)", (rt_bnk2, "2026-03-01", clabe_b, clabe_c, float(rt_amount), "Transferencia operacion 2", "SPEI"))
    cur.execute("INSERT INTO bank_txns (txn_id, date, from_clabe, to_clabe, amount, reference, channel) VALUES (?,?,?,?,?,?,?)", (rt_bnk3, "2026-03-02", clabe_c, clabe_a, float(rt_amount), "Retorno de fondos", "SPEI"))

    total_cycle_volume = float(rt_amount * 3)
    schemes_planted.append({
        "scheme_id": f"S3_round_tripping_{seed}",
        "type": "round_tripping",
        "entities": [f"RFC:{rfc_a}", f"RFC:{rfc_b}"],
        "supporting_invoices": [],
        "supporting_txns": [rt_bnk1, rt_bnk2, rt_bnk3],
        "peso_amount": total_cycle_volume,
        "difficulty": "hard",
    })

    # -------------------------------------------------------------------------
    # SCHEME 4: Threshold Splitting (Multiple POs just below $50,000 threshold)
    # -------------------------------------------------------------------------
    ts_rfc = f"SPLT{seed:04d}0404DD4"[:13]
    ts_name = f"Proveedora de Insumos {seed} SA"
    ts_clabe = generate_clabe()
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (ts_rfc, ts_name, "2025-02-01", "Av. Insumos 10", ts_clabe, "Materiales", "insumos@example.mx"))

    ts_amounts = [
        Decimal("48500.00"),
        Decimal("49200.00"),
        Decimal("49800.00"),
    ]
    ts_po_ids = []
    for idx, amt in enumerate(ts_amounts, start=1):
        po_id = f"PO-TS-{seed:04d}-{idx:03d}"
        ts_po_ids.append(po_id)
        cur.execute("INSERT INTO purchase_orders (po_id, vendor_rfc, date, amount, requester, approver, description) VALUES (?,?,?,?,?,?,?)", (
            po_id, ts_rfc, f"2026-04-0{idx}", float(amt), "Gerente de Compras", "Gerente de Compras", f"Insumos lote {idx}"
        ))

    ts_total = float(sum(ts_amounts))
    schemes_planted.append({
        "scheme_id": f"S4_threshold_splitting_{seed}",
        "type": "threshold_splitting",
        "entities": [f"RFC:{ts_rfc}"],
        "supporting_invoices": [],
        "supporting_txns": [],
        "peso_amount": ts_total,
        "difficulty": "medium",
    })

    # -------------------------------------------------------------------------
    # SCHEME 5: Revenue Inflation (Cancelled invoice active in ledger)
    # -------------------------------------------------------------------------
    ri_rfc = f"INFL{seed:04d}0505EE5"[:13]
    ri_name = f"Servicios Comerciales {seed} SA"
    ri_clabe = generate_clabe()
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (ri_rfc, ri_name, "2024-08-15", "Av. Ficticia 500", ri_clabe, "Servicios", "infl@example.mx"))

    ri_subtotal = round(Decimal(random.randint(80000, 180000)), 2)
    ri_iva = round(ri_subtotal * Decimal("0.16"), 2)
    ri_total = ri_subtotal + ri_iva
    ri_uuid = f"INV-RI-{seed:04d}-001"
    cur.execute("INSERT INTO invoices (uuid, issuer_rfc, receiver_rfc, issue_date, subtotal, iva, total, concepto_text, uso_cfdi, forma_pago, metodo_pago, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
        ri_uuid, ri_rfc, company_rfc, "2026-05-10", float(ri_subtotal), float(ri_iva), float(ri_total), "Servicios contables especiales", "G03", "03", "PUE", "cancelado"
    ))
    ri_ldg1 = f"LDG-RI-{seed:04d}-001"
    cur.execute("INSERT INTO ledger (entry_id, date, account_code, account_name, debit, credit, description, invoice_uuid, cost_center, approver) VALUES (?,?,?,?,?,?,?,?,?,?)", (
        1001, "2026-05-10", "401-01", "Ingresos por Servicios", 0.0, float(ri_total), f"Reconocimiento de ingreso {ri_uuid}", ri_uuid, "CC-100", "A. Auditor"
    ))
    ri_ldg2 = f"LDG-RI-{seed:04d}-002"
    cur.execute("INSERT INTO ledger (entry_id, date, account_code, account_name, debit, credit, description, invoice_uuid, cost_center, approver) VALUES (?,?,?,?,?,?,?,?,?,?)", (
        1002, "2026-05-10", "105-01", "Clientes por Cobrar", float(ri_total), 0.0, f"Cuenta por cobrar {ri_uuid}", ri_uuid, "CC-100", "A. Auditor"
    ))

    schemes_planted.append({
        "scheme_id": f"S5_revenue_inflation_{seed}",
        "type": "revenue_inflation",
        "entities": [f"RFC:{ri_rfc}"],
        "supporting_invoices": [ri_uuid],
        "supporting_txns": [],
        "peso_amount": float(ri_total),
        "difficulty": "hard",
    })

    # -------------------------------------------------------------------------
    # DECOYS (Innocent entities checking out on inspection)
    # -------------------------------------------------------------------------
    # Decoy 1: EFOS listed entity that has ZERO transactions with audited company
    decoy1_rfc = f"EFCL{seed:04d}9999DEC"[:13]
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (decoy1_rfc, f"Proveedor Desvinculado {seed}", "2023-01-01", "Direccion 1", generate_clabe(), "Servicios", "desvinculado@example.mx"))
    cur.execute("INSERT INTO efos_list (rfc, legal_name, status, publication_date) VALUES (?,?,?,?)",
                (decoy1_rfc, f"Proveedor Desvinculado {seed}", "definitivo", "2025-01-01"))
    decoys_planted.append({
        "entity": f"RFC:{decoy1_rfc}",
        "signal": "efos_clearance",
        "why_innocent": "La entidad figura en EFOS definitivo pero no cuenta con facturacion ni pagos registrados en la empresa auditada.",
        "invoices": [],
    })

    # Decoy 2: High value purchase order with formal public contract and different approver
    decoy2_rfc = f"LEGIT{seed:04d}8888DEC"[:13]
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (decoy2_rfc, f"Proveedor Legitimo {seed} SA", "2021-01-01", "Direccion Central", generate_clabe(), "Equipos", "legit@example.mx"))
    cur.execute("INSERT INTO contracts (contract_id, vendor_rfc, start_date, value, scope_text) VALUES (?,?,?,?,?)", (
        f"CTR-DEC-{seed:04d}", decoy2_rfc, "2026-01-01", 500000.0, "Contrato formal de adquisicion"
    ))
    cur.execute("INSERT INTO purchase_orders (po_id, vendor_rfc, date, amount, requester, approver, description) VALUES (?,?,?,?,?,?,?)", (
        f"PO-DEC-{seed:04d}", decoy2_rfc, "2026-02-15", 500000.0, "Gerente de Finanzas", "Director General", "Adquisicion de servidores"
    ))
    decoys_planted.append({
        "entity": f"RFC:{decoy2_rfc}",
        "signal": "high_value_procurement",
        "why_innocent": "Adquisicion de alto valor debidamente amparada en contrato formal licitado y aprobada por direccion.",
        "invoices": [],
    })

    # Decoy 3: Single threshold transaction (not split)
    decoy3_rfc = f"ONEOFF{seed:04d}777DEC"[:13]
    cur.execute("INSERT INTO vendors (rfc, legal_name, registered_date, address, bank_clabe, category, contact_email) VALUES (?,?,?,?,?,?,?)",
                (decoy3_rfc, f"Papeleria Local {seed}", "2022-01-01", "Calle Comercio", generate_clabe(), "Papeleria", "papeleria@example.mx"))
    cur.execute("INSERT INTO purchase_orders (po_id, vendor_rfc, date, amount, requester, approver, description) VALUES (?,?,?,?,?,?,?)", (
        f"PO-ONE-{seed:04d}", decoy3_rfc, "2026-03-10", 49500.0, "Analista Contable", "Gerente de Finanzas", "Suministro anual papeleria"
    ))
    decoys_planted.append({
        "entity": f"RFC:{decoy3_rfc}",
        "signal": "near_threshold_isolated",
        "why_innocent": "Transaccion aislada de compra de insumos ordinarios sin recurrencia consecutiva.",
        "invoices": [],
    })

    conn.commit()
    conn.close()

    ground_truth_dict = {
        "ground_truth": {
            "seed": seed,
            "company_rfc": company_rfc,
            "schemes": schemes_planted,
            "decoys": decoys_planted,
        }
    }

    return ground_truth_dict
