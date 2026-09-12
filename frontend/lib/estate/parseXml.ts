// XML ingestion covers two shapes: a CFDI 4.0 Comprobante (one invoice row, namespace-agnostic
// element lookup since SAT namespaces vary by PAC) and an <estate> document with <table><row>
// children per table. CFDI XML never carries SAT cancellation status, so invoices.status is always
// null with a warning -- the run's own data must supply it if known.

import type { SourceTable } from "@/types/caseFile";
import { SOURCE_TABLES } from "@/types/caseFile";
import type { EstateIssue, ParsedEstateFile } from "@/types/estate";
import { coerceRow } from "@/lib/estate/coerce";

function findAllByLocalName(root: Element, name: string): Element[] {
  return Array.from(root.getElementsByTagName("*")).filter((el) => el.localName === name);
}

function findFirstByLocalName(root: Element, name: string): Element | null {
  return findAllByLocalName(root, name)[0] ?? null;
}

function attr(el: Element | null, name: string): string | null {
  if (!el) return null;
  const value = el.getAttribute(name);
  return value === null || value === "" ? null : value;
}

function parseCfdiInvoice(root: Element, fileName: string): ParsedEstateFile {
  const issues: EstateIssue[] = [];

  const version = attr(root, "Version");
  if (version !== "4.0") {
    issues.push({ severity: "warning", code: "W_CFDI_VERSION", message: `${fileName}: CFDI Version is '${version ?? "unknown"}', expected '4.0'.`, fileName, table: "invoices", rowIndex: null, column: "uuid" });
  }

  const emisor = findFirstByLocalName(root, "Emisor");
  const receptor = findFirstByLocalName(root, "Receptor");
  const complemento = findFirstByLocalName(root, "Complemento");
  const timbre = complemento ? findFirstByLocalName(complemento, "TimbreFiscalDigital") : null;
  const conceptos = findAllByLocalName(root, "Concepto");

  // The Impuestos node cited for reconciliation is the one on Comprobante itself, never the one
  // nested inside a Concepto -- those cover only that line item.
  const impuestosDirect = Array.from(root.children).find((el) => el.localName === "Impuestos") ?? null;

  let uuid = attr(timbre, "UUID");
  if (!uuid) {
    const folio = attr(root, "Folio");
    if (!folio) {
      return {
        detectedAs: "CFDI 4.0 invoice (unusable)",
        status: "failed",
        contributions: {},
        pendingCsv: null,
        caseFileRaw: null,
        fileIssues: [{ severity: "error", code: "E_CFDI_NO_ID", message: `${fileName}: no TimbreFiscalDigital UUID and no Folio to fall back on.`, fileName, table: "invoices", rowIndex: null, column: "uuid" }],
      };
    }
    uuid = `${attr(root, "Serie") ?? ""}${folio}`;
    issues.push({ severity: "warning", code: "W_CFDI_NO_UUID", message: `${fileName}: no TimbreFiscalDigital UUID; using Serie+Folio ('${uuid}') as the invoice id instead.`, fileName, table: "invoices", rowIndex: null, column: "uuid" });
  }

  let iva: number | null = null;
  const ivaAttr = attr(impuestosDirect, "TotalImpuestosTrasladados");
  if (ivaAttr !== null) {
    iva = Number(ivaAttr);
  } else if (impuestosDirect) {
    const traslados = findAllByLocalName(impuestosDirect, "Traslado").filter((t) => attr(t, "Impuesto") === "002");
    if (traslados.length > 0) {
      iva = traslados.reduce((sum, t) => sum + (Number(attr(t, "Importe")) || 0), 0);
    }
  }
  if (iva === null) {
    issues.push({ severity: "warning", code: "W_CFDI_NO_IVA", message: `${fileName}: could not determine IVA from the Comprobante-level Impuestos node or its Traslado entries.`, fileName, table: "invoices", rowIndex: null, column: "iva" });
  }

  issues.push({ severity: "warning", code: "W_CFDI_STATUS_UNKNOWN", message: "CFDI XML does not carry SAT cancellation status; provide status in invoices data if known.", fileName, table: "invoices", rowIndex: null, column: "status" });

  const record: Record<string, unknown> = {
    uuid,
    issuer_rfc: attr(emisor, "Rfc"),
    receiver_rfc: attr(receptor, "Rfc"),
    issue_date: attr(root, "Fecha"),
    subtotal: attr(root, "SubTotal"),
    iva,
    total: attr(root, "Total"),
    concepto_text: conceptos.map((c) => attr(c, "Descripcion")).filter(Boolean).join(" | "),
    uso_cfdi: attr(receptor, "UsoCFDI"),
    forma_pago: attr(root, "FormaPago"),
    metodo_pago: attr(root, "MetodoPago"),
    status: null,
  };

  const { row, issues: coerceIssues } = coerceRow("invoices", record, { fileName, rowIndex: 0 });
  issues.push(...coerceIssues);

  return { detectedAs: "CFDI 4.0 invoice", status: "imported", contributions: { invoices: [row] }, pendingCsv: null, caseFileRaw: null, fileIssues: issues };
}

function parseTableElement(tableEl: Element, table: SourceTable, fileName: string, fileIssues: EstateIssue[]) {
  const seenColumnIssues = new Set<string>();
  return Array.from(tableEl.children)
    .filter((rowEl) => rowEl.localName === "row")
    .map((rowEl, index) => {
      const record: Record<string, unknown> = {};
      for (const colEl of Array.from(rowEl.children)) {
        const text = colEl.textContent?.trim() ?? "";
        record[colEl.localName || colEl.tagName] = text === "" ? null : text;
      }
      const { row, issues } = coerceRow(table, record, { fileName, rowIndex: index }, seenColumnIssues);
      fileIssues.push(...issues);
      return row;
    });
}

/** <estate><vendors><row>...</row></vendors>...</estate> -- root wraps one element per table. */
function parseEstateXml(root: Element, fileName: string): ParsedEstateFile {
  const contributions: ParsedEstateFile["contributions"] = {};
  const fileIssues: EstateIssue[] = [];

  for (const tableEl of Array.from(root.children)) {
    const tableName = tableEl.localName || tableEl.tagName;
    if (!(SOURCE_TABLES as readonly string[]).includes(tableName)) {
      fileIssues.push({ severity: "warning", code: "W_UNKNOWN_KEY", message: `${fileName}: element <${tableName}> does not match any estate table and was ignored.`, fileName, table: null, rowIndex: null, column: null });
      continue;
    }
    const table = tableName as SourceTable;
    contributions[table] = parseTableElement(tableEl, table, fileName, fileIssues);
  }

  return { detectedAs: `Estate XML (${Object.keys(contributions).length} tables)`, status: "imported", contributions, pendingCsv: null, caseFileRaw: null, fileIssues };
}

/** <vendors><row>...</row>...</vendors> -- root IS the single table, e.g. one file per table. */
function parseSingleTableXml(root: Element, table: SourceTable, fileName: string): ParsedEstateFile {
  const fileIssues: EstateIssue[] = [];
  const rows = parseTableElement(root, table, fileName, fileIssues);
  return { detectedAs: `Estate XML → ${table}`, status: "imported", contributions: { [table]: rows }, pendingCsv: null, caseFileRaw: null, fileIssues };
}

export function parseXmlFile(text: string, fileName: string): ParsedEstateFile {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  const parserError = doc.getElementsByTagName("parsererror")[0];
  if (parserError) {
    return {
      detectedAs: "XML (invalid)",
      status: "failed",
      contributions: {},
      pendingCsv: null,
      caseFileRaw: null,
      fileIssues: [{ severity: "error", code: "E_XML_PARSE", message: `${fileName}: invalid XML.`, fileName, table: null, rowIndex: null, column: null }],
    };
  }

  const root = doc.documentElement;
  if (root.localName === "Comprobante") {
    return parseCfdiInvoice(root, fileName);
  }
  if (root.localName === "estate") {
    return parseEstateXml(root, fileName);
  }
  if ((SOURCE_TABLES as readonly string[]).includes(root.localName)) {
    return parseSingleTableXml(root, root.localName as SourceTable, fileName);
  }

  return {
    detectedAs: "XML (unsupported shape)",
    status: "failed",
    contributions: {},
    pendingCsv: null,
    caseFileRaw: null,
    fileIssues: [
      {
        severity: "error",
        code: "E_UNSUPPORTED_XML",
        message: `Unsupported XML in ${fileName}: expected a CFDI 4.0 Comprobante or an <estate> document.`,
        fileName,
        table: null,
        rowIndex: null,
        column: null,
      },
    ],
  };
}
