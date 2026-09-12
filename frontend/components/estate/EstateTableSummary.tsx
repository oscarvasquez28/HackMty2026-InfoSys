"use client";

// Eight-card grid, one per estate table: row count, issue count, and (for amount-bearing tables)
// the sum of their reconciliation column. Clicking a card selects it in EstateTablePreview.

import React from "react";
import type { SourceTable } from "@/types/caseFile";
import { AMOUNT_COLUMN } from "@/lib/caseFile/constants";
import { ESTATE_TABLE_ORDER } from "@/lib/estate/schema";
import type { EstateIssue, EstateTables } from "@/types/estate";
import { formatPesos } from "@/lib/utils";

interface EstateTableSummaryProps {
  tables: EstateTables;
  issues: EstateIssue[];
  selected: SourceTable;
  onSelect: (table: SourceTable) => void;
}

export const EstateTableSummary: React.FC<EstateTableSummaryProps> = ({ tables, issues, selected, onSelect }) => {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {ESTATE_TABLE_ORDER.map((table) => {
        const rows = tables[table];
        const tableIssues = issues.filter((i) => i.table === table);
        const errorCount = tableIssues.filter((i) => i.severity === "error").length;
        const warningCount = tableIssues.filter((i) => i.severity === "warning").length;
        const amountCol = AMOUNT_COLUMN[table];
        const sum = amountCol ? rows.reduce((acc, row) => acc + (typeof row[amountCol] === "number" ? (row[amountCol] as number) : 0), 0) : null;
        const isSelected = table === selected;

        return (
          <button
            key={table}
            type="button"
            onClick={() => onSelect(table)}
            className={`rounded-md border p-3 text-left transition-colors ${
              isSelected ? "border-brand-500 bg-surface-blue" : "border-surface-border bg-surface-raised hover:border-brand-500/50"
            }`}
          >
            <p className="font-mono text-xs text-muted">{table}</p>
            <p className="mt-1 text-lg font-medium text-foreground">{rows.length.toLocaleString("en-US")}</p>
            <p className="text-xs text-muted">
              {errorCount > 0 && <span className="text-status-danger">{errorCount} error(s)</span>}
              {errorCount > 0 && warningCount > 0 && " · "}
              {warningCount > 0 && <span className="text-status-warning">{warningCount} warning(s)</span>}
              {errorCount === 0 && warningCount === 0 && "no issues"}
            </p>
            {sum !== null && <p className="mt-1 text-xs text-muted">Σ {amountCol}: {formatPesos(sum)}</p>}
          </button>
        );
      })}
    </div>
  );
};
