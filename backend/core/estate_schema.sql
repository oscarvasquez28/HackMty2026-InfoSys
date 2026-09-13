-- 1. Initialize TigerData Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 2. Targeted cleanup (replaces the destructive DO $$ block)
DROP TABLE IF EXISTS exhibits, efos_list, employees, contracts, purchase_orders, bank_txns, ledger, invoices, vendors CASCADE;

-- 3. Core Operational Tables
CREATE TABLE vendors (
    rfc             TEXT PRIMARY KEY,   -- 12-13 char Mexican tax id
    legal_name      TEXT,
    registered_date TEXT,               -- ISO 8601
    address         TEXT,
    bank_clabe      TEXT,               -- 18-digit Mexican interbank account
    category        TEXT,
    contact_email   TEXT
);

CREATE TABLE invoices (
    uuid          TEXT PRIMARY KEY,     -- CFDI UUID
    issuer_rfc    TEXT,
    receiver_rfc  TEXT,
    issue_date    TEXT,
    subtotal      NUMERIC(15,2),
    iva           NUMERIC(15,2),        -- 16% VAT
    total         NUMERIC(15,2),        -- cited for peso reconciliation
    concepto_text TEXT,                 -- free-text line description
    uso_cfdi      TEXT,                 -- SAT catalog code, e.g. G03
    forma_pago    TEXT,                 -- SAT catalog code, e.g. 03
    metodo_pago   TEXT,                 -- PUE | PPD
    status        TEXT                  -- vigente | cancelado
);

CREATE TABLE ledger (
    entry_id     INTEGER PRIMARY KEY,
    date         TEXT,
    account_code TEXT,
    account_name TEXT,
    debit        NUMERIC(15,2),
    credit       NUMERIC(15,2),
    description  TEXT,
    invoice_uuid TEXT,                  -- nullable; links a GL entry to an invoice
    cost_center  TEXT,
    approver     TEXT                   -- who signed off, or evidence that nobody did
);

CREATE TABLE bank_txns (
    txn_id     TEXT PRIMARY KEY,
    date       TEXT,
    from_clabe TEXT,
    to_clabe   TEXT,
    amount     NUMERIC(15,2),           -- cited for peso reconciliation
    reference  TEXT,
    channel    TEXT                     -- SPEI | cheque | efectivo
);

CREATE TABLE purchase_orders (
    po_id       TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    date        TEXT,
    amount      NUMERIC(15,2),
    requester   TEXT,
    approver    TEXT,                   -- the approval-limit trail lives here
    description TEXT
);

CREATE TABLE contracts (
    contract_id TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    start_date  TEXT,
    value       NUMERIC(15,2),
    scope_text  TEXT
);

CREATE TABLE employees (
    emp_id     TEXT PRIMARY KEY,        -- cited in Finding entities as "EMP:0001"
    name       TEXT,
    role       TEXT,
    bank_clabe TEXT,                    -- required for any employee-linkage scheme
    hire_date  TEXT
);

CREATE TABLE efos_list (
    rfc              TEXT PRIMARY KEY,
    legal_name       TEXT,
    status           TEXT,              -- definitivo | presunto
    publication_date TEXT
);

CREATE TABLE exhibits (
    exhibit_id      TEXT PRIMARY KEY,
    source_table    TEXT,
    record_id       TEXT,              -- specific uuid, txn_id, or entry_id being cited
    sentence        TEXT
);