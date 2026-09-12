"use client";

// Per-file status table: what format was detected, how many rows landed, how many issues, and --
// for a CSV whose table couldn't be auto-detected -- a manual table picker.

import React from "react";
import { SOURCE_TABLES, type SourceTable } from "@/types/caseFile";
import type { EstateFileEntry } from "@/types/estate";

interface EstateFileListProps {
  files: EstateFileEntry[];
  onAssignTable: (fileId: string, table: SourceTable) => void;
  onRemove: (fileId: string) => void;
}

function rowCount(entry: EstateFileEntry): number {
  return Object.values(entry.contributions).reduce((sum, rows) => sum + (rows?.length ?? 0), 0);
}

function statusBadge(entry: EstateFileEntry): { label: string; className: string } {
  switch (entry.status) {
    case "imported":
      return { label: "Imported", className: "bg-status-success/15 text-status-success" };
    case "needs_table":
      return { label: "Needs table", className: "bg-status-warning/15 text-status-warning" };
    case "case_file":
      return { label: "Case file", className: "bg-brand-500/15 text-brand-300" };
    default:
      return { label: "Failed", className: "bg-status-danger/15 text-status-danger" };
  }
}

export const EstateFileList: React.FC<EstateFileListProps> = ({ files, onAssignTable, onRemove }) => {
  if (files.length === 0) {
    return <p className="text-sm text-muted">No files loaded yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs uppercase tracking-wide text-muted">
            <th className="py-2 pr-3">File</th>
            <th className="py-2 pr-3">Format</th>
            <th className="py-2 pr-3">Detected as</th>
            <th className="py-2 pr-3">Rows</th>
            <th className="py-2 pr-3">Issues</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {files.map((entry) => {
            const badge = statusBadge(entry);
            const errorCount = entry.fileIssues.filter((i) => i.severity === "error").length;
            const warningCount = entry.fileIssues.filter((i) => i.severity === "warning").length;
            return (
              <tr key={entry.id} className="border-b border-surface-border/60 align-top">
                <td className="py-2 pr-3 text-foreground">{entry.fileName}</td>
                <td className="py-2 pr-3 font-mono text-xs uppercase text-muted">{entry.format}</td>
                <td className="py-2 pr-3 text-muted">{entry.detectedAs}</td>
                <td className="py-2 pr-3 tabular-nums">{rowCount(entry)}</td>
                <td className="py-2 pr-3 tabular-nums text-muted">
                  {errorCount > 0 && <span className="text-status-danger">{errorCount}e</span>}
                  {errorCount > 0 && warningCount > 0 && " / "}
                  {warningCount > 0 && <span className="text-status-warning">{warningCount}w</span>}
                  {errorCount === 0 && warningCount === 0 && "—"}
                </td>
                <td className="py-2 pr-3">
                  <span className={`rounded-sm px-1.5 py-0.5 text-xs ${badge.className}`}>{badge.label}</span>
                  {entry.status === "failed" && entry.fileIssues[0] && (
                    <p className="mt-1 max-w-xs text-xs text-status-danger">{entry.fileIssues[0].message}</p>
                  )}
                </td>
                <td className="py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {entry.status === "needs_table" && (
                      <AssignTableControl fileId={entry.id} onAssign={onAssignTable} />
                    )}
                    <button type="button" onClick={() => onRemove(entry.id)} className="text-xs text-muted hover:text-status-danger">
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const AssignTableControl: React.FC<{ fileId: string; onAssign: (fileId: string, table: SourceTable) => void }> = ({ fileId, onAssign }) => {
  const [value, setValue] = React.useState<SourceTable | "">("");
  return (
    <>
      <select
        value={value}
        onChange={(e) => setValue(e.target.value as SourceTable | "")}
        className="rounded-md border border-surface-border bg-surface-deep px-1.5 py-1 text-xs text-foreground"
      >
        <option value="">Choose table…</option>
        {SOURCE_TABLES.map((table) => (
          <option key={table} value={table}>
            {table}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={!value}
        onClick={() => value && onAssign(fileId, value)}
        className="app-button px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
      >
        Import as table
      </button>
    </>
  );
};
