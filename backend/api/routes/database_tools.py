"""
Database Tools API Router for Forensic Auditor & n8n AI Agents.
Provides dedicated reading and inspection endpoints for every table in the financial data estate,
enabling adversarial reviewers and investigative agents to query records, verify material facts,
and persist evidentiary exhibits.
"""

from decimal import Decimal
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from backend.core.config import settings
from backend.models.estate import (
    BankTxnRecord,
    ContractRecord,
    EfosRecord,
    EmployeeRecord,
    ExhibitRecord,
    HISTORIC_TABLE_MODELS,
    InvoiceRecord,
    LedgerRecord,
    PurchaseOrderRecord,
    VendorRecord,
)
from backend.models.forensic import (
    AccountMappingRecord,
    AccountRecord,
    CashTransactionRecord,
    PartyRecord,
)
from backend.services.estate_connector import (
    ESTATE_AMOUNT_COLUMNS,
    ESTATE_ID_COLUMNS,
    ESTATE_TABLE_MODELS,
    estate_connector,
)

logger = logging.getLogger("forensic_auditor.database_tools")

router = APIRouter(prefix="/database", tags=["database-tools"])

# Union of all supported database models (estate ethereal + historic + core banking)
ALL_DATABASE_MODELS: Dict[str, Any] = {
    **ESTATE_TABLE_MODELS,
    **HISTORIC_TABLE_MODELS,
    "accounts": AccountRecord,
    "account_mappings": AccountMappingRecord,
    "parties": PartyRecord,
    "cash_transactions": CashTransactionRecord,
}

TABLE_PRIMARY_KEYS: Dict[str, str] = {
    **ESTATE_ID_COLUMNS,
    **{k: "history_id" for k in HISTORIC_TABLE_MODELS},
    "accounts": "acct_id",
    "account_mappings": "cust_acct_mapping_id",
    "parties": "party_id",
    "cash_transactions": "tran_id",
}

TABLE_METADATA: Dict[str, str] = {
    "vendors": "Corporate suppliers and moral persons registered in the active ethereal estate.",
    "invoices": "CFDI 4.0 electronic invoices emitted or received with tax and monetary subtotals in the active ethereal estate.",
    "ledger": "General ledger journal entries and accounting debit/credit records in the active ethereal estate.",
    "bank_txns": "Interbank SPEI and wire transfers across source and destination CLABEs in the active ethereal estate.",
    "purchase_orders": "Corporate requisitions, procurement approvals, and purchase orders in the active ethereal estate.",
    "contracts": "Commercial contracts and master service agreements with scopes of work in the active ethereal estate.",
    "employees": "Company personnel, procurement officers, and account signatories in the active ethereal estate.",
    "efos_list": "SAT Articulo 69-B blacklisted simulated operation vendors (empresas fantasma) in the active ethereal estate.",
    "exhibits": "Catalog of formal evidentiary exhibits registered by auditors and reviewers in the active ethereal estate.",
    **{k: f"Historical archive table for {k.replace('_history', '')} tagged with pipeline run_id." for k in HISTORIC_TABLE_MODELS},
    "accounts": "Internal bank accounts with status, currency, and KYC customer linkage.",
    "account_mappings": "Mappings linking accounts to customer/party records.",
    "parties": "Customer, individual, and organizational profiles.",
    "cash_transactions": "Cash transactions, ATM deposits, and cashouts.",
}


def serialize_model_instance(inst: Any, table_name: str) -> Dict[str, Any]:
    """Converts an ORM record into a JSON-serializable dictionary."""
    d: Dict[str, Any] = {}
    pk_col = TABLE_PRIMARY_KEYS.get(table_name)
    record_id = None

    for col in inst.__table__.columns:
        val = getattr(inst, col.name)
        if isinstance(val, Decimal):
            d[col.name] = float(val)
        elif hasattr(val, "isoformat"):
            d[col.name] = val.isoformat()
        else:
            d[col.name] = val
        if pk_col and col.name == pk_col:
            record_id = str(val)

    # Attach convenient exhibit evidence format
    if record_id:
        d["evidence_citation"] = {
            "source_table": table_name,
            "record_id": record_id,
        }

    from backend.core.masking import mask_sensitive_record
    return mask_sensitive_record(d)


def resolve_estate_target(estate_path: Optional[str] = None) -> Optional[Union[str, Path]]:
    """Resolves target database path or defaults to active estate/PostgreSQL."""
    if estate_path and estate_path.strip():
        return Path(estate_path.strip()).resolve()
    if settings.DATABASE_URL:
        return "default"
    # Check default estate file in data/
    default_sqlite = Path("data/estate.db")
    if default_sqlite.exists():
        return default_sqlite.resolve()
    return "default"


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class TableInfo(BaseModel):
    table_name: str
    description: str
    primary_key: str
    columns: List[str]
    total_records: int


class TablesCatalogResponse(BaseModel):
    total_tables: int
    tables: List[TableInfo]


class TableQueryResponse(BaseModel):
    table: str
    total: int
    limit: int
    offset: int
    records: List[Dict[str, Any]]


class TableQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    q: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class ExhibitCreateRequest(BaseModel):
    estate_path: Optional[str] = None
    exhibit_id: Optional[str] = Field(None, description="Optional custom exhibit ID (e.g. EX-ADV-001)")
    source_table: str = Field(..., description="Name of the source table cited (e.g. contracts, invoices)")
    record_id: str = Field(..., description="Record primary key cited in the source table")
    sentence: str = Field(..., description="Statement explaining what this evidence proves")


class ExhibitCreateResponse(BaseModel):
    status: str
    exhibit_id: str
    source_table: str
    record_id: str
    sentence: str
    verified: bool


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get(
    "/tables",
    response_model=TablesCatalogResponse,
    summary="List all database tables and schema catalog",
    description="Returns available database tables, column names, primary keys, and row counts.",
)
async def list_tables(
    estate_path: Optional[str] = Query(None, description="Path to SQLite data estate file"),
):
    target = resolve_estate_target(estate_path)
    result_tables: List[TableInfo] = []

    async with estate_connector.session_scope(target) as session:
        for tbl_name, model_cls in ALL_DATABASE_MODELS.items():
            col_names = [c.name for c in model_cls.__table__.columns]
            pk = TABLE_PRIMARY_KEYS.get(tbl_name, "id")
            try:
                count_stmt = select(func.count()).select_from(model_cls)
                row_count = (await session.execute(count_stmt)).scalar() or 0
            except Exception:
                row_count = 0

            result_tables.append(
                TableInfo(
                    table_name=tbl_name,
                    description=TABLE_METADATA.get(tbl_name, "Data estate table"),
                    primary_key=pk,
                    columns=col_names,
                    total_records=row_count,
                )
            )

    return TablesCatalogResponse(
        total_tables=len(result_tables),
        tables=result_tables,
    )


# -----------------------------------------------------------------------------
# Dedicated Table Endpoints for Adversarial Reviewer & AI Agent Tools
# -----------------------------------------------------------------------------
@router.get("/vendors", response_model=TableQueryResponse, summary="Query vendors table")
async def get_vendors(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    rfc: Optional[str] = Query(None),
    legal_name: Optional[str] = Query(None),
    bank_clabe: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search across RFC, legal name, address"),
):
    filters = {}
    if rfc:
        filters["rfc"] = rfc
    if legal_name:
        filters["legal_name"] = legal_name
    if bank_clabe:
        filters["bank_clabe"] = bank_clabe
    if category:
        filters["category"] = category
    return await _query_table_internal("vendors", estate_path, limit, offset, q, filters)


@router.get("/invoices", response_model=TableQueryResponse, summary="Query invoices table")
async def get_invoices(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    uuid: Optional[str] = Query(None),
    issuer_rfc: Optional[str] = Query(None),
    receiver_rfc: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    q: Optional[str] = Query(None, description="Search across UUID, RFCs, concepto_text"),
):
    filters = {}
    if uuid:
        filters["uuid"] = uuid
    if issuer_rfc:
        filters["issuer_rfc"] = issuer_rfc
    if receiver_rfc:
        filters["receiver_rfc"] = receiver_rfc
    if status:
        filters["status"] = status
    return await _query_table_internal(
        "invoices", estate_path, limit, offset, q, filters, min_amount=min_amount, max_amount=max_amount
    )


@router.get("/ledger", response_model=TableQueryResponse, summary="Query ledger table")
async def get_ledger(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    entry_id: Optional[int] = Query(None),
    account_code: Optional[str] = Query(None),
    invoice_uuid: Optional[str] = Query(None),
    approver: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search across description, account_name, approver"),
):
    filters = {}
    if entry_id is not None:
        filters["entry_id"] = entry_id
    if account_code:
        filters["account_code"] = account_code
    if invoice_uuid:
        filters["invoice_uuid"] = invoice_uuid
    if approver:
        filters["approver"] = approver
    return await _query_table_internal("ledger", estate_path, limit, offset, q, filters)


@router.get("/bank_txns", response_model=TableQueryResponse, summary="Query bank transactions table")
async def get_bank_txns(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    txn_id: Optional[str] = Query(None),
    from_clabe: Optional[str] = Query(None),
    to_clabe: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    q: Optional[str] = Query(None, description="Search across reference, CLABEs, txn_id"),
):
    filters = {}
    if txn_id:
        filters["txn_id"] = txn_id
    if from_clabe:
        filters["from_clabe"] = from_clabe
    if to_clabe:
        filters["to_clabe"] = to_clabe
    return await _query_table_internal(
        "bank_txns", estate_path, limit, offset, q, filters, min_amount=min_amount, max_amount=max_amount
    )


@router.get("/purchase_orders", response_model=TableQueryResponse, summary="Query purchase orders table")
async def get_purchase_orders(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    po_id: Optional[str] = Query(None),
    vendor_rfc: Optional[str] = Query(None),
    approver: Optional[str] = Query(None),
    requester: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    q: Optional[str] = Query(None, description="Search description, approver, requester"),
):
    filters = {}
    if po_id:
        filters["po_id"] = po_id
    if vendor_rfc:
        filters["vendor_rfc"] = vendor_rfc
    if approver:
        filters["approver"] = approver
    if requester:
        filters["requester"] = requester
    return await _query_table_internal(
        "purchase_orders", estate_path, limit, offset, q, filters, min_amount=min_amount, max_amount=max_amount
    )


@router.get("/contracts", response_model=TableQueryResponse, summary="Query contracts table")
async def get_contracts(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    contract_id: Optional[str] = Query(None),
    vendor_rfc: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    q: Optional[str] = Query(None, description="Search scope_text, contract_id, vendor_rfc"),
):
    filters = {}
    if contract_id:
        filters["contract_id"] = contract_id
    if vendor_rfc:
        filters["vendor_rfc"] = vendor_rfc
    return await _query_table_internal(
        "contracts", estate_path, limit, offset, q, filters, min_amount=min_value, max_amount=max_value
    )


@router.get("/employees", response_model=TableQueryResponse, summary="Query employees table")
async def get_employees(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    emp_id: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    bank_clabe: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search employee name, role, CLABE"),
):
    filters = {}
    if emp_id:
        filters["emp_id"] = emp_id
    if name:
        filters["name"] = name
    if role:
        filters["role"] = role
    if bank_clabe:
        filters["bank_clabe"] = bank_clabe
    return await _query_table_internal("employees", estate_path, limit, offset, q, filters)


@router.get("/efos_list", response_model=TableQueryResponse, summary="Query SAT EFOS blacklist")
async def get_efos_list(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    rfc: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search RFC or legal_name"),
):
    filters = {}
    if rfc:
        filters["rfc"] = rfc
    if status:
        filters["status"] = status
    return await _query_table_internal("efos_list", estate_path, limit, offset, q, filters)


@router.get("/exhibits", response_model=TableQueryResponse, summary="Query registered evidentiary exhibits")
async def get_exhibits(
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    exhibit_id: Optional[str] = Query(None),
    source_table: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search exhibit_id, record_id, sentence"),
):
    filters = {}
    if exhibit_id:
        filters["exhibit_id"] = exhibit_id
    if source_table:
        filters["source_table"] = source_table
    if record_id:
        filters["record_id"] = record_id
    return await _query_table_internal("exhibits", estate_path, limit, offset, q, filters)


@router.post(
    "/exhibits",
    response_model=ExhibitCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Insert new evidence into exhibits table",
    description="Registers an evidentiary exhibit cited by the adversarial reviewer into the database exhibits table.",
)
async def create_exhibit(req: ExhibitCreateRequest):
    """Inserts an evidence record into the exhibits table."""
    target = resolve_estate_target(req.estate_path)
    ex_id = req.exhibit_id or f"EX-ADV-{uuid.uuid4().hex[:8].upper()}"

    # Verify source table exists
    if req.source_table not in ALL_DATABASE_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_table '{req.source_table}'. Valid tables: {list(ALL_DATABASE_MODELS.keys())}",
        )

    # Verify the cited record exists in the source table
    source_model = ALL_DATABASE_MODELS[req.source_table]
    pk_col = TABLE_PRIMARY_KEYS.get(req.source_table)
    verified = False

    from sqlalchemy import text
    async with estate_connector.session_scope(target) as session:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS exhibits (
                exhibit_id VARCHAR(32) PRIMARY KEY,
                source_table VARCHAR(64),
                record_id VARCHAR(64),
                sentence TEXT
            );
        """))
        if pk_col and hasattr(source_model, pk_col):
            col_attr = getattr(source_model, pk_col)
            # Match string or integer
            try:
                val = int(req.record_id) if isinstance(getattr(source_model, pk_col).type.python_type, int) else str(req.record_id)
            except Exception:
                val = str(req.record_id)
            check_stmt = select(source_model).where(col_attr == val)
            found = (await session.execute(check_stmt)).scalar_one_or_none()
            verified = (found is not None)

        # Check if exhibit already exists; update or insert
        ex_stmt = select(ExhibitRecord).where(ExhibitRecord.exhibit_id == ex_id)
        existing_ex = (await session.execute(ex_stmt)).scalar_one_or_none()

        if existing_ex:
            existing_ex.source_table = req.source_table
            existing_ex.record_id = str(req.record_id)
            existing_ex.sentence = req.sentence
        else:
            new_ex = ExhibitRecord(
                exhibit_id=ex_id,
                source_table=req.source_table,
                record_id=str(req.record_id),
                sentence=req.sentence,
            )
            session.add(new_ex)

    # Dual persist into PostgreSQL history table
    try:
        from backend.services.estate_sync import estate_sync_service
        await estate_sync_service.persist_exhibits_dual(
            [{
                "exhibit_id": ex_id,
                "source_table": req.source_table,
                "record_id": str(req.record_id),
                "sentence": req.sentence,
            }],
            estate_target=target if target != "default" else None,
        )
    except Exception as sync_err:
        logger.warning(f"Could not dual sync exhibit {ex_id}: {sync_err}")

    return ExhibitCreateResponse(
        status="INSERTED",
        exhibit_id=ex_id,
        source_table=req.source_table,
        record_id=str(req.record_id),
        sentence=req.sentence,
        verified=verified,
    )


# -----------------------------------------------------------------------------
# Generic Dynamic Table Query & Record Lookup Endpoints
# -----------------------------------------------------------------------------
@router.get(
    "/{table_name}",
    response_model=TableQueryResponse,
    summary="Generic table query with search & pagination",
)
async def query_any_table(
    table_name: str,
    estate_path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
):
    return await _query_table_internal(
        table_name=table_name,
        estate_path=estate_path,
        limit=limit,
        offset=offset,
        q=q,
        min_amount=min_amount,
        max_amount=max_amount,
    )


@router.post(
    "/{table_name}/query",
    response_model=TableQueryResponse,
    summary="Structured JSON table query",
)
async def query_any_table_post(table_name: str, body: TableQueryRequest):
    return await _query_table_internal(
        table_name=table_name,
        estate_path=body.estate_path,
        limit=body.limit,
        offset=body.offset,
        q=body.q,
        filters=body.filters,
        min_amount=body.min_amount,
        max_amount=body.max_amount,
    )


@router.get(
    "/{table_name}/{record_id}",
    response_model=Dict[str, Any],
    summary="Direct single record lookup by primary key ID",
)
async def get_table_record_by_id(
    table_name: str,
    record_id: str,
    estate_path: Optional[str] = Query(None),
):
    clean_table = table_name.strip().lower()
    if clean_table not in ALL_DATABASE_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table '{clean_table}' not found. Available: {list(ALL_DATABASE_MODELS.keys())}",
        )

    model_cls = ALL_DATABASE_MODELS[clean_table]
    pk_col = TABLE_PRIMARY_KEYS.get(clean_table)
    if not pk_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No primary key defined for table '{clean_table}'.",
        )

    target = resolve_estate_target(estate_path)
    async with estate_connector.session_scope(target) as session:
        col_attr = getattr(model_cls, pk_col)
        # Attempt integer conversion if the column is integer
        try:
            val: Union[int, str] = int(record_id) if hasattr(col_attr.type, "python_type") and col_attr.type.python_type is int else record_id
        except Exception:
            val = record_id

        stmt = select(model_cls).where(col_attr == val)
        record = (await session.execute(stmt)).scalar_one_or_none()

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record '{record_id}' not found in table '{clean_table}'.",
            )
        return serialize_model_instance(record, clean_table)


# -----------------------------------------------------------------------------
# Internal Query Engine
# -----------------------------------------------------------------------------
async def _query_table_internal(
    table_name: str,
    estate_path: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
) -> TableQueryResponse:
    clean_table = table_name.strip().lower()
    if clean_table not in ALL_DATABASE_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table '{clean_table}' does not exist. Available tables: {list(ALL_DATABASE_MODELS.keys())}",
        )

    model_cls = ALL_DATABASE_MODELS[clean_table]
    target = resolve_estate_target(estate_path)

    clauses = []

    # 1. Apply column filters
    if filters:
        for col_name, val in filters.items():
            if hasattr(model_cls, col_name) and val is not None:
                col_attr = getattr(model_cls, col_name)
                if isinstance(val, str) and "%" in val:
                    clauses.append(col_attr.ilike(val))
                elif isinstance(val, str):
                    clauses.append(col_attr == val)
                else:
                    clauses.append(col_attr == val)

    # 2. Apply amount range if amount-bearing table
    amt_col_name = ESTATE_AMOUNT_COLUMNS.get(clean_table)
    if amt_col_name and hasattr(model_cls, amt_col_name):
        amt_attr = getattr(model_cls, amt_col_name)
        if min_amount is not None:
            clauses.append(amt_attr >= Decimal(str(min_amount)))
        if max_amount is not None:
            clauses.append(amt_attr <= Decimal(str(max_amount)))

    # 3. Free-text search query across string/text columns
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        or_clauses = []
        for col in model_cls.__table__.columns:
            if hasattr(col.type, "python_type") and col.type.python_type is str:
                or_clauses.append(getattr(model_cls, col.name).ilike(search_term))
        if or_clauses:
            clauses.append(or_(*or_clauses))

    try:
        async with estate_connector.session_scope(target) as session:
            # Total matching records count
            count_stmt = select(func.count()).select_from(model_cls)
            if clauses:
                count_stmt = count_stmt.where(*clauses)
            total = (await session.execute(count_stmt)).scalar() or 0

            # Query paginated slice
            query_stmt = select(model_cls)
            if clauses:
                query_stmt = query_stmt.where(*clauses)
            query_stmt = query_stmt.limit(limit).offset(offset)

            rows = (await session.execute(query_stmt)).scalars().all()
            serialized_records = [serialize_model_instance(r, clean_table) for r in rows]
    except Exception as exc:
        # Historic archive tables only exist in PostgreSQL; querying them against
        # a SQLite estate target should degrade to an empty result, not a 500.
        logger.warning(f"Table '{clean_table}' unavailable on target: {exc}")
        return TableQueryResponse(
            table=clean_table,
            total=0,
            limit=limit,
            offset=offset,
            records=[],
        )

    return TableQueryResponse(
        table=clean_table,
        total=total,
        limit=limit,
        offset=offset,
        records=serialized_records,
    )
