"""
Comprehensive automated tests for ExhibitBuilder and PerTableReconciler.
Validates:
- Mathematical 2% reconciliation per table
- Multi-table settlements without double counting (invoices + bank_txns)
- Rejection of variances exceeding 2%
- Auto-completion to satisfy minimum 3 exhibits constraint
- Direct persistence to the estate 'exhibits' table
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest

from backend.models.estate import (
    BankTxnRecord,
    ContractRecord,
    ExhibitRecord,
    InvoiceRecord,
    LedgerRecord,
    PurchaseOrderRecord,
    VendorRecord,
)
from backend.services.estate_connector import EstateConnector
from backend.services.exhibit_builder import ExhibitBuilder, PerTableReconciler


@pytest.fixture
def reconciler():
    return PerTableReconciler(tolerance=0.02)


def test_reconciler_exact_match(reconciler):
    """Tests exact match on single table (0.00% variance)."""
    sums = {"invoices": 100000.0}
    res = reconciler.calculate_reconciliation(100000.0, sums)
    assert res.is_reconciled is True
    assert res.best_table == "invoices"
    assert res.variance_amount == 0.0
    assert res.variance_pct == 0.0
    assert "0.00% variance" in res.formula_text


def test_reconciler_within_two_percent_tolerance(reconciler):
    """Tests 1.5% variance (within 2% tolerance)."""
    sums = {"invoices": 100000.0}
    # 101,500 is 1.5% above 100,000 (allowed margin is 2,000)
    res = reconciler.calculate_reconciliation(101500.0, sums)
    assert res.is_reconciled is True
    assert res.variance_amount == 1500.0
    assert res.variance_pct == 0.015


def test_reconciler_exceeding_tolerance_fails(reconciler):
    """Tests 2.5% variance (exceeding 2% tolerance)."""
    sums = {"invoices": 100000.0}
    # 102,500 is 2.5% above 100,000 (exceeds 2,000 margin)
    res = reconciler.calculate_reconciliation(102500.0, sums)
    assert res.is_reconciled is False
    assert res.variance_amount == 2500.0
    assert len(res.errors) > 0
    assert "DOES NOT reconcile" in res.formula_text


def test_multi_table_best_match_avoids_double_counting(reconciler):
    """
    Tests that citing an invoice ($92,800) and the bank transfer ($92,800) that settled it
    does NOT sum to $185,600, but reconciles against the best-matching table ($92,800).
    """
    sums = {
        "invoices": 92800.0,
        "bank_txns": 92800.0,
        "purchase_orders": 92800.0,
    }
    res = reconciler.calculate_reconciliation(92800.0, sums)
    assert res.is_reconciled is True
    assert res.best_table in ("invoices", "bank_txns", "purchase_orders")
    assert res.best_table_sum == 92800.0
    assert res.variance_amount == 0.0


@pytest.mark.asyncio
async def test_exhibit_builder_autocomplete_and_persistence():
    """
    Tests:
    1. Exhibit auto-completion to ensure >= 3 exhibits.
    2. Direct persistence to the estate 'exhibits' table.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "exhibit_estate.db"
        connector = EstateConnector()
        await connector.init_schema(db_path)

        async with connector.session_scope(db_path) as session:
            session.add_all([
                VendorRecord(
                    rfc="AAAA010101AA1",
                    legal_name="Proveedor Prueba SA",
                    bank_clabe="000000000000000001",
                ),
                InvoiceRecord(
                    uuid="INV-001",
                    issuer_rfc="AAAA010101AA1",
                    receiver_rfc="EMPRESA_AUDITADA",
                    total=Decimal("50000.00"),
                    status="vigente",
                ),
                LedgerRecord(
                    entry_id=1,
                    account_code="5000",
                    debit=Decimal("50000.00"),
                    credit=Decimal("0.00"),
                    invoice_uuid="INV-001",
                    description="Registro INV-001",
                ),
                BankTxnRecord(
                    txn_id="BNK-001",
                    from_clabe="000000000000000099",
                    to_clabe="000000000000000001",
                    amount=Decimal("50000.00"),
                    reference="Pago INV-001",
                ),
            ])

        dfs = {
            "vendors": await connector.load_table_as_polars("vendors", db_path),
            "invoices": await connector.load_table_as_polars("invoices", db_path),
            "ledger": await connector.load_table_as_polars("ledger", db_path),
            "bank_txns": await connector.load_table_as_polars("bank_txns", db_path),
        }

        builder = ExhibitBuilder(connector=connector)

        # Finding starts with only 1 exhibit
        finding = {
            "scheme_type": "phantom_vendor",
            "entities": ["RFC:AAAA010101AA1"],
            "exhibits": [
                {
                    "exhibit_id": "EX-01",
                    "source_table": "invoices",
                    "record_id": "INV-001",
                    "note": "Factura simulada inicial.",
                }
            ],
        }

        # Auto-complete should add vendor and ledger/bank exhibits to reach >= 3
        completed_exhibits = builder.auto_complete_exhibits(finding, dfs)
        assert len(completed_exhibits) >= 3, f"Expected >= 3 exhibits, got {len(completed_exhibits)}"

        # Verify sequential IDs
        assert completed_exhibits[0]["exhibit_id"] == "EX-01"
        assert completed_exhibits[1]["exhibit_id"] == "EX-02"
        assert completed_exhibits[2]["exhibit_id"] == "EX-03"

        # Persist exhibits directly into estate table
        try:
            persisted_count = await builder.persist_exhibits_to_estate(completed_exhibits, estate_target=db_path)
            assert persisted_count == len(completed_exhibits)

            # Check database table contains the exhibits
            summary = await connector.get_estate_summary(db_path)
            assert summary["table_counts"]["exhibits"] == len(completed_exhibits)
        finally:
            await connector.dispose_all()

