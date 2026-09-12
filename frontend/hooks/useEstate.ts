"use client";

// Owns the in-browser data estate: every uploaded file's parse result, the folded/validated tables
// derived from them, and export helpers (estate.db / estate.json). Nothing here persists across a
// reload -- see components/estate/DataEstateWorkspace.tsx for the explicit "cleared on reload" notice.

import { useCallback, useMemo, useRef, useState } from "react";
import type { SourceTable } from "@/types/caseFile";
import type { EstateFileEntry } from "@/types/estate";
import { MAX_FILES_PER_BATCH, ESTATE_TABLE_ORDER } from "@/lib/estate/schema";
import { ingestFile, assignCsvTable } from "@/lib/estate/ingest";
import { buildEstate } from "@/lib/estate/validateEstate";
import { exportEstateSqlite } from "@/lib/estate/sqlite";

export interface UseEstateReturn {
  status: "idle" | "processing" | "ready";
  files: EstateFileEntry[];
  tables: ReturnType<typeof buildEstate>["tables"];
  issues: ReturnType<typeof buildEstate>["issues"];
  totalRows: number;
  hasEstate: boolean;
  addFiles: (files: File[]) => Promise<{ caseFiles: { fileName: string; raw: unknown }[] }>;
  assignTable: (fileId: string, table: SourceTable) => void;
  removeFile: (fileId: string) => void;
  clear: () => void;
  exportSqlite: () => Promise<Uint8Array>;
  exportJson: () => string;
}

export function useEstate(): UseEstateReturn {
  const [files, setFiles] = useState<EstateFileEntry[]>([]);
  const [status, setStatus] = useState<UseEstateReturn["status"]>("idle");
  const counterRef = useRef(0);

  const { tables, issues: foldIssues } = useMemo(() => buildEstate(files), [files]);
  const issues = useMemo(() => [...files.flatMap((f) => f.fileIssues), ...foldIssues], [files, foldIssues]);
  const totalRows = useMemo(() => ESTATE_TABLE_ORDER.reduce((sum, t) => sum + tables[t].length, 0), [tables]);
  const hasEstate = files.some((f) => f.status === "imported");

  const addFiles = useCallback(async (incoming: File[]) => {
    setStatus("processing");
    const batch = incoming.slice(0, MAX_FILES_PER_BATCH);
    const overflow = incoming.slice(MAX_FILES_PER_BATCH);

    const entries = await Promise.all(
      batch.map((file) => {
        counterRef.current += 1;
        return ingestFile(file, `file-${counterRef.current}`);
      })
    );

    const overflowEntries: EstateFileEntry[] = overflow.map((file) => {
      counterRef.current += 1;
      return {
        id: `file-${counterRef.current}`,
        fileName: file.name,
        format: "json",
        sizeBytes: file.size,
        status: "failed",
        detectedAs: "Skipped",
        contributions: {},
        pendingCsv: null,
        caseFileRaw: null,
        fileIssues: [
          { severity: "error", code: "E_BATCH_LIMIT", message: `Skipped: batch limit is ${MAX_FILES_PER_BATCH} files per upload.`, fileName: file.name, table: null, rowIndex: null, column: null },
        ],
      };
    });

    const allEntries = [...entries, ...overflowEntries];
    setFiles((prev) => [...prev, ...allEntries]);
    setStatus("ready");

    const caseFiles = allEntries.filter((e) => e.status === "case_file").map((e) => ({ fileName: e.fileName, raw: e.caseFileRaw }));
    return { caseFiles };
  }, []);

  const assignTable = useCallback((fileId: string, table: SourceTable) => {
    setFiles((prev) => prev.map((entry) => (entry.id === fileId ? assignCsvTable(entry, table) : entry)));
  }, []);

  const removeFile = useCallback((fileId: string) => {
    setFiles((prev) => prev.filter((entry) => entry.id !== fileId));
  }, []);

  const clear = useCallback(() => {
    setFiles([]);
    setStatus("idle");
  }, []);

  const exportSqlite = useCallback(() => exportEstateSqlite(tables), [tables]);

  const exportJson = useCallback(() => {
    const obj: Record<string, unknown> = {};
    for (const table of ESTATE_TABLE_ORDER) obj[table] = tables[table];
    return `${JSON.stringify(obj, null, 2)}\n`;
  }, [tables]);

  return { status, files, tables, issues, totalRows, hasEstate, addFiles, assignTable, removeFile, clear, exportSqlite, exportJson };
}
