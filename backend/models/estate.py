"""
SQLAlchemy 2.0 ORM data models for the Forensic Auditor Data Estate.
Directly implements the schema defined in tmp/estate_schema - polar.sql,
conforming to CFDI 4.0 and Mexican corporate/tax compliance conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.forensic import Base, JSON_DOCUMENT


class VendorRecord(Base):
    """
    Corporate and moral vendors / suppliers registered in the data estate.
    Table: 'vendors'
    """
    __tablename__ = "vendors"

    rfc: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registered_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class InvoiceRecord(Base):
    """
    CFDI 4.0 electronic invoices emitted or received.
    Table: 'invoices'
    """
    __tablename__ = "invoices"

    uuid: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    issuer_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    receiver_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    issue_date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    iva: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    concepto_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uso_cfdi: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    forma_pago: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    metodo_pago: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)


class LedgerRecord(Base):
    """
    General ledger accounting journal entries.
    Table: 'ledger'
    """
    __tablename__ = "ledger"

    entry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    account_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    debit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), default=0.0, nullable=True)
    credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), default=0.0, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_uuid: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approver: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class BankTxnRecord(Base):
    """
    Interbank SPEI and treasury wire transactions.
    Table: 'bank_txns'
    """
    __tablename__ = "bank_txns"

    txn_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    from_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    to_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class PurchaseOrderRecord(Base):
    """
    Corporate purchase orders and procurement requisitions.
    Table: 'purchase_orders'
    """
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    requester: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approver: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ContractRecord(Base):
    """
    Commercial service and supply contracts executed with vendors.
    Table: 'contracts'
    """
    __tablename__ = "contracts"

    contract_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    scope_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EmployeeRecord(Base):
    """
    Company employees and procurement officers.
    Table: 'employees'
    """
    __tablename__ = "employees"

    emp_id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bank_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    hire_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class EfosRecord(Base):
    """
    SAT Articulo 69-B blacklisted companies (Empresas que Facturan Operaciones Simuladas).
    Table: 'efos_list'
    """
    __tablename__ = "efos_list"

    rfc: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    publication_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ExhibitRecord(Base):
    """
    Catalog of evidentiary exhibits extracted during forensic audits.
    Table: 'exhibits'
    """
    __tablename__ = "exhibits"

    exhibit_id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    source_table: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    sentence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# -----------------------------------------------------------------------------
# Historic Data Estate Models (Persists historical runs with run_id)
# -----------------------------------------------------------------------------
class VendorHistoryRecord(Base):
    """Historical archive of vendors per pipeline run."""
    __tablename__ = "vendors_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    rfc: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registered_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class InvoiceHistoryRecord(Base):
    """Historical archive of invoices per pipeline run."""
    __tablename__ = "invoices_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    uuid: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    issuer_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    receiver_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    issue_date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    iva: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    concepto_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uso_cfdi: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    forma_pago: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    metodo_pago: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)


class LedgerHistoryRecord(Base):
    """Historical archive of general ledger entries per pipeline run."""
    __tablename__ = "ledger_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    entry_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    account_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    debit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), default=0.0, nullable=True)
    credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), default=0.0, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_uuid: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approver: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class BankTxnHistoryRecord(Base):
    """Historical archive of bank transactions per pipeline run."""
    __tablename__ = "bank_txns_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    txn_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    from_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    to_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class PurchaseOrderHistoryRecord(Base):
    """Historical archive of purchase orders per pipeline run."""
    __tablename__ = "purchase_orders_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    po_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    requester: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approver: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ContractHistoryRecord(Base):
    """Historical archive of contracts per pipeline run."""
    __tablename__ = "contracts_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    contract_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    scope_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EmployeeHistoryRecord(Base):
    """Historical archive of employees per pipeline run."""
    __tablename__ = "employees_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    emp_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bank_clabe: Mapped[Optional[str]] = mapped_column(String(18), index=True, nullable=True)
    hire_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class EfosHistoryRecord(Base):
    """Historical archive of SAT EFOS blacklists per pipeline run."""
    __tablename__ = "efos_list_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    rfc: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    publication_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ExhibitHistoryRecord(Base):
    """Historical archive of evidentiary exhibits per pipeline run."""
    __tablename__ = "exhibits_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    exhibit_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_table: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    sentence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


HISTORIC_TABLE_MODELS: Dict[str, Any] = {
    "vendors_history": VendorHistoryRecord,
    "invoices_history": InvoiceHistoryRecord,
    "ledger_history": LedgerHistoryRecord,
    "bank_txns_history": BankTxnHistoryRecord,
    "purchase_orders_history": PurchaseOrderHistoryRecord,
    "contracts_history": ContractHistoryRecord,
    "employees_history": EmployeeHistoryRecord,
    "efos_list_history": EfosHistoryRecord,
    "exhibits_history": ExhibitHistoryRecord,
}

ETHEREAL_TO_HISTORIC_MODELS: Dict[str, Any] = {
    "vendors": VendorHistoryRecord,
    "invoices": InvoiceHistoryRecord,
    "ledger": LedgerHistoryRecord,
    "bank_txns": BankTxnHistoryRecord,
    "purchase_orders": PurchaseOrderHistoryRecord,
    "contracts": ContractHistoryRecord,
    "employees": EmployeeHistoryRecord,
    "efos_list": EfosHistoryRecord,
    "exhibits": ExhibitHistoryRecord,
}

ESTATE_TABLE_MODELS: Dict[str, Any] = {
    "vendors": VendorRecord,
    "invoices": InvoiceRecord,
    "ledger": LedgerRecord,
    "bank_txns": BankTxnRecord,
    "purchase_orders": PurchaseOrderRecord,
    "contracts": ContractRecord,
    "employees": EmployeeRecord,
    "efos_list": EfosRecord,
    "exhibits": ExhibitRecord,
}


# -----------------------------------------------------------------------------
# Audit Reports Registry (persists generated forensic reports per run_id)
# -----------------------------------------------------------------------------
class AuditReportRecord(Base):
    """
    Persisted forensic audit report generated by an estate audit pipeline run.
    Stores the full enriched submission payload, rendered Markdown case file,
    and terminal verdict so past reports can be listed and reopened by run_id.
    Table: 'audit_reports'
    """
    __tablename__ = "audit_reports"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_rfc: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    estate_source: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    risk_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    total_amount_mxn: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report: Mapped[Dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    case_file_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verdict: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

