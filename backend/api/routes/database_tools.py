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

from fastapi import APIRouter, HTTPException, Query, Response, status
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


class TablesCatalogRequest(BaseModel):
    estate_path: Optional[str] = Field(None, description="Path to SQLite data estate file")


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


class VendorsQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    rfc: Optional[str] = None
    legal_name: Optional[str] = None
    bank_clabe: Optional[str] = None
    category: Optional[str] = None
    q: Optional[str] = Field(None, description="Search across RFC, legal name, address")


class InvoicesQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    uuid: Optional[str] = None
    issuer_rfc: Optional[str] = None
    receiver_rfc: Optional[str] = None
    status: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    q: Optional[str] = Field(None, description="Search across UUID, RFCs, concepto_text")


class LedgerQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    entry_id: Optional[int] = None
    account_code: Optional[str] = None
    invoice_uuid: Optional[str] = None
    approver: Optional[str] = None
    q: Optional[str] = Field(None, description="Search across description, account_name, approver")


class BankTxnsQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    txn_id: Optional[str] = None
    from_clabe: Optional[str] = None
    to_clabe: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    q: Optional[str] = Field(None, description="Search across reference, CLABEs, txn_id")


class PurchaseOrdersQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    po_id: Optional[str] = None
    vendor_rfc: Optional[str] = None
    approver: Optional[str] = None
    requester: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    q: Optional[str] = Field(None, description="Search description, approver, requester")


class ContractsQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    contract_id: Optional[str] = None
    vendor_rfc: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    q: Optional[str] = Field(None, description="Search scope_text, contract_id, vendor_rfc")


class EmployeesQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    emp_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    bank_clabe: Optional[str] = None
    q: Optional[str] = Field(None, description="Search employee name, role, CLABE")


class EfosListQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    rfc: Optional[str] = None
    status: Optional[str] = None
    q: Optional[str] = Field(None, description="Search RFC or legal_name")


class ExhibitsQueryRequest(BaseModel):
    estate_path: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    exhibit_id: Optional[str] = None
    source_table: Optional[str] = None
    record_id: Optional[str] = None
    q: Optional[str] = Field(None, description="Search exhibit_id, record_id, sentence")


class ExhibitCreateRequest(BaseModel):
    estate_path: Optional[str] = None
    exhibit_id: Optional[str] = Field(None, description="Optional custom exhibit ID (e.g. EX-ADV-001)")
    source_table: Optional[str] = Field(None, description="Name of the source table cited (e.g. contracts, invoices)")
    record_id: Optional[str] = Field(None, description="Record primary key cited in the source table")
    sentence: Optional[str] = Field(None, description="Statement explaining what this evidence proves")
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    q: Optional[str] = Field(None, description="Search exhibit_id, record_id, sentence")


class ExhibitCreateResponse(BaseModel):
    status: str
    exhibit_id: str
    source_table: str
    record_id: str
    sentence: str
    verified: bool


class RecordLookupRequest(BaseModel):
    estate_path: Optional[str] = None


class DirectRecordLookupRequest(BaseModel):
    table_name: str = Field(..., description="Target database table name")
    record_id: str = Field(..., description="Record primary key cited in the source table")
    estate_path: Optional[str] = None


class DatabaseDynamicQueryRequest(TableQueryRequest):
    table_name: str = Field(..., description="Target database table name")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
async def _list_tables_internal(estate_path: Optional[str] = None) -> TablesCatalogResponse:
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


@router.get(
    "/tables",
    response_model=TablesCatalogResponse,
    summary="List all database tables and schema catalog (GET)",
    description="Returns available database tables, column names, primary keys, and row counts.",
)
async def list_tables(
    estate_path: Optional[str] = Query(None, description="Path to SQLite data estate file"),
):
    return await _list_tables_internal(estate_path)


@router.post(
    "/tables",
    response_model=TablesCatalogResponse,
    summary="List all database tables and schema catalog (POST)",
    description="Returns available database tables, column names, primary keys, and row counts via POST body.",
)
async def list_tables_post(
    body: Optional[TablesCatalogRequest] = None,
):
    estate_path = body.estate_path if body else None
    return await _list_tables_internal(estate_path)


# -----------------------------------------------------------------------------
# Dedicated Table Endpoints for Adversarial Reviewer & AI Agent Tools
# -----------------------------------------------------------------------------
@router.get("/vendors", response_model=TableQueryResponse, summary="Query vendors table (GET)")
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


@router.post("/vendors", response_model=TableQueryResponse, summary="Query vendors table (POST)")
async def post_vendors(body: Optional[VendorsQueryRequest] = None):
    req = body or VendorsQueryRequest()
    filters = {}
    if req.rfc:
        filters["rfc"] = req.rfc
    if req.legal_name:
        filters["legal_name"] = req.legal_name
    if req.bank_clabe:
        filters["bank_clabe"] = req.bank_clabe
    if req.category:
        filters["category"] = req.category
    return await _query_table_internal("vendors", req.estate_path, req.limit, req.offset, req.q, filters)


@router.get("/invoices", response_model=TableQueryResponse, summary="Query invoices table (GET)")
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


@router.post("/invoices", response_model=TableQueryResponse, summary="Query invoices table (POST)")
async def post_invoices(body: Optional[InvoicesQueryRequest] = None):
    req = body or InvoicesQueryRequest()
    filters = {}
    if req.uuid:
        filters["uuid"] = req.uuid
    if req.issuer_rfc:
        filters["issuer_rfc"] = req.issuer_rfc
    if req.receiver_rfc:
        filters["receiver_rfc"] = req.receiver_rfc
    if req.status:
        filters["status"] = req.status
    return await _query_table_internal(
        "invoices", req.estate_path, req.limit, req.offset, req.q, filters, min_amount=req.min_amount, max_amount=req.max_amount
    )


@router.get("/ledger", response_model=TableQueryResponse, summary="Query ledger table (GET)")
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


@router.post("/ledger", response_model=TableQueryResponse, summary="Query ledger table (POST)")
async def post_ledger(body: Optional[LedgerQueryRequest] = None):
    req = body or LedgerQueryRequest()
    filters = {}
    if req.entry_id is not None:
        filters["entry_id"] = req.entry_id
    if req.account_code:
        filters["account_code"] = req.account_code
    if req.invoice_uuid:
        filters["invoice_uuid"] = req.invoice_uuid
    if req.approver:
        filters["approver"] = req.approver
    return await _query_table_internal("ledger", req.estate_path, req.limit, req.offset, req.q, filters)


@router.get("/bank_txns", response_model=TableQueryResponse, summary="Query bank transactions table (GET)")
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


@router.post("/bank_txns", response_model=TableQueryResponse, summary="Query bank transactions table (POST)")
async def post_bank_txns(body: Optional[BankTxnsQueryRequest] = None):
    req = body or BankTxnsQueryRequest()
    filters = {}
    if req.txn_id:
        filters["txn_id"] = req.txn_id
    if req.from_clabe:
        filters["from_clabe"] = req.from_clabe
    if req.to_clabe:
        filters["to_clabe"] = req.to_clabe
    return await _query_table_internal(
        "bank_txns", req.estate_path, req.limit, req.offset, req.q, filters, min_amount=req.min_amount, max_amount=req.max_amount
    )


@router.get("/purchase_orders", response_model=TableQueryResponse, summary="Query purchase orders table (GET)")
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


@router.post("/purchase_orders", response_model=TableQueryResponse, summary="Query purchase orders table (POST)")
async def post_purchase_orders(body: Optional[PurchaseOrdersQueryRequest] = None):
    req = body or PurchaseOrdersQueryRequest()
    filters = {}
    if req.po_id:
        filters["po_id"] = req.po_id
    if req.vendor_rfc:
        filters["vendor_rfc"] = req.vendor_rfc
    if req.approver:
        filters["approver"] = req.approver
    if req.requester:
        filters["requester"] = req.requester
    return await _query_table_internal(
        "purchase_orders", req.estate_path, req.limit, req.offset, req.q, filters, min_amount=req.min_amount, max_amount=req.max_amount
    )


@router.get("/contracts", response_model=TableQueryResponse, summary="Query contracts table (GET)")
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


@router.post("/contracts", response_model=TableQueryResponse, summary="Query contracts table (POST)")
async def post_contracts(body: Optional[ContractsQueryRequest] = None):
    req = body or ContractsQueryRequest()
    filters = {}
    if req.contract_id:
        filters["contract_id"] = req.contract_id
    if req.vendor_rfc:
        filters["vendor_rfc"] = req.vendor_rfc
    return await _query_table_internal(
        "contracts", req.estate_path, req.limit, req.offset, req.q, filters, min_amount=req.min_value, max_amount=req.max_value
    )


@router.get("/employees", response_model=TableQueryResponse, summary="Query employees table (GET)")
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


@router.post("/employees", response_model=TableQueryResponse, summary="Query employees table (POST)")
async def post_employees(body: Optional[EmployeesQueryRequest] = None):
    req = body or EmployeesQueryRequest()
    filters = {}
    if req.emp_id:
        filters["emp_id"] = req.emp_id
    if req.name:
        filters["name"] = req.name
    if req.role:
        filters["role"] = req.role
    if req.bank_clabe:
        filters["bank_clabe"] = req.bank_clabe
    return await _query_table_internal("employees", req.estate_path, req.limit, req.offset, req.q, filters)


@router.get("/efos_list", response_model=TableQueryResponse, summary="Query SAT EFOS blacklist (GET)")
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


@router.post("/efos_list", response_model=TableQueryResponse, summary="Query SAT EFOS blacklist (POST)")
async def post_efos_list(body: Optional[EfosListQueryRequest] = None):
    req = body or EfosListQueryRequest()
    filters = {}
    if req.rfc:
        filters["rfc"] = req.rfc
    if req.status:
        filters["status"] = req.status
    return await _query_table_internal("efos_list", req.estate_path, req.limit, req.offset, req.q, filters)


@router.get("/exhibits", response_model=TableQueryResponse, summary="Query registered evidentiary exhibits (GET)")
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


async def _create_exhibit_internal(req: ExhibitCreateRequest) -> ExhibitCreateResponse:
    """Internal implementation for inserting an evidence record into the exhibits table."""
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
                "note": req.sentence,
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


@router.post(
    "/exhibits",
    response_model=Union[ExhibitCreateResponse, TableQueryResponse],
    summary="Insert new evidence or query exhibits table (POST)",
    description="Registers an evidentiary exhibit if sentence is provided (HTTP 201), or queries exhibits if omitted (HTTP 200).",
)
async def create_exhibit(req: ExhibitCreateRequest, response: Response):
    """Inserts evidence into exhibits table or queries exhibits if sentence is omitted."""
    # If 'sentence' is provided, this is an exhibit creation/registration request
    if req.sentence and req.sentence.strip():
        if not req.source_table or not req.record_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_table and record_id are required when creating an exhibit.",
            )
        response.status_code = status.HTTP_201_CREATED
        return await _create_exhibit_internal(req)

    # Otherwise, this is a query request for exhibits
    response.status_code = status.HTTP_200_OK
    filters = {}
    if req.exhibit_id:
        filters["exhibit_id"] = req.exhibit_id
    if req.source_table:
        filters["source_table"] = req.source_table
    if req.record_id:
        filters["record_id"] = req.record_id
    return await _query_table_internal("exhibits", req.estate_path, req.limit, req.offset, req.q, filters)


@router.post(
    "/exhibits/query",
    response_model=TableQueryResponse,
    summary="Query registered evidentiary exhibits via dedicated POST route",
)
async def query_exhibits_post(body: Optional[ExhibitsQueryRequest] = None):
    req = body or ExhibitsQueryRequest()
    filters = {}
    if req.exhibit_id:
        filters["exhibit_id"] = req.exhibit_id
    if req.source_table:
        filters["source_table"] = req.source_table
    if req.record_id:
        filters["record_id"] = req.record_id
    return await _query_table_internal("exhibits", req.estate_path, req.limit, req.offset, req.q, filters)


@router.post(
    "/exhibits/search",
    response_model=TableQueryResponse,
    summary="Search registered evidentiary exhibits via dedicated POST route",
)
async def search_exhibits_post(body: Optional[ExhibitsQueryRequest] = None):
    return await query_exhibits_post(body)


# -----------------------------------------------------------------------------
# Generic Dynamic Table Query & Record Lookup Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/query",
    response_model=TableQueryResponse,
    summary="Dynamic table query via POST body",
)
async def query_table_dynamic(body: DatabaseDynamicQueryRequest):
    return await _query_table_internal(
        table_name=body.table_name,
        estate_path=body.estate_path,
        limit=body.limit,
        offset=body.offset,
        q=body.q,
        filters=body.filters,
        min_amount=body.min_amount,
        max_amount=body.max_amount,
    )


@router.post(
    "/record",
    response_model=Dict[str, Any],
    summary="Direct single record lookup via POST body",
)
async def post_record_lookup(body: DirectRecordLookupRequest):
    return await _get_table_record_by_id_internal(body.table_name, body.record_id, body.estate_path)


@router.get(
    "/{table_name}",
    response_model=TableQueryResponse,
    summary="Generic table query with search & pagination (GET)",
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
    "/{table_name}",
    response_model=TableQueryResponse,
    summary="Generic table query with search & pagination (POST)",
)
async def query_any_table_post_direct(
    table_name: str,
    body: Optional[TableQueryRequest] = None,
):
    req = body or TableQueryRequest()
    return await _query_table_internal(
        table_name=table_name,
        estate_path=req.estate_path,
        limit=req.limit,
        offset=req.offset,
        q=req.q,
        filters=req.filters,
        min_amount=req.min_amount,
        max_amount=req.max_amount,
    )


@router.post(
    "/{table_name}/query",
    response_model=TableQueryResponse,
    summary="Structured JSON table query (POST)",
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


async def _get_table_record_by_id_internal(
    table_name: str,
    record_id: str,
    estate_path: Optional[str] = None,
) -> Dict[str, Any]:
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


@router.get(
    "/{table_name}/{record_id}",
    response_model=Dict[str, Any],
    summary="Direct single record lookup by primary key ID (GET)",
)
async def get_table_record_by_id(
    table_name: str,
    record_id: str,
    estate_path: Optional[str] = Query(None),
):
    return await _get_table_record_by_id_internal(table_name, record_id, estate_path)


@router.post(
    "/{table_name}/{record_id}",
    response_model=Dict[str, Any],
    summary="Direct single record lookup by primary key ID (POST)",
)
async def post_table_record_by_id(
    table_name: str,
    record_id: str,
    body: Optional[RecordLookupRequest] = None,
):
    estate_path = body.estate_path if body else None
    return await _get_table_record_by_id_internal(table_name, record_id, estate_path)


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

    return TableQueryResponse(
        table=clean_table,
        total=total,
        limit=limit,
        offset=offset,
        records=serialized_records,
    )
