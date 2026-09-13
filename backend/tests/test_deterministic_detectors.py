"""
Comprehensive automated tests for ForensicDetectorSuite.
Validates detection of all 5 competition fraud typologies on a planted estate:
1. phantom_vendor
2. kickback
3. round_tripping
4. threshold_splitting
5. revenue_inflation
Plus:
- Decoy clearance into leads_not_pursued
- 100% compliance with validate_format.py
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
from backend.services.deterministic_detectors import ForensicDetectorSuite
from backend.services.estate_connector import EstateConnector
from tmp.validate_format import validate_against_estate, validate_structure


@pytest.mark.asyncio
async def test_all_five_fraud_typologies_and_decoys():
    """
    Sets up a complete synthetic estate with planted instances of all 5 scheme types
    and innocent decoys, runs the detector suite, and confirms validate_format.py passes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "full_scheme_estate.db"
        connector = EstateConnector()

        # 1. Provision schema
        await connector.init_schema(db_path)

        async with connector.session_scope(db_path) as session:
            # -----------------------------------------------------------------
            # 1. PHANTOM VENDOR setup:
            # Vendor AAAA010101AA1 listed in efos_list, invoices issued, no contract
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="AAAA010101AA1",
                legal_name="Facturas Fantasma SA de CV",
                registered_date="2025-10-01",
                address="Av. Ficticia 100",
                bank_clabe="000000000000000001",
                category="Servicios",
            ))
            session.add(EfosRecord(
                rfc="AAAA010101AA1",
                legal_name="Facturas Fantasma SA de CV",
                status="definitivo",
                publication_date="2025-12-01",
            ))
            session.add(InvoiceRecord(
                uuid="INV-PV-001",
                issuer_rfc="AAAA010101AA1",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2026-01-10",
                subtotal=Decimal("80000.00"),
                iva=Decimal("12800.00"),
                total=Decimal("92800.00"),
                concepto_text="Asesoria tecnica ficticia",
                status="vigente",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-PV-001",
                date="2026-01-15",
                from_clabe="000000000000000099",
                to_clabe="000000000000000001",
                amount=Decimal("92800.00"),
                reference="Pago INV-PV-001",
                channel="SPEI",
            ))

            # -----------------------------------------------------------------
            # 2. KICKBACK setup:
            # Vendor BBBB020202BB2 pays bribe to Employee EMP:0001's CLABE
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="BBBB020202BB2",
                legal_name="Proveedor Coludido SA",
                registered_date="2024-05-01",
                address="Calle Corrupta 200",
                bank_clabe="000000000000000002",
                category="Construccion",
            ))
            session.add(EmployeeRecord(
                emp_id="EMP:0001",
                name="Juan Soborno",
                role="Gerente de Compras",
                bank_clabe="000000000000000501",
                hire_date="2020-01-01",
            ))
            session.add(PurchaseOrderRecord(
                po_id="PO-KB-001",
                vendor_rfc="BBBB020202BB2",
                date="2026-02-01",
                amount=Decimal("250000.00"),
                requester="Juan Soborno",
                approver="Juan Soborno",
                description="Obra civil",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-KB-001",
                date="2026-02-05",
                from_clabe="000000000000000002",
                to_clabe="000000000000000501",  # Employee's personal CLABE!
                amount=Decimal("25000.00"),
                reference="Comision indebida",
                channel="SPEI",
            ))

            # -----------------------------------------------------------------
            # 3. ROUND TRIPPING setup:
            # Cycle of bank transfers: 000000000000000010 -> 000000000000000020 -> 000000000000000030 -> 000000000000000010
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="CCCC030303CC3",
                legal_name="Intermediario A SA",
                bank_clabe="000000000000000010",
            ))
            session.add(VendorRecord(
                rfc="DDDD040404DD4",
                legal_name="Intermediario B SA",
                bank_clabe="000000000000000020",
            ))
            session.add(VendorRecord(
                rfc="EEEE050505EE5",
                legal_name="Intermediario C SA",
                bank_clabe="000000000000000030",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-RT-001",
                date="2026-03-01",
                from_clabe="000000000000000010",
                to_clabe="000000000000000020",
                amount=Decimal("150000.00"),
                reference="Giro etapa 1",
                channel="SPEI",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-RT-002",
                date="2026-03-02",
                from_clabe="000000000000000020",
                to_clabe="000000000000000030",
                amount=Decimal("148000.00"),
                reference="Giro etapa 2",
                channel="SPEI",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-RT-003",
                date="2026-03-03",
                from_clabe="000000000000000030",
                to_clabe="000000000000000010",
                amount=Decimal("145000.00"),
                reference="Giro retorno",
                channel="SPEI",
            ))

            # -----------------------------------------------------------------
            # 4. THRESHOLD SPLITTING setup:
            # Two POs for $48,000 each (total $96,000) structured just below $50k
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="FFFF060606FF6",
                legal_name="Proveedor Fraccionado SA",
                bank_clabe="000000000000000040",
            ))
            session.add(PurchaseOrderRecord(
                po_id="PO-TS-001",
                vendor_rfc="FFFF060606FF6",
                date="2026-02-18",
                amount=Decimal("48000.00"),
                requester="Pedro Gerente",
                approver="Pedro Gerente",
                description="Lote suministros parte 1",
            ))
            session.add(PurchaseOrderRecord(
                po_id="PO-TS-002",
                vendor_rfc="FFFF060606FF6",
                date="2026-02-18",
                amount=Decimal("48000.00"),
                requester="Pedro Gerente",
                approver="Pedro Gerente",
                description="Lote suministros parte 2",
            ))

            # -----------------------------------------------------------------
            # 5. REVENUE INFLATION setup:
            # Cancelled invoice INV-RI-001 ($60,000) booked in ledger credit, never reversed
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="GGGG070707GG7",
                legal_name="Cliente Inflado SA",
                bank_clabe="000000000000000050",
            ))
            session.add(InvoiceRecord(
                uuid="INV-RI-001",
                issuer_rfc="GGGG070707GG7",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2026-02-28",
                subtotal=Decimal("51724.14"),
                iva=Decimal("8275.86"),
                total=Decimal("60000.00"),
                concepto_text="Venta cancelada pero computada",
                status="cancelado",  # Cancelled!
            ))
            session.add(LedgerRecord(
                entry_id=101,
                date="2026-02-28",
                account_code="4100",
                account_name="Ingresos por ventas",
                debit=Decimal("0.00"),
                credit=Decimal("60000.00"),  # Credited revenue, never reversed
                description="Registro ingreso factura INV-RI-001",
                invoice_uuid="INV-RI-001",
                approver="Contador General",
            ))

            # -----------------------------------------------------------------
            # DECOYS:
            # 1. Legitimate vendor with invoices + signed contract + PO
            # -----------------------------------------------------------------
            session.add(VendorRecord(
                rfc="HONEST010101H1",
                legal_name="Proveedor Honesto SA de CV",
                bank_clabe="000000000000000080",
                registered_date="2021-01-01",
            ))
            session.add(ContractRecord(
                contract_id="CTR-LEGIT-001",
                vendor_rfc="HONEST010101H1",
                start_date="2025-01-01",
                value=Decimal("120000.00"),
                scope_text="Mantenimiento general",
            ))
            session.add(PurchaseOrderRecord(
                po_id="PO-LEGIT-001",
                vendor_rfc="HONEST010101H1",
                date="2026-01-05",
                amount=Decimal("120000.00"),
                requester="Gerencia",
                approver="Director",
                description="Mantenimiento anual",
            ))
            session.add(InvoiceRecord(
                uuid="INV-LEGIT-001",
                issuer_rfc="HONEST010101H1",
                receiver_rfc="EMPRESA_AUDITADA",
                issue_date="2026-01-05",
                subtotal=Decimal("103448.28"),
                iva=Decimal("16551.72"),
                total=Decimal("120000.00"),
                concepto_text="Mantenimiento contractual",
                status="vigente",
            ))

            # 2. Legitimate employee receiving normal payroll from company
            session.add(EmployeeRecord(
                emp_id="EMP:0002",
                name="Empleado Inocente",
                bank_clabe="000000000000000502",
                role="Operador",
            ))
            session.add(BankTxnRecord(
                txn_id="BNK-PAYROLL-001",
                date="2026-01-15",
                from_clabe="000000000000000099",  # Company CLABE, not a vendor!
                to_clabe="000000000000000502",
                amount=Decimal("18500.00"),
                reference="Nomina quincenal",
                channel="SPEI",
            ))

        try:
            # 2. Run the detection pipeline
            suite = ForensicDetectorSuite(connector)
            submission = await suite.run_forensic_detection_pipeline(estate_target=db_path, seed=42)

            # 3. Assertions on findings
            findings = submission["findings"]
            assert len(findings) >= 5, f"Expected at least 5 findings, got {len(findings)}"

            detected_schemes = {f["scheme_type"] for f in findings}
            expected_schemes = {
                "phantom_vendor",
                "kickback",
                "round_tripping",
                "threshold_splitting",
                "revenue_inflation",
            }
            assert expected_schemes.issubset(detected_schemes), (
                f"Missing schemes: {expected_schemes - detected_schemes}. Detected: {detected_schemes}"
            )

            # Check decoy presence in leads_not_pursued
            leads = submission["leads_not_pursued"]
            assert len(leads) >= 2, f"Expected at least 2 leads not pursued, got {len(leads)}"

            lead_entities = {l["entity"] for l in leads}
            assert "RFC:HONEST010101H1" in lead_entities, "Decoy honest vendor should be in leads_not_pursued"
            assert "EMP:0002" in lead_entities or "EMP:EMP:0002" in lead_entities, (
                "Decoy employee should be in leads_not_pursued"
            )

            # 4. Strictly validate with validate_format.py
            errs_struct = validate_structure(submission)
            assert len(errs_struct) == 0, f"Structure validation failed: {errs_struct}"

            errs_estate = validate_against_estate(submission, str(db_path))
            assert len(errs_estate) == 0, f"Estate reconciliation failed: {errs_estate}"

            # 5. Check run metadata
            meta = submission["run_metadata"]
            assert meta["deterministic"] is True
            assert meta["wall_clock_seconds"] > 0
            assert meta["llm_calls"] == 0
            assert meta["mxn_cost"] == 0.0
        finally:
            await connector.dispose_all()
            from backend.services.estate_connector import estate_connector
            await estate_connector.dispose_all()

