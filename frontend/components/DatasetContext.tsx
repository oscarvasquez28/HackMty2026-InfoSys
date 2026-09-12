"use client";

import React from "react";
import { FileSpreadsheet, ArrowUpRight, Database, Info } from "lucide-react";
import { UploadResponse } from "@/types/investigation";
import { formatCurrencyMXN } from "@/lib/utils";

interface DatasetContextProps {
  currentCase: UploadResponse | null;
  onOpenDataset: () => void;
}

export const DatasetContext: React.FC<DatasetContextProps> = ({ currentCase, onOpenDataset }) => (
  <aside className="min-w-0 space-y-7" aria-label="Dataset context">
    <div>
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground"><Database className="h-4 w-4 text-muted" aria-hidden="true" /> Your source</div>
      <div className="rounded-lg border border-surface-border bg-surface p-4">
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-md border border-surface-border bg-surface-raised text-brand-300"><FileSpreadsheet className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" /></div>
        <p className="break-all text-sm font-medium text-foreground">{currentCase?.filename || (currentCase ? "Transaction dataset" : "No dataset attached")}</p>
        <p className="mt-2 text-xs leading-5 text-muted">{currentCase?.simulation ? `${currentCase.source_files?.length || 1} local CSV file${currentCase.source_files?.length === 1 ? "" : "s"} used for this visual demo` : currentCase ? "Transaction dataset and returned evidence" : "Add a CSV to give the review team a source to investigate."}</p>
        {!!currentCase?.source_files?.length && currentCase.source_files.length > 1 && <ul className="mt-3 space-y-1 border-t border-surface-border pt-3">{currentCase.source_files.map(file => <li key={file} className="truncate text-xs text-muted" title={file}>{file}</li>)}</ul>}
        {currentCase && <button type="button" onClick={onOpenDataset} className="mt-4 flex min-h-11 w-full items-center justify-between border-t border-surface-border pt-3 text-xs text-brand-300 hover:text-brand-50">Inspect dataset <ArrowUpRight className="h-4 w-4" aria-hidden="true" /></button>}
      </div>
    </div>
    {currentCase && <div>
      <h2 className="mb-4 text-sm font-medium text-foreground">Case overview</h2>
      <dl className="space-y-4 text-xs">
        <div className="flex items-center justify-between gap-3"><dt className="text-muted">Accepted transactions</dt><dd className="font-mono text-foreground">{currentCase.ingestion?.total_records.toLocaleString("en-US") ?? "Not provided"}</dd></div>
        <div className="flex items-center justify-between gap-3"><dt className="text-muted">Accounts analyzed</dt><dd className="font-mono text-foreground">{currentCase.metrics.total_nodes_analyzed.toLocaleString("en-US")}</dd></div>
        <div className="flex items-center justify-between gap-3"><dt className="text-muted">Account-to-account links</dt><dd className="font-mono text-foreground">{currentCase.metrics.total_edges_analyzed.toLocaleString("en-US")}</dd></div>
        <div className="border-t border-surface-border pt-4"><dt className="text-muted">Flagged transfer volume</dt><dd className="mt-2 break-words text-lg font-medium tracking-tight text-foreground">{formatCurrencyMXN(currentCase.metrics.suspicious_volume_mxn)}</dd><p className="mt-1 text-xs leading-5 text-muted">Aggregated MXN volume, not proven loss.</p></div>
      </dl>
    </div>}
    <div className="border-t border-surface-border pt-5">
      <div className="flex items-center gap-2 text-xs font-medium text-muted"><Info className="h-3.5 w-3.5" aria-hidden="true" /> Review scope</div>
      <p className="mt-3 text-xs leading-6 text-muted">{currentCase?.simulation ? "Visual simulation only. Agent updates, patterns, and risk labels are illustrative." : "Circular flows and rapid pass-through patterns. Findings support human review; they do not establish fraud."}</p>
      {currentCase?.ingestion?.timestamps_synthetic && <p className="mt-3 text-xs leading-5 text-status-warning">Timestamps were synthesized. Verify the original timing before relying on time-window findings.</p>}
      <p className="mt-3 text-xs leading-5 text-muted">Cases last for this session only.</p>
    </div>
  </aside>
);
