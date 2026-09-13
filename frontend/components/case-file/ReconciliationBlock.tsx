"use client";

// Task 9: the arithmetic showing the claimed amount equals the sum of cited exhibits within the
// judges' 2% tolerance, mirroring validate_format.py::validate_against_estate.

import React from "react";
import { CircleCheck, CircleHelp, CircleX } from "lucide-react";
import type { ReconciliationView } from "@/lib/caseFile/derive";
import { formatPesos } from "@/lib/utils";

interface ReconciliationBlockProps {
  reconciliation: ReconciliationView;
}

export const ReconciliationBlock: React.FC<ReconciliationBlockProps> = ({ reconciliation: rec }) => {
  const statusBar =
    rec.status === "reconciled" ? (
      <div className="flex items-center gap-2 bg-evidence-reconciled px-4 py-2 font-mono text-xs font-bold text-evidence-on">
        <CircleCheck className="h-3.5 w-3.5" aria-hidden="true" />
        RECONCILED (≤ 2% VARIANCE)
      </div>
    ) : rec.status === "not_reconciled" ? (
      <div className="flex items-center gap-2 bg-evidence-proven px-4 py-2 font-mono text-xs font-bold text-evidence-on">
        <CircleX className="h-3.5 w-3.5" aria-hidden="true" />
        NOT RECONCILED — VARIANCE EXCEEDS 2%
      </div>
    ) : (
      <div className="flex items-center gap-2 bg-paper-muted px-4 py-2 font-mono text-xs font-bold text-evidence-on">
        <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
        NOT VERIFIABLE — NO EXHIBIT AMOUNTS SUPPLIED
      </div>
    );

  const originNote =
    rec.origin === "estate"
      ? "Computed in the browser from the loaded data estate."
      : rec.origin === "derived"
      ? "Computed in the browser from exhibit amounts."
      : rec.origin === "backend"
      ? "Reported by the run."
      : null;

  return (
    <div className="case-avoid-break overflow-hidden rounded-sm border border-paper-ink">
      {statusBar}
      <dl>
        <div className="grid grid-cols-[1fr_auto] gap-4 border-b border-paper-border px-4 py-2">
          <dt>Claimed amount</dt>
          <dd className="text-right font-mono tabular-nums">{rec.claimed !== null ? formatPesos(rec.claimed) : "—"}</dd>
        </div>
        <div className="grid grid-cols-[1fr_auto] gap-4 border-b border-paper-border px-4 py-2">
          <dt>
            Sum of cited exhibits {rec.matchedTable ? <>— best-matching table <code className="font-mono">{rec.matchedTable}</code></> : null}
          </dt>
          <dd className="text-right font-mono tabular-nums">{rec.matchedSubtotal !== null ? formatPesos(rec.matchedSubtotal) : "—"}</dd>
        </div>
        <div className="grid grid-cols-[1fr_auto] gap-4 px-4 py-2">
          <dt>Variance (Δ)</dt>
          <dd className="text-right font-mono tabular-nums">
            {rec.delta !== null && rec.variancePct !== null ? `${formatPesos(rec.delta)} (${rec.variancePct.toFixed(2)}%)` : "—"}
          </dd>
        </div>
      </dl>
      {rec.perTable.length > 0 && (
        <div className="border-t border-paper-border px-4 py-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-paper-muted">Per-table subtotals</p>
          <table className="mt-1 w-full text-xs">
            <tbody>
              {rec.perTable.map((entry) => (
                <tr key={entry.table} className={entry.table === rec.matchedTable ? "font-semibold" : undefined}>
                  <td className="py-0.5 font-mono">{entry.table}</td>
                  <td className="py-0.5 text-right font-mono tabular-nums">{formatPesos(entry.subtotal)}</td>
                  <td className="py-0.5 pl-2 text-[11px] text-paper-muted">{entry.table === rec.matchedTable ? "matched" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="border-t border-paper-border px-4 py-2 text-[11px] text-paper-muted">
        Amounts reconcile per table: an invoice and the bank transfer that settled it are the same pesos seen twice, so subtotals are
        never added across tables.
        {originNote && <> {originNote}</>}
      </p>
    </div>
  );
};
