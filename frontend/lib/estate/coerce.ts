// Coerces one loosely-typed record (from CSV, JSON, or SQLite) into an EstateRow matching
// ESTATE_SCHEMA's column types. Column matching is case-insensitive so "RFC", "rfc", " Rfc " all
// resolve to the same schema column; unmatched columns are dropped with a warning, not silently kept.

import type { SourceTable } from "@/types/caseFile";
import type { EstateIssue, EstateRow, EstateValue } from "@/types/estate";
import { ESTATE_SCHEMA } from "@/lib/estate/schema";

interface CoerceContext {
  fileName: string;
  rowIndex: number;
}

const NUMERIC_WITH_COMMAS_RE = /^-?\d{1,3}(,\d{3})+(\.\d+)?$/;

function issue(
  severity: EstateIssue["severity"],
  code: string,
  message: string,
  ctx: { fileName: string | null; table: SourceTable | null; rowIndex: number | null; column: string | null }
): EstateIssue {
  return { severity, code, message, ...ctx };
}

/** Coerces one record into an EstateRow for `table`. `seenColumnIssues` is a Set shared across every
 * row of the same file, so unknown/missing-column warnings are reported once per file, not once per row. */
export function coerceRow(
  table: SourceTable,
  record: Record<string, unknown>,
  ctx: CoerceContext,
  seenColumnIssues: Set<string> = new Set()
): { row: EstateRow; issues: EstateIssue[] } {
  const spec = ESTATE_SCHEMA[table];
  const issues: EstateIssue[] = [];
  const row: EstateRow = {};

  const recordKeys = new Map<string, string>();
  for (const key of Object.keys(record)) {
    recordKeys.set(key.trim().toLowerCase(), key);
  }

  for (const col of spec) {
    const matchedKey = recordKeys.get(col.name.toLowerCase());
    recordKeys.delete(col.name.toLowerCase());
    if (matchedKey === undefined) {
      const dedupeKey = `missing:${ctx.fileName}:${table}:${col.name}`;
      if (!seenColumnIssues.has(dedupeKey)) {
        seenColumnIssues.add(dedupeKey);
        issues.push(
          issue(
            "warning",
            "W_MISSING_COLUMN",
            `Column '${col.name}' is missing from ${ctx.fileName}; every ${table} row will have it set to null.`,
            { fileName: ctx.fileName, table, rowIndex: null, column: col.name }
          )
        );
      }
      row[col.name] = null;
      continue;
    }

    const raw = record[matchedKey];
    row[col.name] = coerceValue(raw, col.type, col.name, table, ctx, issues);
  }

  for (const [, originalKey] of Array.from(recordKeys)) {
    const dedupeKey = `unknown:${ctx.fileName}:${table}:${originalKey}`;
    if (!seenColumnIssues.has(dedupeKey)) {
      seenColumnIssues.add(dedupeKey);
      issues.push(
        issue("warning", "W_UNKNOWN_COLUMN", `Column '${originalKey}' in ${ctx.fileName} does not match any ${table} column and was ignored.`, {
          fileName: ctx.fileName,
          table,
          rowIndex: null,
          column: originalKey,
        })
      );
    }
  }

  return { row, issues };
}

function coerceValue(
  raw: unknown,
  type: "TEXT" | "REAL" | "INTEGER",
  column: string,
  table: SourceTable,
  ctx: CoerceContext,
  issues: EstateIssue[]
): EstateValue {
  if (raw === null || raw === undefined) return null;

  if (type === "TEXT") {
    if (typeof raw === "string") {
      const trimmed = raw.trim();
      return trimmed === "" ? null : trimmed;
    }
    if (typeof raw === "number" && Number.isFinite(raw)) {
      if (column.toLowerCase().endsWith("clabe")) {
        issues.push(
          issue("warning", "W_CLABE_NUMERIC", `${table}.${column} in row ${ctx.rowIndex} arrived as a number; leading zeros may have been lost.`, {
            fileName: ctx.fileName,
            table,
            rowIndex: ctx.rowIndex,
            column,
          })
        );
      }
      return String(raw);
    }
    issues.push(
      issue("error", "E_TYPE", `${table}.${column} in row ${ctx.rowIndex} is not text-compatible: ${typeof raw}.`, {
        fileName: ctx.fileName,
        table,
        rowIndex: ctx.rowIndex,
        column,
      })
    );
    return null;
  }

  // REAL / INTEGER
  let numeric: number | null = null;
  if (typeof raw === "number") {
    numeric = raw;
  } else if (typeof raw === "string") {
    const trimmed = raw.trim();
    const cleaned = NUMERIC_WITH_COMMAS_RE.test(trimmed) ? trimmed.replace(/,/g, "") : trimmed;
    const parsed = Number(cleaned);
    numeric = cleaned === "" ? null : parsed;
  }

  if (numeric === null || !Number.isFinite(numeric)) {
    issues.push(
      issue("error", "E_TYPE", `${table}.${column} in row ${ctx.rowIndex} is not a valid ${type.toLowerCase()}: ${JSON.stringify(raw)}.`, {
        fileName: ctx.fileName,
        table,
        rowIndex: ctx.rowIndex,
        column,
      })
    );
    return null;
  }

  if (type === "INTEGER" && !Number.isInteger(numeric)) {
    issues.push(
      issue("error", "E_TYPE", `${table}.${column} in row ${ctx.rowIndex} must be an integer, got ${numeric}.`, {
        fileName: ctx.fileName,
        table,
        rowIndex: ctx.rowIndex,
        column,
      })
    );
    return null;
  }

  return numeric;
}
