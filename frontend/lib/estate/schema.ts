// Mirrors student-materials/forensic-auditor/estate_schema.sql exactly: table order, column names,
// types, and primary keys. Every Finding exhibit's source_table cites one of these 8 tables by name,
// so column names must match the spec verbatim -- judges read these directly.

import { SOURCE_TABLES, type SourceTable } from "@/types/caseFile";
import type { EstateColumnSpec, EstateTables } from "@/types/estate";

export const ESTATE_TABLE_ORDER: SourceTable[] = [
  "vendors",
  "invoices",
  "ledger",
  "bank_txns",
  "purchase_orders",
  "contracts",
  "employees",
  "efos_list",
];

export const ESTATE_SCHEMA: Record<SourceTable, EstateColumnSpec[]> = {
  vendors: [
    { name: "rfc", type: "TEXT", primaryKey: true },
    { name: "legal_name", type: "TEXT", primaryKey: false },
    { name: "registered_date", type: "TEXT", primaryKey: false },
    { name: "address", type: "TEXT", primaryKey: false },
    { name: "bank_clabe", type: "TEXT", primaryKey: false },
    { name: "category", type: "TEXT", primaryKey: false },
    { name: "contact_email", type: "TEXT", primaryKey: false },
  ],
  invoices: [
    { name: "uuid", type: "TEXT", primaryKey: true },
    { name: "issuer_rfc", type: "TEXT", primaryKey: false },
    { name: "receiver_rfc", type: "TEXT", primaryKey: false },
    { name: "issue_date", type: "TEXT", primaryKey: false },
    { name: "subtotal", type: "REAL", primaryKey: false },
    { name: "iva", type: "REAL", primaryKey: false },
    { name: "total", type: "REAL", primaryKey: false },
    { name: "concepto_text", type: "TEXT", primaryKey: false },
    { name: "uso_cfdi", type: "TEXT", primaryKey: false },
    { name: "forma_pago", type: "TEXT", primaryKey: false },
    { name: "metodo_pago", type: "TEXT", primaryKey: false },
    { name: "status", type: "TEXT", primaryKey: false },
  ],
  ledger: [
    { name: "entry_id", type: "INTEGER", primaryKey: true },
    { name: "date", type: "TEXT", primaryKey: false },
    { name: "account_code", type: "TEXT", primaryKey: false },
    { name: "account_name", type: "TEXT", primaryKey: false },
    { name: "debit", type: "REAL", primaryKey: false },
    { name: "credit", type: "REAL", primaryKey: false },
    { name: "description", type: "TEXT", primaryKey: false },
    { name: "invoice_uuid", type: "TEXT", primaryKey: false },
    { name: "cost_center", type: "TEXT", primaryKey: false },
    { name: "approver", type: "TEXT", primaryKey: false },
  ],
  bank_txns: [
    { name: "txn_id", type: "TEXT", primaryKey: true },
    { name: "date", type: "TEXT", primaryKey: false },
    { name: "from_clabe", type: "TEXT", primaryKey: false },
    { name: "to_clabe", type: "TEXT", primaryKey: false },
    { name: "amount", type: "REAL", primaryKey: false },
    { name: "reference", type: "TEXT", primaryKey: false },
    { name: "channel", type: "TEXT", primaryKey: false },
  ],
  purchase_orders: [
    { name: "po_id", type: "TEXT", primaryKey: true },
    { name: "vendor_rfc", type: "TEXT", primaryKey: false },
    { name: "date", type: "TEXT", primaryKey: false },
    { name: "amount", type: "REAL", primaryKey: false },
    { name: "requester", type: "TEXT", primaryKey: false },
    { name: "approver", type: "TEXT", primaryKey: false },
    { name: "description", type: "TEXT", primaryKey: false },
  ],
  contracts: [
    { name: "contract_id", type: "TEXT", primaryKey: true },
    { name: "vendor_rfc", type: "TEXT", primaryKey: false },
    { name: "start_date", type: "TEXT", primaryKey: false },
    { name: "value", type: "REAL", primaryKey: false },
    { name: "scope_text", type: "TEXT", primaryKey: false },
  ],
  employees: [
    { name: "emp_id", type: "TEXT", primaryKey: true },
    { name: "name", type: "TEXT", primaryKey: false },
    { name: "role", type: "TEXT", primaryKey: false },
    { name: "bank_clabe", type: "TEXT", primaryKey: false },
    { name: "hire_date", type: "TEXT", primaryKey: false },
  ],
  efos_list: [
    { name: "rfc", type: "TEXT", primaryKey: true },
    { name: "legal_name", type: "TEXT", primaryKey: false },
    { name: "status", type: "TEXT", primaryKey: false },
    { name: "publication_date", type: "TEXT", primaryKey: false },
  ],
};

// Literal DDL from estate_schema.sql (comments and illustrative rows stripped), used verbatim to
// create the in-browser SQLite database exported as estate.db.
export const ESTATE_DDL = `
CREATE TABLE vendors (
    rfc             TEXT PRIMARY KEY,
    legal_name      TEXT,
    registered_date TEXT,
    address         TEXT,
    bank_clabe      TEXT,
    category        TEXT,
    contact_email   TEXT
);

CREATE TABLE invoices (
    uuid          TEXT PRIMARY KEY,
    issuer_rfc    TEXT,
    receiver_rfc  TEXT,
    issue_date    TEXT,
    subtotal      REAL,
    iva           REAL,
    total         REAL,
    concepto_text TEXT,
    uso_cfdi      TEXT,
    forma_pago    TEXT,
    metodo_pago   TEXT,
    status        TEXT
);

CREATE TABLE ledger (
    entry_id     INTEGER PRIMARY KEY,
    date         TEXT,
    account_code TEXT,
    account_name TEXT,
    debit        REAL,
    credit       REAL,
    description  TEXT,
    invoice_uuid TEXT,
    cost_center  TEXT,
    approver     TEXT
);

CREATE TABLE bank_txns (
    txn_id     TEXT PRIMARY KEY,
    date       TEXT,
    from_clabe TEXT,
    to_clabe   TEXT,
    amount     REAL,
    reference  TEXT,
    channel    TEXT
);

CREATE TABLE purchase_orders (
    po_id       TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    date        TEXT,
    amount      REAL,
    requester   TEXT,
    approver    TEXT,
    description TEXT
);

CREATE TABLE contracts (
    contract_id TEXT PRIMARY KEY,
    vendor_rfc  TEXT,
    start_date  TEXT,
    value       REAL,
    scope_text  TEXT
);

CREATE TABLE employees (
    emp_id     TEXT PRIMARY KEY,
    name       TEXT,
    role       TEXT,
    bank_clabe TEXT,
    hire_date  TEXT
);

CREATE TABLE efos_list (
    rfc              TEXT PRIMARY KEY,
    legal_name       TEXT,
    status           TEXT,
    publication_date TEXT
);
`;

export const REQUIRED_COLUMNS: Record<SourceTable, string[]> = {
  vendors: ["rfc", "legal_name"],
  invoices: ["uuid", "issuer_rfc", "receiver_rfc", "issue_date", "total"],
  ledger: ["entry_id", "date", "account_code"],
  bank_txns: ["txn_id", "date", "amount"],
  purchase_orders: ["po_id", "vendor_rfc", "amount"],
  contracts: ["contract_id", "vendor_rfc", "value"],
  employees: ["emp_id", "name", "bank_clabe"],
  efos_list: ["rfc", "status"],
};

export const MAX_ESTATE_FILE_BYTES = 50 * 1024 * 1024;
export const MAX_FILES_PER_BATCH = 50;
export const PREVIEW_PAGE_SIZE = 50;

export function emptyEstateTables(): EstateTables {
  const tables = {} as EstateTables;
  for (const table of SOURCE_TABLES) {
    tables[table] = [];
  }
  return tables;
}
