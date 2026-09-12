// Data estate types. Mirrors student-materials/forensic-auditor/estate_schema.sql: the 8 tables a
// case file's exhibits cite by `source_table`. Populated in the browser from SQLite, CSV, JSON or
// CFDI/estate XML uploads (see lib/estate/*), never persisted server-side.

import type { SourceTable } from "@/types/caseFile";

export type EstateColumnType = "TEXT" | "REAL" | "INTEGER";

export interface EstateColumnSpec {
  name: string;
  type: EstateColumnType;
  primaryKey: boolean;
}

export type EstateValue = string | number | null;
export type EstateRow = Record<string, EstateValue>;
export type EstateTables = Record<SourceTable, EstateRow[]>;

export type EstateFileFormat = "sqlite" | "csv" | "json" | "xml";
export type EstateFileStatus = "imported" | "needs_table" | "failed" | "case_file";

export interface EstateIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  fileName: string | null;
  table: SourceTable | null;
  rowIndex: number | null;
  column: string | null;
}

export interface EstateFileEntry {
  id: string;
  fileName: string;
  format: EstateFileFormat;
  sizeBytes: number;
  status: EstateFileStatus;
  detectedAs: string;
  contributions: Partial<Record<SourceTable, EstateRow[]>>;
  pendingCsv: { header: string[]; rows: string[][] } | null;
  caseFileRaw: unknown | null;
  fileIssues: EstateIssue[];
}

/** Shared shape every format parser (CSV/JSON/XML/SQLite) returns; ingest.ts adds id/fileName/format/sizeBytes. */
export type ParsedEstateFile = Pick<
  EstateFileEntry,
  "detectedAs" | "status" | "contributions" | "pendingCsv" | "caseFileRaw" | "fileIssues"
>;
