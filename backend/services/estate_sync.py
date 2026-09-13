"""
Estate Synchronization Service for Dual PostgreSQL Architecture.

Manages the dual-table data estate lifecycle:
1. Ethereal Tables (vendors, invoices, ledger, bank_txns, purchase_orders, contracts,
   employees, efos_list, exhibits):
   - Wiped (DELETE) on each pipeline run.
   - Populated with the fresh active dataset.
   - Polled by n8n agents and query tools without run ID filtering.
2. Historic Tables (vendors_history, invoices_history, ledger_history, bank_txns_history,
   purchase_orders_history, contracts_history, employees_history, efos_list_history,
   exhibits_history):
   - Preserves all previous pipeline runs.
   - Appends incoming records tagged with an immutable `run_id` and timestamp.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

import polars as pl
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_engine, get_session_factory
from backend.models.estate import (
    ETHEREAL_TO_HISTORIC_MODELS,
    ESTATE_TABLE_MODELS,
    HISTORIC_TABLE_MODELS,
    BankTxnHistoryRecord,
    BankTxnRecord,
    ContractHistoryRecord,
    ContractRecord,
    EfosHistoryRecord,
    EfosRecord,
    EmployeeHistoryRecord,
    EmployeeRecord,
    ExhibitHistoryRecord,
    ExhibitRecord,
    InvoiceHistoryRecord,
    InvoiceRecord,
    LedgerHistoryRecord,
    LedgerRecord,
    PurchaseOrderHistoryRecord,
    PurchaseOrderRecord,
    VendorHistoryRecord,
    VendorRecord,
)
from backend.models.forensic import Base
from backend.services.estate_connector import estate_connector

logger = logging.getLogger("forensic_auditor.estate_sync")

# Global active run ID tracker for current session
ACTIVE_RUN_ID: Optional[str] = None

# Deletion order respecting possible references
ETHEREAL_DELETE_ORDER = [
    ExhibitRecord,
    LedgerRecord,
    BankTxnRecord,
    InvoiceRecord,
    PurchaseOrderRecord,
    ContractRecord,
    EmployeeRecord,
    EfosRecord,
    VendorRecord,
]

# Ingestion order
ETHEREAL_INSERT_ORDER = [
    "vendors",
    "efos_list",
    "employees",
    "contracts",
    "purchase_orders",
    "invoices",
    "bank_txns",
    "ledger",
    "exhibits",
]

DECIMAL_COLUMNS: Dict[str, List[str]] = {
    "invoices": ["subtotal", "iva", "total"],
    "ledger": ["debit", "credit"],
    "bank_txns": ["amount"],
    "purchase_orders": ["amount"],
    "contracts": ["value"],
}


def generate_run_id(prefix: str = "RUN") -> str:
    """Generates a structured, chronological run identifier."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{ts}-{uid}"


def get_active_run_id() -> str:
    """Returns the currently active run ID or generates a fallback."""
    global ACTIVE_RUN_ID
    if not ACTIVE_RUN_ID:
        ACTIVE_RUN_ID = generate_run_id()
    return ACTIVE_RUN_ID


def set_active_run_id(run_id: str) -> None:
    """Explicitly sets the active run ID."""
    global ACTIVE_RUN_ID
    ACTIVE_RUN_ID = run_id


def sanitize_row_for_model(table_name: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Casts numbers and dates for SQLAlchemy ORM models."""
    d = dict(row)
    dec_cols = DECIMAL_COLUMNS.get(table_name, [])
    for col in dec_cols:
        val = d.get(col)
        if val is not None and val != "":
            try:
                d[col] = Decimal(str(round(float(val), 2)))
            except Exception:
                d[col] = Decimal("0.00")
        else:
            d[col] = Decimal("0.00")

    # Ensure integer fields
    if table_name == "ledger" and "entry_id" in d:
        try:
            d["entry_id"] = int(d["entry_id"])
        except Exception:
            pass

    return d


class EstateSyncService:
    """
    Coordinates synchronization of incoming data estates into PostgreSQL dual tables.
    """

    async def ensure_schema_provisioned(self) -> None:
        """Ensures all ethereal and historic tables are provisioned in PostgreSQL."""
        if not settings.DATABASE_URL:
            return
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Ensured all dual estate tables are created in PostgreSQL.")
        except Exception as exc:
            logger.warning(f"Could not verify schema provisioning: {exc}")

    async def sync_estate_to_postgres(
        self,
        estate_target: Union[str, Path],
        run_id: Optional[str] = None,
    ) -> str:
        """
        Main pipeline hook:
        1. Generates and sets a new run_id.
        2. Ensures PostgreSQL schema exists.
        3. Clears ethereal tables in PostgreSQL.
        4. Loads all estate tables from incoming source (SQLite .db file or memory).
        5. Bulk-inserts into ethereal tables (no run_id).
        6. Bulk-inserts into historic tables (tagged with run_id).
        """
        assigned_run_id = run_id or generate_run_id()
        set_active_run_id(assigned_run_id)

        if not settings.DATABASE_URL:
            logger.info("DATABASE_URL not configured. Running offline without PostgreSQL sync.")
            return assigned_run_id

        # Provision schema if needed
        await self.ensure_schema_provisioned()

        factory = get_session_factory()
        logger.info(f"[*] Beginning dual database sync for estate: {estate_target} (Run ID: {assigned_run_id})")

        # 1. Load data from source estate via Polars
        loaded_data: Dict[str, List[Dict[str, Any]]] = {}
        for tbl in ETHEREAL_INSERT_ORDER:
            try:
                df = await estate_connector.load_table_as_polars(tbl, target=estate_target)
                if not df.is_empty():
                    loaded_data[tbl] = [
                        sanitize_row_for_model(tbl, r) for r in df.iter_rows(named=True)
                    ]
                else:
                    loaded_data[tbl] = []
            except Exception as e:
                logger.warning(f"Could not load table '{tbl}' from source estate: {e}")
                loaded_data[tbl] = []

        total_source_records = sum(len(rows) for rows in loaded_data.values())

        # 2. Database transaction: Clear ethereal & Insert both ethereal and historic
        async with factory() as session:
            try:
                # Clear all ethereal tables
                for model_cls in ETHEREAL_DELETE_ORDER:
                    await session.execute(delete(model_cls))
                await session.flush()
                logger.info("Cleared all ethereal tables in PostgreSQL.")

                ethereal_objects: List[Any] = []
                historic_objects: List[Any] = []

                for tbl in ETHEREAL_INSERT_ORDER:
                    rows = loaded_data.get(tbl, [])
                    ethereal_cls = ESTATE_TABLE_MODELS[tbl]
                    historic_cls = ETHEREAL_TO_HISTORIC_MODELS[tbl]

                    for row in rows:
                        # Ethereal instance (normal columns)
                        ethereal_objects.append(ethereal_cls(**row))

                        # Historic instance (includes run_id)
                        hist_row = dict(row)
                        hist_row["run_id"] = assigned_run_id
                        historic_objects.append(historic_cls(**hist_row))

                # Bulk insert in batches to handle large datasets efficiently
                BATCH_SIZE = 500
                for i in range(0, len(ethereal_objects), BATCH_SIZE):
                    session.add_all(ethereal_objects[i : i + BATCH_SIZE])
                for i in range(0, len(historic_objects), BATCH_SIZE):
                    session.add_all(historic_objects[i : i + BATCH_SIZE])

                await session.commit()
                logger.info(
                    f"[+] Successfully synced {total_source_records} records to PostgreSQL: "
                    f"{len(ethereal_objects)} into ethereal tables, {len(historic_objects)} into historic tables "
                    f"with Run ID: {assigned_run_id}"
                )

            except Exception as exc:
                await session.rollback()
                logger.error(f"Failed during dual database sync to PostgreSQL: {exc}")
                raise

        return assigned_run_id

    async def persist_exhibits_dual(
        self,
        exhibits: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        estate_target: Optional[Union[str, Path]] = None,
    ) -> int:
        """
        Persists evidentiary exhibits into:
        1. The source estate exhibits table (e.g. SQLite .db file).
        2. The PostgreSQL ethereal exhibits table.
        3. The PostgreSQL exhibits_history table with run_id.
        """
        if not exhibits:
            return 0

        active_run = run_id or get_active_run_id()

        # 1. Persist to local SQLite estate if target provided
        if estate_target is not None:
            try:
                from backend.services.exhibit_builder import exhibit_builder
                await exhibit_builder.persist_exhibits_to_estate(exhibits, estate_target)
            except Exception as exc:
                logger.warning(f"Error persisting exhibits to local estate: {exc}")

        # 2. Persist to PostgreSQL dual tables
        if not settings.DATABASE_URL:
            return len(exhibits)

        inserted = 0
        factory = get_session_factory()
        async with factory() as session:
            try:
                for ex in exhibits:
                    ex_id = str(ex.get("exhibit_id", f"EX-{uuid.uuid4().hex[:6].upper()}"))
                    src = str(ex.get("source_table", "invoices"))
                    rid = str(ex.get("record_id", ""))
                    stmt = str(ex.get("note") or ex.get("sentence", ""))

                    # Upsert to ethereal exhibits table
                    existing = (
                        await session.execute(
                            select(ExhibitRecord).where(ExhibitRecord.exhibit_id == ex_id)
                        )
                    ).scalar_one_or_none()

                    if existing:
                        existing.source_table = src
                        existing.record_id = rid
                        existing.sentence = stmt
                    else:
                        session.add(
                            ExhibitRecord(
                                exhibit_id=ex_id,
                                source_table=src,
                                record_id=rid,
                                sentence=stmt,
                            )
                        )

                    # Append to historic exhibits table
                    session.add(
                        ExhibitHistoryRecord(
                            run_id=active_run,
                            exhibit_id=ex_id,
                            source_table=src,
                            record_id=rid,
                            sentence=stmt,
                        )
                    )
                    inserted += 1

                await session.commit()
                logger.info(f"Persisted {inserted} exhibits to dual PostgreSQL tables (run_id: {active_run})")
            except Exception as exc:
                await session.rollback()
                logger.error(f"Failed to persist exhibits to PostgreSQL: {exc}")

        return inserted


estate_sync_service = EstateSyncService()

