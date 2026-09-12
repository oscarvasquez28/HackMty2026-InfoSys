"""
SQLAlchemy 2.0 ORM data models for the Forensic Auditor Data Estate.
Directly implements the schema defined in tmp/estate_schema - polar.sql,
conforming to CFDI 4.0 and Mexican corporate/tax compliance conventions.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.forensic import Base


class VendorRecord(Base):
    """
    Corporate and moral vendors / suppliers registered in the data estate.
    Table: 'vendors'
    """
    __tablename__ = "vendors"

    rfc: Mapped[str] = mapped_column(String(13), primary_key=True, index=True)
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
    issuer_rfc: Mapped[Optional[str]] = mapped_column(String(13), index=True, nullable=True)
    receiver_rfc: Mapped[Optional[str]] = mapped_column(String(13), index=True, nullable=True)
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
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(13), index=True, nullable=True)
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
    vendor_rfc: Mapped[Optional[str]] = mapped_column(String(13), index=True, nullable=True)
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

    rfc: Mapped[str] = mapped_column(String(13), primary_key=True, index=True)
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

