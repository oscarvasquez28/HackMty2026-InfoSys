// Dispatches one uploaded File to the right format parser by extension, and lets the Data estate
// page assign a table after the fact for a CSV whose table couldn't be auto-detected.

import type { SourceTable } from "@/types/caseFile";
import type { EstateFileEntry, EstateFileFormat } from "@/types/estate";
import { MAX_ESTATE_FILE_BYTES } from "@/lib/estate/schema";
import { parseCsvFile } from "@/lib/estate/parseCsv";
import { parseJsonFile } from "@/lib/estate/parseJson";
import { parseXmlFile } from "@/lib/estate/parseXml";
import { parseSqliteFile } from "@/lib/estate/sqlite";
import { coerceRow } from "@/lib/estate/coerce";

function detectFormat(fileName: string): EstateFileFormat | null {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".db") || lower.endsWith(".sqlite") || lower.endsWith(".sqlite3")) return "sqlite";
  if (lower.endsWith(".csv")) return "csv";
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".xml")) return "xml";
  return null;
}

function failedEntry(id: string, fileName: string, format: EstateFileFormat, sizeBytes: number, message: string): EstateFileEntry {
  return {
    id,
    fileName,
    format,
    sizeBytes,
    status: "failed",
    detectedAs: "Unsupported",
    contributions: {},
    pendingCsv: null,
    caseFileRaw: null,
    fileIssues: [{ severity: "error", code: "E_UNSUPPORTED_FORMAT", message, fileName, table: null, rowIndex: null, column: null }],
  };
}

export async function ingestFile(file: File, id: string): Promise<EstateFileEntry> {
  const format = detectFormat(file.name);
  if (!format) {
    return failedEntry(id, file.name, "json", file.size, "Unsupported file type. Use .db, .sqlite, .csv, .json or .xml.");
  }
  if (file.size > MAX_ESTATE_FILE_BYTES) {
    return failedEntry(id, file.name, format, file.size, "File exceeds 50 MB.");
  }

  try {
    if (format === "sqlite") {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const parsed = await parseSqliteFile(bytes, file.name);
      return { id, fileName: file.name, format, sizeBytes: file.size, ...parsed };
    }
    const text = await file.text();
    const parsed = format === "csv" ? parseCsvFile(text, file.name) : format === "json" ? parseJsonFile(text, file.name) : parseXmlFile(text, file.name);
    return { id, fileName: file.name, format, sizeBytes: file.size, ...parsed };
  } catch (e) {
    return failedEntry(id, file.name, format, file.size, `Failed to read ${file.name}: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/** Converts a `needs_table` CSV entry into an imported one now that the user has picked a table. */
export function assignCsvTable(entry: EstateFileEntry, table: SourceTable): EstateFileEntry {
  if (!entry.pendingCsv) return entry;
  const { header, rows } = entry.pendingCsv;
  const seenColumnIssues = new Set<string>();
  const fileIssues: EstateFileEntry["fileIssues"] = [];
  const contributionRows = rows.map((values, index) => {
    const record: Record<string, unknown> = {};
    header.forEach((col, i) => {
      record[col] = values[i];
    });
    const { row, issues } = coerceRow(table, record, { fileName: entry.fileName, rowIndex: index }, seenColumnIssues);
    fileIssues.push(...issues);
    return row;
  });

  return {
    ...entry,
    status: "imported",
    detectedAs: `CSV → ${table} (assigned)`,
    contributions: { [table]: contributionRows },
    pendingCsv: null,
    fileIssues,
  };
}
