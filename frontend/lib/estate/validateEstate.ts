// Folds every imported file's contributions into one EstateTables (first occurrence of a primary key
// wins, later duplicates are reported and dropped) and runs estate-wide content checks: RFC/CLABE/date
// formats, CFDI enums, invoice arithmetic, and referential integrity against vendors/invoices.

import type { SourceTable } from "@/types/caseFile";
import { SOURCE_TABLES } from "@/types/caseFile";
import type { EstateFileEntry, EstateIssue, EstateTables } from "@/types/estate";
import { ID_COLUMN } from "@/lib/caseFile/constants";
import { REQUIRED_COLUMNS, emptyEstateTables } from "@/lib/estate/schema";

const RFC_COLUMNS: Array<{ table: SourceTable; column: string }> = [
  { table: "vendors", column: "rfc" },
  { table: "efos_list", column: "rfc" },
  { table: "invoices", column: "issuer_rfc" },
  { table: "invoices", column: "receiver_rfc" },
  { table: "purchase_orders", column: "vendor_rfc" },
  { table: "contracts", column: "vendor_rfc" },
];

const CLABE_COLUMNS: Array<{ table: SourceTable; column: string }> = [
  { table: "vendors", column: "bank_clabe" },
  { table: "employees", column: "bank_clabe" },
  { table: "bank_txns", column: "from_clabe" },
  { table: "bank_txns", column: "to_clabe" },
];

const DATE_COLUMNS: Array<{ table: SourceTable; column: string }> = [
  { table: "vendors", column: "registered_date" },
  { table: "invoices", column: "issue_date" },
  { table: "ledger", column: "date" },
  { table: "bank_txns", column: "date" },
  { table: "purchase_orders", column: "date" },
  { table: "contracts", column: "start_date" },
  { table: "employees", column: "hire_date" },
  { table: "efos_list", column: "publication_date" },
];

const RFC_RE = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/;
const CLABE_RE = /^\d{18}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/;
const EMP_ID_RE = /^EMP:\d{4}$/;

function warn(code: string, message: string, table: SourceTable | null, column: string | null, fileName: string | null = null): EstateIssue {
  return { severity: "warning", code, message, fileName, table, rowIndex: null, column };
}

function foldContributions(files: EstateFileEntry[]): { tables: EstateTables; issues: EstateIssue[] } {
  const tables = emptyEstateTables();
  const issues: EstateIssue[] = [];
  const seenKeys: Record<SourceTable, Set<string>> = {} as Record<SourceTable, Set<string>>;
  for (const table of SOURCE_TABLES) seenKeys[table] = new Set();

  for (const file of files) {
    if (file.status !== "imported") continue;
    for (const table of SOURCE_TABLES) {
      const rows = file.contributions[table];
      if (!rows) continue;
      const pkColumn = ID_COLUMN[table];
      for (const row of rows) {
        const pk = row[pkColumn];
        if (pk === null || pk === undefined || pk === "") {
          issues.push({ severity: "error", code: "E_PK_EMPTY", message: `${table} row in ${file.fileName} has an empty ${pkColumn} and was dropped.`, fileName: file.fileName, table, rowIndex: null, column: pkColumn });
          continue;
        }
        const key = String(pk);
        if (seenKeys[table].has(key)) {
          issues.push({ severity: "error", code: "E_DUPLICATE_PK", message: `${table}.${pkColumn} '${key}' appears again in ${file.fileName}; the first occurrence was kept.`, fileName: file.fileName, table, rowIndex: null, column: pkColumn });
          continue;
        }
        seenKeys[table].add(key);
        tables[table].push(row);
      }
    }
  }

  return { tables, issues };
}

function checkFormats(tables: EstateTables, issues: EstateIssue[]) {
  for (const { table, column } of RFC_COLUMNS) {
    for (const row of tables[table]) {
      const value = row[column];
      if (typeof value === "string" && !RFC_RE.test(value)) {
        issues.push(warn("W_RFC_FORMAT", `${table}.${column} '${value}' does not look like a valid RFC.`, table, column));
      }
    }
  }
  for (const { table, column } of CLABE_COLUMNS) {
    for (const row of tables[table]) {
      const value = row[column];
      if (typeof value === "string" && !CLABE_RE.test(value)) {
        issues.push(warn("W_CLABE_FORMAT", `${table}.${column} '${value}' is not an 18-digit CLABE.`, table, column));
      }
    }
  }
  for (const { table, column } of DATE_COLUMNS) {
    for (const row of tables[table]) {
      const value = row[column];
      if (typeof value === "string" && !DATE_RE.test(value)) {
        issues.push(warn("W_DATE_FORMAT", `${table}.${column} '${value}' is not an ISO 8601 date.`, table, column));
      }
    }
  }
}

function checkEnums(tables: EstateTables, issues: EstateIssue[]) {
  for (const row of tables.invoices) {
    const metodo = row.metodo_pago;
    if (typeof metodo === "string" && metodo !== "PUE" && metodo !== "PPD") {
      issues.push(warn("W_ENUM_VALUE", `invoices.metodo_pago '${metodo}' is not PUE or PPD.`, "invoices", "metodo_pago"));
    }
    const status = row.status;
    if (typeof status === "string" && status !== "vigente" && status !== "cancelado") {
      issues.push(warn("W_ENUM_VALUE", `invoices.status '${status}' is not vigente or cancelado.`, "invoices", "status"));
    }
  }
  for (const row of tables.bank_txns) {
    const channel = row.channel;
    if (typeof channel === "string" && channel !== "SPEI" && channel !== "cheque" && channel !== "efectivo") {
      issues.push(warn("W_ENUM_VALUE", `bank_txns.channel '${channel}' is not SPEI, cheque or efectivo.`, "bank_txns", "channel"));
    }
  }
  for (const row of tables.efos_list) {
    const status = row.status;
    if (typeof status === "string" && status !== "definitivo" && status !== "presunto") {
      issues.push(warn("W_ENUM_VALUE", `efos_list.status '${status}' is not definitivo or presunto.`, "efos_list", "status"));
    }
  }
}

function checkInvoiceArithmetic(tables: EstateTables, issues: EstateIssue[]) {
  for (const row of tables.invoices) {
    const subtotal = typeof row.subtotal === "number" ? row.subtotal : null;
    const iva = typeof row.iva === "number" ? row.iva : null;
    const total = typeof row.total === "number" ? row.total : null;
    if (subtotal !== null && iva !== null && Math.abs(iva - 0.16 * subtotal) > 0.01) {
      issues.push(warn("W_IVA_RATE", `invoices.uuid '${row.uuid}' has iva ${iva} but 16% of subtotal ${subtotal} is ${(0.16 * subtotal).toFixed(2)}.`, "invoices", "iva"));
    }
    if (subtotal !== null && iva !== null && total !== null && Math.abs(total - (subtotal + iva)) > 0.01) {
      issues.push(warn("W_TOTAL_MISMATCH", `invoices.uuid '${row.uuid}' has total ${total} but subtotal + iva is ${(subtotal + iva).toFixed(2)}.`, "invoices", "total"));
    }
  }
}

function checkLedger(tables: EstateTables, issues: EstateIssue[]) {
  for (const row of tables.ledger) {
    const debit = typeof row.debit === "number" ? row.debit : 0;
    const credit = typeof row.credit === "number" ? row.credit : 0;
    if (debit > 0 && credit > 0) {
      issues.push(warn("W_LEDGER_BOTH_SIDES", `ledger.entry_id ${row.entry_id} has both a debit and a credit amount.`, "ledger", "debit"));
    }
  }
}

function checkEmployeeIds(tables: EstateTables, issues: EstateIssue[]) {
  for (const row of tables.employees) {
    const empId = row.emp_id;
    if (typeof empId === "string" && !EMP_ID_RE.test(empId)) {
      issues.push(warn("W_EMP_ID_FORMAT", `employees.emp_id '${empId}' does not match the EMP:0000 format cited in Finding entities.`, "employees", "emp_id"));
    }
  }
}

function checkRequiredColumns(tables: EstateTables, issues: EstateIssue[]) {
  for (const table of SOURCE_TABLES) {
    const required = REQUIRED_COLUMNS[table];
    for (const row of tables[table]) {
      for (const column of required) {
        if (row[column] === null) {
          issues.push(warn("W_REQUIRED_EMPTY", `${table}.${column} is required but empty for one or more rows.`, table, column));
        }
      }
    }
  }
}

function checkReferences(tables: EstateTables, issues: EstateIssue[]) {
  const vendorRfcs = new Set(tables.vendors.map((r) => r.rfc));
  const invoiceUuids = new Set(tables.invoices.map((r) => r.uuid));

  for (const row of [...tables.purchase_orders, ...tables.contracts]) {
    const vendorRfc = row.vendor_rfc;
    if (vendorRfc !== null && !vendorRfcs.has(vendorRfc)) {
      issues.push(warn("W_REF_VENDOR", `vendor_rfc '${vendorRfc}' does not match any row in vendors.`, null, "vendor_rfc"));
    }
  }
  for (const row of tables.ledger) {
    const invoiceUuid = row.invoice_uuid;
    if (invoiceUuid !== null && !invoiceUuids.has(invoiceUuid)) {
      issues.push(warn("W_REF_INVOICE", `ledger.invoice_uuid '${invoiceUuid}' does not match any row in invoices.`, "ledger", "invoice_uuid"));
    }
  }
}

function dedupe(issues: EstateIssue[]): EstateIssue[] {
  const seen = new Set<string>();
  const out: EstateIssue[] = [];
  for (const issue of issues) {
    const key = `${issue.severity}|${issue.code}|${issue.message}|${issue.fileName}|${issue.table}|${issue.column}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(issue);
  }
  return out;
}

export function buildEstate(files: EstateFileEntry[]): { tables: EstateTables; issues: EstateIssue[] } {
  const { tables, issues } = foldContributions(files);
  checkFormats(tables, issues);
  checkEnums(tables, issues);
  checkInvoiceArithmetic(tables, issues);
  checkLedger(tables, issues);
  checkEmployeeIds(tables, issues);
  checkRequiredColumns(tables, issues);
  checkReferences(tables, issues);
  return { tables, issues: dedupe(issues) };
}
