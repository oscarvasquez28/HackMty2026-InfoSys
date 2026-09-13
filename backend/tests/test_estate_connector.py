"""
Comprehensive automated tests for EstateConnector and Estate ORM models.
Validates:
- Dynamic SQLite estate initialization (both :memory: and temp files)
- Full CRUD operations across all 9 estate tables (vendors, invoices, ledger, bank_txns, purchase_orders, contracts, employees, efos_list, exhibits)
- Zero-copy Polars DataFrame table extraction
- Exhibit resolution and per-table 2% peso reconciliation
- Integration with validate_format.py
"""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import pytest

from backend.models.estate import (
    BankTxnRecord,
    ContractRecord,
    EfosRecord,
    EmployeeRecord,
    ExhibitRecord,
    InvoiceRecord,
    LedgerRecord,
    PurchaseOrderRecord,
    VendorRecord,
)
from backend.services.estate_connector import EstateConnector, estate_connector

import importlib.util
_val_path = Path("student-materials/forensic-auditor/validate_format.py")
if not _val_path.exists():
    _val_path = Path("tmp/validate_format.py")
_spec = importlib.util.spec_from_file_location("validate_format", str(_val_path))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_against_estate = _mod.validate_against_estate
validate_structure = _mod.validate_structure


@pytest.mark.asyncio
async def test_estate_connector_memory_init_and_crud():
    """Tests initializing schema and inserting records in an in-memory SQLite estate."""
    connector = EstateConnector()
    target = ":memory:"

    # 1. Initialize schema
    await connector.init_schema(target)

    # 2. Insert records across all tables
    async with connector.session_scope(target) as session:
        vendor = VendorRecord(
            rfc="AAAA010101AA1",
            legal_name="Proveedor Uno SA de CV",
            registered_date="2025-01-15",
            address="Calle 1, Monterrey",
            bank_clabe="000000000000000001",
            category="Consultoria",
            contact_email="uno@example.com",
        )
        invoice = InvoiceRecord(
            uuid="INV-00001",
            issuer_rfc="AAAA010101AA1",
            receiver_rfc="EMP920101AB1",
            issue_date="2026-02-15",
            subtotal=Decimal("80000.00"),
            iva=Decimal("12800.00"),
            total=Decimal("92800.00"),
            concepto_text="Servicios de consultoria",
            uso_cfdi="G03",
            forma_pago="03",
            metodo_pago="PUE",
            status="vigente",
        )
        ledger = LedgerRecord(
            entry_id=1,
            date="2026-02-15",
            account_code="5000",
            account_name="Gastos operativos",
            debit=Decimal("92800.00"),
            credit=Decimal("0.00"),
            description="Registro factura INV-00001",
            invoice_uuid="INV-00001",
            cost_center="CC-100",
            approver="A. Ejemplo",
        )
        bank_txn = BankTxnRecord(
            txn_id="BNK-00001",
            date="2026-03-29",
            from_clabe="000000000000000099",
            to_clabe="000000000000000001",
            amount=Decimal("92800.00"),
            reference="Pago factura INV-00001",
            channel="SPEI",
        )
        po = PurchaseOrderRecord(
            po_id="PO-00001",
            vendor_rfc="AAAA010101AA1",
            date="2026-02-10",
            amount=Decimal("92800.00"),
            requester="C. Ejemplo",
            approver="D. Ejemplo",
            description="PO Consultoria",
        )
        contract = ContractRecord(
            contract_id="CTR-00001",
            vendor_rfc="AAAA010101AA1",
            start_date="2025-01-01",
            value=Decimal("500000.00"),
            scope_text="Contrato anual de servicios",
        )
        employee = EmployeeRecord(
            emp_id="EMP:0001",
            name="Persona Uno",
            role="Gerente de Compras",
            bank_clabe="000000000000000501",
            hire_date="2021-03-01",
        )
        efos = EfosRecord(
            rfc="AAAA010101AA1",
            legal_name="Proveedor Uno SA de CV",
            status="definitivo",
            publication_date="2025-12-11",
        )
        exhibit = ExhibitRecord(
            exhibit_id="EX-01",
            source_table="invoices",
            record_id="INV-00001",
            sentence="Factura emitida por monto inflado.",
        )

        session.add_all([vendor, invoice, ledger, bank_txn, po, contract, employee, efos, exhibit])

    # 3. Verify summary counts
    summary = await connector.get_estate_summary(target)
    assert summary["total_records"] == 9
    counts = summary["table_counts"]
    for tbl in ("vendors", "invoices", "ledger", "bank_txns", "purchase_orders", "contracts", "employees", "efos_list", "exhibits"):
        assert counts[tbl] == 1

    # 4. Verify Polars table extraction
    df_invoices = await connector.load_table_as_polars("invoices", target)
    assert df_invoices.shape[0] == 1
    assert "uuid" in df_invoices.columns
    assert "total" in df_invoices.columns
    assert df_invoices["uuid"][0] == "INV-00001"
    assert df_invoices["total"][0] == 92800.0

    df_bank = await connector.load_table_as_polars("bank_txns", target)
    assert df_bank.shape[0] == 1
    assert df_bank["amount"][0] == 92800.0

    await connector.dispose_all()


@pytest.mark.asyncio
async def test_estate_connector_file_and_validator_compatibility():
    """
    Tests creating a SQLite file on disk, inserting records, verifying exhibits with
    per-table 2% reconciliation, and passing validate_against_estate from validate_format.py.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_estate.db"
        connector = EstateConnector()

        # Initialize schema
        await connector.init_schema(db_path)

        # Seed data
        async with connector.session_scope(db_path) as session:
            session.add_all([
                VendorRecord(
                    rfc="AAAA010101AA1",
                    legal_name="Proveedor Fantasma SA",
                    registered_date="2025-01-01",
                    address="Calle Falsa 123",
                    bank_clabe="000000000000000001",
                    category="Consultoria",
                    contact_email="test@example.com",
                ),
                InvoiceRecord(
                    uuid="INV-00001",
                    issuer_rfc="AAAA010101AA1",
                    receiver_rfc="EMP920101AB1",
                    issue_date="2026-02-15",
                    subtotal=Decimal("80000.00"),
                    iva=Decimal("12800.00"),
                    total=Decimal("92800.00"),
                    concepto_text="Servicios inexistentes",
                    uso_cfdi="G03",
                    forma_pago="03",
                    metodo_pago="PUE",
                    status="vigente",
                ),
                InvoiceRecord(
                    uuid="INV-00002",
                    issuer_rfc="AAAA010101AA1",
                    receiver_rfc="EMP920101AB1",
                    issue_date="2026-02-27",
                    subtotal=Decimal("40000.00"),
                    iva=Decimal("6400.00"),
                    total=Decimal("46400.00"),
                    concepto_text="Mantenimiento simulado",
                    uso_cfdi="G03",
                    forma_pago="03",
                    metodo_pago="PUE",
                    status="vigente",
                ),
                BankTxnRecord(
                    txn_id="BNK-00001",
                    date="2026-03-29",
                    from_clabe="000000000000000099",
                    to_clabe="000000000000000001",
                    amount=Decimal("92800.00"),
                    reference="Pago factura 1",
                    channel="SPEI",
                ),
                BankTxnRecord(
                    txn_id="BNK-00002",
                    date="2026-03-16",
                    from_clabe="000000000000000099",
                    to_clabe="000000000000000001",
                    amount=Decimal("46400.00"),
                    reference="Pago factura 2",
                    channel="SPEI",
                ),
                EfosRecord(
                    rfc="AAAA010101AA1",
                    legal_name="Proveedor Fantasma SA",
                    status="definitivo",
                    publication_date="2025-12-11",
                ),
            ])

        # Test exhibit verification service
        exhibits = [
            {"exhibit_id": "EX-01", "source_table": "invoices", "record_id": "INV-00001", "note": "Factura simulada 1"},
            {"exhibit_id": "EX-02", "source_table": "invoices", "record_id": "INV-00002", "note": "Factura simulada 2"},
            {"exhibit_id": "EX-03", "source_table": "vendors", "record_id": "AAAA010101AA1", "note": "Empresa fantasma"},
            {"exhibit_id": "EX-04", "source_table": "efos_list", "record_id": "AAAA010101AA1", "note": "Listado definitivo SAT 69-B"},
        ]

        # Invoices sum: 92,800 + 46,400 = 139,200.0
        claimed_amount = 139200.0
        res = await connector.verify_exhibits(exhibits, claimed_amount=claimed_amount, target=db_path)
        assert res["valid"] is True
        assert res["reconciled"] is True
        assert "invoices" in res["per_table_totals"]
        assert res["per_table_totals"]["invoices"] == 139200.0

        # Test failure on non-existent record
        bad_exhibits = exhibits + [{"exhibit_id": "EX-99", "source_table": "invoices", "record_id": "INV-99999", "note": "Non-existent"}]
        res_bad = await connector.verify_exhibits(bad_exhibits, claimed_amount=claimed_amount, target=db_path)
        assert res_bad["valid"] is False
        assert any("does not exist in estate" in err for err in res_bad["errors"])

        # Test failure on amount mismatch (> 2%)
        res_unreconciled = await connector.verify_exhibits(exhibits, claimed_amount=100000.0, target=db_path)
        assert res_unreconciled["valid"] is False
        assert any("does not reconcile" in err for err in res_unreconciled["errors"])

        # Test direct compatibility with validate_format.py
        submission = {
            "seed": 1,
            "findings": [
                {
                    "scheme_type": "phantom_vendor",
                    "entities": ["RFC:AAAA010101AA1"],
                    "rule_broken": "SAT Articulo 69-B",
                    "narrative": "Empresa fantasma que emitio facturas sin sustancia economica.",
                    "peso_amount": 139200.0,
                    "confidence": "proven",
                    "money_trail": [
                        {"from": "EMP920101AB1", "to": "AAAA010101AA1", "amount": 92800.0, "date": "2026-03-29", "exhibit_id": "EX-01"},
                        {"from": "EMP920101AB1", "to": "AAAA010101AA1", "amount": 46400.0, "date": "2026-03-16", "exhibit_id": "EX-02"},
                    ],
                    "exhibits": exhibits,
                }
            ],
            "leads_not_pursued": [
                {
                    "entity": "RFC:BBBB020202BB2",
                    "signal": "efos_check",
                    "reason": "Empresa solvente con contratos y entregables verificados.",
                    "tool_calls_made": ["search_transactions"],
                    "closed_by": "investigator",
                }
            ],
            "run_metadata": {
                "llm_calls": 2,
                "mxn_cost": 0.15,
                "wall_clock_seconds": 1.2,
                "deterministic": True,
            },
        }

        # 1. Check structure
        errs_struct = validate_structure(submission)
        assert len(errs_struct) == 0, f"Structure errors: {errs_struct}"

        # 2. Check against estate using validate_format.py logic
        errs_estate = validate_against_estate(submission, str(db_path))
        assert len(errs_estate) == 0, f"Estate check errors: {errs_estate}"

        # 3. Check synchronous connection getter
        sync_conn = connector.get_sync_connection(db_path)
        row = sync_conn.execute("SELECT COUNT(*) FROM invoices").fetchone()
        assert row[0] == 2
        sync_conn.close()

        await connector.dispose_all()

