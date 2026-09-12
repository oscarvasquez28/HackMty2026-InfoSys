// JSON ingestion covers three shapes: a case file submission (handed off to the case file viewer,
// not the estate), an object keyed by table name (`{ "vendors": [...], "invoices": [...] }`), or a
// bare array named after its table via the filename (e.g. vendors.json).

import { isRecord } from "@/types/investigation";
import { SOURCE_TABLES, type SourceTable } from "@/types/caseFile";
import type { EstateIssue, ParsedEstateFile } from "@/types/estate";
import { coerceRow } from "@/lib/estate/coerce";

const TABLE_SUFFIX_RE = new RegExp(`(^|[_\\-. ])(${SOURCE_TABLES.join("|")})$`, "i");

function detectTableByFileName(fileName: string): SourceTable | null {
  const stem = fileName.replace(/\.[^.]+$/, "").toLowerCase();
  const match = stem.match(TABLE_SUFFIX_RE);
  if (!match) return null;
  const candidate = match[2].toLowerCase();
  return (SOURCE_TABLES as readonly string[]).includes(candidate) ? (candidate as SourceTable) : null;
}

function isCaseFileShape(value: Record<string, unknown>): boolean {
  return "findings" in value || "leads_not_pursued" in value || "run_metadata" in value;
}

function ingestTableArray(table: SourceTable, rows: unknown[], fileName: string): { rows: ReturnType<typeof coerceRow>["row"][]; issues: EstateIssue[] } {
  const seenColumnIssues = new Set<string>();
  const issues: EstateIssue[] = [];
  const out = rows.map((entry, index) => {
    const record = isRecord(entry) ? entry : {};
    const { row, issues: rowIssues } = coerceRow(table, record, { fileName, rowIndex: index }, seenColumnIssues);
    issues.push(...rowIssues);
    return row;
  });
  return { rows: out, issues };
}

export function parseJsonFile(text: string, fileName: string): ParsedEstateFile {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (e) {
    return {
      detectedAs: "JSON (invalid)",
      status: "failed",
      contributions: {},
      pendingCsv: null,
      caseFileRaw: null,
      fileIssues: [
        { severity: "error", code: "E_JSON_PARSE", message: `${fileName} is not valid JSON: ${e instanceof Error ? e.message : String(e)}`, fileName, table: null, rowIndex: null, column: null },
      ],
    };
  }

  if (isRecord(parsed) && isCaseFileShape(parsed)) {
    return { detectedAs: "Case file JSON", status: "case_file", contributions: {}, pendingCsv: null, caseFileRaw: parsed, fileIssues: [] };
  }

  if (isRecord(parsed)) {
    const contributions: ParsedEstateFile["contributions"] = {};
    const fileIssues: EstateIssue[] = [];
    let matchedAny = false;

    for (const [key, value] of Object.entries(parsed)) {
      if ((SOURCE_TABLES as readonly string[]).includes(key) && Array.isArray(value)) {
        const table = key as SourceTable;
        const { rows, issues } = ingestTableArray(table, value, fileName);
        contributions[table] = rows;
        fileIssues.push(...issues);
        matchedAny = true;
      } else {
        fileIssues.push({
          severity: "warning",
          code: "W_UNKNOWN_KEY",
          message: `Top-level key '${key}' in ${fileName} does not match any estate table and was ignored.`,
          fileName,
          table: null,
          rowIndex: null,
          column: null,
        });
      }
    }

    if (matchedAny) {
      return {
        detectedAs: `Estate JSON (${Object.keys(contributions).length} tables)`,
        status: "imported",
        contributions,
        pendingCsv: null,
        caseFileRaw: null,
        fileIssues,
      };
    }
  }

  if (Array.isArray(parsed)) {
    const table = detectTableByFileName(fileName);
    if (table) {
      const { rows, issues } = ingestTableArray(table, parsed, fileName);
      return { detectedAs: `JSON array → ${table}`, status: "imported", contributions: { [table]: rows }, pendingCsv: null, caseFileRaw: null, fileIssues: issues };
    }
  }

  return {
    detectedAs: "JSON (unsupported shape)",
    status: "failed",
    contributions: {},
    pendingCsv: null,
    caseFileRaw: null,
    fileIssues: [
      {
        severity: "error",
        code: "E_UNSUPPORTED_JSON",
        message: `Unsupported JSON in ${fileName}: expected a case file, an object keyed by table name, or an array named after a table (e.g. vendors.json).`,
        fileName,
        table: null,
        rowIndex: null,
        column: null,
      },
    ],
  };
}
