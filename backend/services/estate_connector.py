"""
Estate Connector Service for Forensic Auditor Data Estates.
Supports dynamic switching between TigerData/PostgreSQL and runtime SQLite (.db) estates,
schema provisioning from tmp/estate_schema - polar.sql, high-throughput Polars table loading,
and exhibit reconciliation.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, Union

import polars as pl
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.core.config import settings
from backend.core.database import (
    create_engine_and_sessionmaker,
    get_engine,
    get_session_factory,
    normalize_database_url,
    provision_estate_schema,
)
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
from backend.models.forensic import Base

logger = logging.getLogger("forensic_auditor.estate_connector")

# Table name to ORM model mapping
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

# Column configuration matching validate_format.py
ESTATE_ID_COLUMNS: Dict[str, str] = {
    "ledger": "entry_id",
    "invoices": "uuid",
    "bank_txns": "txn_id",
    "vendors": "rfc",
    "efos_list": "rfc",
    "purchase_orders": "po_id",
    "contracts": "contract_id",
    "employees": "emp_id",
    "exhibits": "exhibit_id",
}

ESTATE_AMOUNT_COLUMNS: Dict[str, str] = {
    "invoices": "total",
    "bank_txns": "amount",
    "purchase_orders": "amount",
    "contracts": "value",
}


class EstateConnector:
    """
    Unified manager for interacting with the Forensic Auditor Data Estate.
    Can query the default PostgreSQL / TigerData instance or dynamically connect
    to an SQLite database path specified at runtime (e.g. for offline evaluation).
    """

    def __init__(self) -> None:
        # Cache for dynamically instantiated SQLite engines and sessionmakers
        self._dynamic_engines: Dict[str, Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = {}

    def _normalize_target(self, target: Optional[Union[str, Path]]) -> str:
        """
        Normalizes a target database specifier to a canonical string key.
        Returns:
            - 'default' if target is None or empty.
            - 'sqlite+aiosqlite:///:memory:' for in-memory SQLite.
            - 'sqlite+aiosqlite:///<absolute_path>' for SQLite files.
            - Normalized PostgreSQL URL if already a postgres URI.
        """
        if target is None:
            return "default"

        target_str = str(target).strip()
        if not target_str or target_str.lower() in ("default", "none"):
            return "default"

        if target_str == ":memory:":
            return "sqlite+aiosqlite:///:memory:"

        if target_str.startswith("sqlite"):
            if not target_str.startswith("sqlite+aiosqlite"):
                target_str = target_str.replace("sqlite://", "sqlite+aiosqlite://")
            return target_str

        if target_str.startswith(("postgresql", "postgres")):
            return target_str

        # Assume filesystem path to SQLite database file
        resolved_path = Path(target_str).resolve().as_posix()
        return f"sqlite+aiosqlite:///{resolved_path}"

    def get_engine_and_factory(
        self, target: Optional[Union[str, Path]] = None
    ) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        """
        Retrieves or creates an (AsyncEngine, async_sessionmaker) pair for the specified target.
        """
        key = self._normalize_target(target)

        if key == "default":
            return get_engine(), get_session_factory()

        if key not in self._dynamic_engines:
            logger.info(f"Creating dynamic estate engine for target: {key}")
            if "sqlite" in key:
                connect_args: Dict[str, Any] = {"check_same_thread": False}
                engine = create_async_engine(
                    key,
                    echo=settings.DB_ECHO,
                    poolclass=StaticPool,
                    connect_args=connect_args,
                )
                factory = async_sessionmaker(
                    bind=engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
                self._dynamic_engines[key] = (engine, factory)
            else:
                engine, factory = create_engine_and_sessionmaker(key)
                self._dynamic_engines[key] = (engine, factory)

        return self._dynamic_engines[key]

    @asynccontextmanager
    async def session_scope(
        self, target: Optional[Union[str, Path]] = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager yielding a transactional AsyncSession.
        Commits on normal exit, rolls back on exceptions.
        """
        _, factory = self.get_engine_and_factory(target)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def get_sync_connection(self, target: Union[str, Path]) -> sqlite3.Connection:
        """
        Returns a synchronous standard-library sqlite3.Connection for direct
        evaluation harness compatibility (matching validate_format.py).
        """
        key = self._normalize_target(target)
        if not key.startswith("sqlite"):
            raise ValueError(f"get_sync_connection only supports SQLite targets, got: {key}")

        if key == "sqlite+aiosqlite:///:memory:":
            raw_path = ":memory:"
        else:
            raw_path = key.replace("sqlite+aiosqlite:///", "")

        conn = sqlite3.connect(raw_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init_schema(
        self, target: Optional[Union[str, Path]] = None, ddl_path: Optional[Path] = None
    ) -> None:
        """
        Creates all estate tables in the target database from estate_schema - polar.sql
        and ensures the 9 historic archive tables exist.
        """
        engine, _ = self.get_engine_and_factory(target)

        async with engine.begin() as conn:
            await provision_estate_schema(conn, engine.dialect.name, ddl_path=ddl_path)

        logger.info(f"Initialized estate schema successfully on target: {self._normalize_target(target)}")

    async def get_estate_summary(
        self, target: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Inspects the target estate database and returns row counts and metadata
        for all 9 estate tables.
        """
        summary: Dict[str, int] = {}
        engine, _ = self.get_engine_and_factory(target)

        async with self.session_scope(target) as session:
            for table_name, model_cls in ESTATE_TABLE_MODELS.items():
                try:
                    stmt = select(func.count()).select_from(model_cls)
                    count = (await session.execute(stmt)).scalar() or 0
                    summary[table_name] = count
                except Exception as exc:
                    logger.warning(f"Could not count table '{table_name}': {exc}")
                    summary[table_name] = -1

        return {
            "target": self._normalize_target(target),
            "dialect": engine.dialect.name,
            "table_counts": summary,
            "total_records": sum(c for c in summary.values() if c > 0),
        }

    async def load_table_as_polars(
        self, table_name: str, target: Optional[Union[str, Path]] = None
    ) -> pl.DataFrame:
        """
        Loads an entire estate table into an in-memory Polars DataFrame
        for high-throughput vector and graph processing.
        """
        if table_name not in ESTATE_TABLE_MODELS:
            raise ValueError(
                f"Unknown estate table '{table_name}'. Valid tables: {sorted(list(ESTATE_TABLE_MODELS.keys()))}"
            )

        model_cls = ESTATE_TABLE_MODELS[table_name]

        async with self.session_scope(target) as session:
            stmt = select(model_cls)
            res = await session.execute(stmt)
            rows = res.scalars().all()

        if not rows:
            # Return empty DataFrame with column names from model
            cols = [c.name for c in model_cls.__table__.columns]
            return pl.DataFrame(schema=cols)

        # Convert ORM instances to dictionaries
        dicts: List[Dict[str, Any]] = []
        for r in rows:
            d = {}
            for col in model_cls.__table__.columns:
                val = getattr(r, col.name)
                # Convert Decimals to float for Polars compatibility if needed
                if hasattr(val, "as_tuple"):
                    val = float(val)
                d[col.name] = val
            dicts.append(d)

        return pl.DataFrame(dicts)

    async def verify_exhibits(
        self,
        exhibits: List[Dict[str, Any]],
        claimed_amount: Optional[float] = None,
        target: Optional[Union[str, Path]] = None,
        tolerance: float = 0.02,
    ) -> Dict[str, Any]:
        """
        Validates a list of cited exhibits against the estate database:
        - Confirms every record_id exists in source_table.
        - Computes per-table sums for amount-bearing tables.
        - Verifies whether claimed_amount reconciles to best matching table within tolerance.
        """
        errors: List[str] = []
        per_table_totals: Dict[str, float] = {}

        async with self.session_scope(target) as session:
            for j, ex in enumerate(exhibits):
                tbl = ex.get("source_table")
                rid = str(ex.get("record_id", "")).strip()

                if tbl not in ESTATE_TABLE_MODELS:
                    errors.append(f"Exhibit[{j}]: unknown source_table '{tbl}'")
                    continue

                col_name = ESTATE_ID_COLUMNS.get(tbl)
                if not col_name:
                    errors.append(f"Exhibit[{j}]: no ID column defined for table '{tbl}'")
                    continue

                model_cls = ESTATE_TABLE_MODELS[tbl]
                col_attr = getattr(model_cls, col_name, None)
                if col_attr is None:
                    errors.append(f"Exhibit[{j}]: attribute '{col_name}' missing on {tbl}")
                    continue

                stmt = select(model_cls).where(col_attr == rid)
                row = (await session.execute(stmt)).scalar_one_or_none()

                if row is None:
                    errors.append(f"Exhibit[{j}]: {tbl}.{rid} does not exist in estate")
                    continue

                # Accumulate amount if table is amount-bearing
                amt_col = ESTATE_AMOUNT_COLUMNS.get(tbl)
                if amt_col and hasattr(row, amt_col):
                    raw_val = getattr(row, amt_col)
                    amt_float = float(raw_val or 0.0)
                    per_table_totals[tbl] = per_table_totals.get(tbl, 0.0) + amt_float

        # Check peso reconciliation if claimed_amount is provided
        reconciled = False
        reconciliation_detail = ""

        if claimed_amount is not None:
            claimed_float = float(claimed_amount)
            if per_table_totals:
                best_diff = float("inf")
                best_table = ""
                for tbl, total in per_table_totals.items():
                    diff = abs(claimed_float - total)
                    if diff < best_diff:
                        best_diff = diff
                        best_table = tbl

                best_sum = per_table_totals[best_table]
                allowed_margin = tolerance * max(best_sum, 1.0)
                if best_diff <= allowed_margin:
                    reconciled = True
                    reconciliation_detail = (
                        f"Reconciled within {tolerance * 100}% against table '{best_table}' "
                        f"(claimed={claimed_float:,.2f}, table_sum={best_sum:,.2f}, diff={best_diff:,.2f})"
                    )
                else:
                    detail_str = ", ".join(f"{t}={v:,.2f}" for t, v in sorted(per_table_totals.items()))
                    errors.append(
                        f"Claimed peso_amount {claimed_float:,.2f} does not reconcile to cited exhibits: [{detail_str}]"
                    )
            else:
                errors.append("No exhibit cites an amount-bearing table (invoices, bank_txns, purchase_orders, contracts)")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "reconciled": reconciled,
            "reconciliation_detail": reconciliation_detail,
            "per_table_totals": per_table_totals,
        }

    async def dispose_all(self) -> None:
        """Disposes all cached dynamic engines."""
        for key, (engine, _) in list(self._dynamic_engines.items()):
            try:
                await engine.dispose()
            except Exception as exc:
                logger.warning(f"Error disposing engine for '{key}': {exc}")
        self._dynamic_engines.clear()


# Global singleton instance
estate_connector = EstateConnector()

