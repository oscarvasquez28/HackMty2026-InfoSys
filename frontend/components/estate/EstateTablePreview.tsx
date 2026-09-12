"use client";

// Paginated row viewer for one selected table, columns in schema order, with a text search and an
// "only rows with issues" toggle. Cells that triggered a validation issue are highlighted inline.

import React, { useMemo, useState } from "react";
import type { SourceTable } from "@/types/caseFile";
import { ESTATE_SCHEMA, PREVIEW_PAGE_SIZE } from "@/lib/estate/schema";
import type { EstateIssue, EstateRow, EstateTables } from "@/types/estate";

interface EstateTablePreviewProps {
  table: SourceTable;
  tables: EstateTables;
  issues: EstateIssue[];
}

export const EstateTablePreview: React.FC<EstateTablePreviewProps> = ({ table, tables, issues }) => {
  const [search, setSearch] = useState("");
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [page, setPage] = useState(0);

  const columns = ESTATE_SCHEMA[table];
  const pkColumn = columns.find((c) => c.primaryKey)?.name ?? columns[0].name;
  const tableIssues = useMemo(() => issues.filter((i) => i.table === table), [issues, table]);
  const rowHasIssue = useMemo(() => {
    // Row-level issues carry no rowIndex once folded (see validateEstate.ts), so "has an issue" is
    // approximated by matching the row's own values against issue messages that name this table.
    return (row: EstateRow) => tableIssues.some((i) => i.message.includes(String(row[pkColumn] ?? "")));
  }, [tableIssues, pkColumn]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tables[table].filter((row) => {
      if (onlyIssues && !rowHasIssue(row)) return false;
      if (q === "") return true;
      return Object.values(row).some((v) => v !== null && String(v).toLowerCase().includes(q));
    });
  }, [tables, table, search, onlyIssues, rowHasIssue]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PREVIEW_PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageRows = filtered.slice(currentPage * PREVIEW_PAGE_SIZE, (currentPage + 1) * PREVIEW_PAGE_SIZE);
  const start = filtered.length === 0 ? 0 : currentPage * PREVIEW_PAGE_SIZE + 1;
  const end = Math.min(filtered.length, (currentPage + 1) * PREVIEW_PAGE_SIZE);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Search in this table"
          className="min-h-9 min-w-48 rounded-md border border-surface-border bg-surface-deep px-2 text-sm text-foreground"
        />
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <input
            type="checkbox"
            checked={onlyIssues}
            onChange={(e) => {
              setOnlyIssues(e.target.checked);
              setPage(0);
            }}
          />
          Only rows with issues
        </label>
        <span className="text-xs text-muted">
          Rows {start}–{end} of {filtered.length}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button type="button" disabled={currentPage === 0} onClick={() => setPage((p) => p - 1)} className="app-button px-2 py-1 text-xs disabled:opacity-40">
            Previous
          </button>
          <button type="button" disabled={currentPage >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="app-button px-2 py-1 text-xs disabled:opacity-40">
            Next
          </button>
        </div>
      </div>

      <div className="mt-2 overflow-x-auto rounded-md border border-surface-border">
        <table className="w-full min-w-[640px] border-collapse text-xs">
          <thead>
            <tr className="border-b border-surface-border bg-surface-raised text-left uppercase tracking-wide text-muted">
              {columns.map((col) => (
                <th key={col.name} className="px-2 py-1.5 font-mono">
                  {col.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-2 py-3 text-center text-muted">
                  No rows to show.
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => (
                <tr key={`${row[pkColumn]}-${i}`} className="border-b border-surface-border/50">
                  {columns.map((col) => {
                    const value = row[col.name];
                    const cellIssue = tableIssues.find((issue) => issue.column === col.name && issue.message.includes(String(value ?? "")));
                    return (
                      <td
                        key={col.name}
                        title={cellIssue?.message}
                        className={`px-2 py-1.5 font-mono ${
                          cellIssue ? (cellIssue.severity === "error" ? "bg-status-danger/15" : "bg-status-warning/15") : ""
                        }`}
                      >
                        {value === null ? <span className="text-muted">—</span> : String(value)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
