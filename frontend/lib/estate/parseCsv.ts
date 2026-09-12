// CSV ingestion: detects which of the 8 estate tables a file belongs to, first by filename, then by
// header shape, coercing every row through coerceRow. A CSV whose table can't be determined is held
// as `pendingCsv` so the Data estate page can let the user assign it manually.

import Papa from "papaparse";
import { SOURCE_TABLES, type SourceTable } from "@/types/caseFile";
import type { EstateIssue, ParsedEstateFile } from "@/types/estate";
import { ESTATE_SCHEMA } from "@/lib/estate/schema";
import { coerceRow } from "@/lib/estate/coerce";

const TABLE_SUFFIX_RE = new RegExp(`(^|[_\\-. ])(${SOURCE_TABLES.join("|")})$`, "i");

function detectTableByFileName(fileName: string): SourceTable | null {
  const stem = fileName.replace(/\.[^.]+$/, "").toLowerCase();
  const match = stem.match(TABLE_SUFFIX_RE);
  if (!match) return null;
  const candidate = match[2].toLowerCase();
  return (SOURCE_TABLES as readonly string[]).includes(candidate) ? (candidate as SourceTable) : null;
}

function detectTableByHeader(header: string[]): SourceTable | null {
  const normalizedHeader = new Set(header.map((h) => h.trim().toLowerCase()));
  let best: { table: SourceTable; ratio: number } | null = null;
  let tie = false;

  for (const table of SOURCE_TABLES) {
    const spec = ESTATE_SCHEMA[table];
    const pkColumn = spec.find((c) => c.primaryKey)!.name.toLowerCase();
    if (!normalizedHeader.has(pkColumn)) continue;
    const matched = spec.filter((c) => normalizedHeader.has(c.name.toLowerCase())).length;
    const ratio = matched / spec.length;
    if (ratio < 0.6) continue;
    if (!best || ratio > best.ratio) {
      best = { table, ratio };
      tie = false;
    } else if (ratio === best.ratio && table !== best.table) {
      tie = true;
    }
  }

  return best && !tie ? best.table : null;
}

export function parseCsvFile(text: string, fileName: string): ParsedEstateFile {
  const cleaned = text.replace(/^﻿/, "");
  const parsed = Papa.parse<string[]>(cleaned, { skipEmptyLines: "greedy" });
  const rows = parsed.data;

  if (rows.length === 0) {
    return { detectedAs: "CSV (empty)", status: "failed", contributions: {}, pendingCsv: null, caseFileRaw: null, fileIssues: [] };
  }

  const header = rows[0];
  const dataRows = rows.slice(1);
  const fileIssues: EstateIssue[] = [];

  for (const row of dataRows) {
    if (row.length !== header.length) {
      fileIssues.push({
        severity: "warning",
        code: "W_CSV_ROW_LENGTH",
        message: `${fileName} has a row with ${row.length} column(s), expected ${header.length}.`,
        fileName,
        table: null,
        rowIndex: null,
        column: null,
      });
    }
  }

  const table = detectTableByFileName(fileName) ?? detectTableByHeader(header);
  if (!table) {
    return {
      detectedAs: "CSV → table not detected",
      status: "needs_table",
      contributions: {},
      pendingCsv: { header, rows: dataRows },
      caseFileRaw: null,
      fileIssues,
    };
  }

  const seenColumnIssues = new Set<string>();
  const rowsOut = dataRows.map((values, index) => {
    const record: Record<string, unknown> = {};
    header.forEach((col, i) => {
      record[col] = values[i];
    });
    const { row, issues } = coerceRow(table, record, { fileName, rowIndex: index }, seenColumnIssues);
    fileIssues.push(...issues);
    return row;
  });

  return {
    detectedAs: `CSV → ${table}`,
    status: "imported",
    contributions: { [table]: rowsOut },
    pendingCsv: null,
    caseFileRaw: null,
    fileIssues,
  };
}
