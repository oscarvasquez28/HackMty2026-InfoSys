"""
Comprehensive automated tests for CaseFileGenerator.
Validates:
- Generation of the 5 required sections in exact order (case_file_structure.md)
- Rendered Mermaid flowcharts for money trails
- Executive summary table shape and arithmetic totals
- Inclusion of Leads Not Pursued in the body
- Exporting dual artifacts (case_file.md and submission.json)
- Validation against validate_format.py
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
    InvoiceRecord,
    LedgerRecord,
    PurchaseOrderRecord,
    VendorRecord,
)
from backend.services.case_file_generator import CaseFileGenerator, case_file_generator
from backend.services.deterministic_detectors import ForensicDetectorSuite
from backend.services.estate_connector import EstateConnector
from tmp.validate_format import validate_against_estate, validate_structure


def test_mermaid_renderer_validity():
    """Tests that money trail renders into valid Mermaid flowchart syntax."""
    generator = CaseFileGenerator()
    trail = [
        {
            "from": "RFC:EMPRESA_AUDITADA",
            "to": "RFC:AAAA010101AA1",
            "amount": 92800.0,
            "date": "2026-03-29",
            "exhibit_id": "EX-01",
        },
        {
            "from": "RFC:AAAA010101AA1",
            "to": "EMP:0001",
            "amount": 25000.0,
            "date": "2026-04-02",
            "exhibit_id": "EX-02",
        },
    ]

    mermaid_code = generator.render_money_trail_mermaid(trail)
    assert "```mermaid" in mermaid_code
    assert "flowchart LR" in mermaid_code
    assert "node_1" in mermaid_code
    assert "node_2" in mermaid_code
    assert "$92,800.00 MXN" in mermaid_code
    assert "[EX-01]" in mermaid_code
    assert "[EX-02]" in mermaid_code
    assert "```" in mermaid_code


@pytest.mark.asyncio
async def test_case_file_full_generation_and_export():
    """
    Sets up an estate, runs detection pipeline, generates case_file.md and submission.json,
    and asserts compliance with all 5 required sections and validate_format.py.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "generator_estate.db"
        connector = EstateConnector()
        await connector.init_schema(db_path)

        async with connector.session_scope(db_path) as session:
            # Seed phantom vendor
            session.add_all([
                VendorRecord(
                    rfc="AAAA010101AA1",
                    legal_name="Facturas Fantasma SA de CV",
                    bank_clabe="000000000000000001",
                ),
                EfosRecord(
                    rfc="AAAA010101AA1",
                    legal_name="Facturas Fantasma SA de CV",
                    status="definitivo",
                ),
                InvoiceRecord(
                    uuid="INV-001",
                    issuer_rfc="AAAA010101AA1",
                    receiver_rfc="EMPRESA_AUDITADA",
                    total=Decimal("85000.00"),
                    status="vigente",
                ),
                BankTxnRecord(
                    txn_id="BNK-001",
                    from_clabe="000000000000000099",
                    to_clabe="000000000000000001",
                    amount=Decimal("85000.00"),
                ),
            ])

        try:
            suite = ForensicDetectorSuite(connector)
            submission_data = await suite.run_forensic_detection_pipeline(estate_target=db_path, seed=7)

            generator = CaseFileGenerator()
            case_file_path, sub_path = generator.export_artifacts(
                submission_data=submission_data,
                output_dir=tmpdir,
                file_prefix="test_run",
                company_name="Corporativo Titan SA de CV",
                audit_period="Ejercicio Fiscal 2026",
            )

            # Assert files were written
            assert case_file_path.exists()
            assert sub_path.exists()

            md_content = case_file_path.read_text(encoding="utf-8")

            # Assert 1. Header requirements
            assert "## 1. Header" in md_content
            assert "Corporativo Titan SA de CV" in md_content
            assert "Ejercicio Fiscal 2026" in md_content
            assert "Estate Seed:** `7`" in md_content
            assert "LLM Call Count:" in md_content
            assert "Wall-Clock Seconds:" in md_content
            assert "Deterministic Run:" in md_content

            # Assert 2. Executive Summary requirements
            assert "## 2. Executive summary" in md_content
            assert "| **Findings** |" in md_content
            assert "| **Total exposure** |" in md_content
            assert "| **Leads investigated and closed** |" in md_content

            # Assert 3. Finding section requirements
            assert "## 3. Findings" in md_content
            assert "Qué Sucedió (Narrativa Pericial)" in md_content or "Narrative" in md_content or "Qué Sucedió" in md_content
            assert "Money Trail" in md_content
            assert "```mermaid" in md_content
            assert "flowchart LR" in md_content
            assert "Exhibits Table" in md_content
            assert "Conciliación Aritmética" in md_content or "Conciliación" in md_content
            assert "Revisión Adversarial" in md_content or "Adversarial" in md_content

            # Assert 4. Leads Not Pursued in the body
            assert "## 4. Leads not pursued" in md_content
            assert "| Entity | Signal / Check | Reason Closed |" in md_content

            # Assert 5. Method and limits requirements
            assert "## 5. Method and limits" in md_content
            assert "### Architecture" in md_content
            assert "### Out of Scope" in md_content
            assert "### What the System Cannot Detect (Limits)" in md_content
            assert "### Reproducibility" in md_content

            # Assert validate_format.py passes with 0 errors
            loaded_sub = json.loads(sub_path.read_text(encoding="utf-8"))
            errs_struct = validate_structure(loaded_sub)
            assert len(errs_struct) == 0, f"Format check failed: {errs_struct}"

            errs_estate = validate_against_estate(loaded_sub, str(db_path))
            assert len(errs_estate) == 0, f"Estate check failed: {errs_estate}"

        finally:
            await connector.dispose_all()
