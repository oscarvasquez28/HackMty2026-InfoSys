"use client";

// Task 8: the exhibit schedule -- one row per record cited as proof, styled as an audit workpaper.
// Each row is a target anchor so money-trail exhibit chips can jump straight to it.

import React from "react";
import { CircleCheck, CircleX } from "lucide-react";
import type { FindingView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { AMOUNT_COLUMN, MIN_EXHIBITS, isSourceTable } from "@/lib/caseFile/constants";
import { ESTATE_SCHEMA } from "@/lib/estate/schema";
import { formatPesos } from "@/lib/utils";
import { IssueNotice } from "@/components/case-file/IssueNotice";

interface ExhibitsTableProps {
  finding: FindingView;
  issues: ValidationIssue[];
}

export const ExhibitsTable: React.FC<ExhibitsTableProps> = ({ finding, issues }) => {
  const exhibits = finding.finding.exhibits;
  const belowMinimum = exhibits.length < MIN_EXHIBITS;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border border-b-0 border-paper-ink bg-paper-raised px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em]">
        <span>
          Workpaper {finding.workpaperId} · Exhibit schedule
        </span>
        <span className={belowMinimum ? "text-evidence-proven" : undefined}>
          {exhibits.length} exhibits · minimum {MIN_EXHIBITS}
        </span>
      </div>
      <div className="case-scroll overflow-x-auto">
        <table className="w-full min-w-[640px] table-fixed border-collapse border border-paper-ink text-sm">
          <colgroup>
            <col style={{ width: "14%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "22%" }} />
            <col style={{ width: "46%" }} />
          </colgroup>
          <thead className="bg-paper-ink font-mono text-[11px] uppercase tracking-[0.12em] text-paper">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Exhibit ID</th>
              <th className="px-3 py-2 text-left font-semibold">Source table</th>
              <th className="px-3 py-2 text-left font-semibold">Record ID</th>
              <th className="px-3 py-2 text-left font-semibold">What it proves</th>
            </tr>
          </thead>
          <tbody>
            {exhibits.map((exhibit, index) => {
              const anchor = finding.exhibitAnchors[exhibit.exhibit_id] ?? `${finding.anchorId}-exhibit-${index}`;
              const isDuplicate = finding.duplicateExhibitIds.includes(exhibit.exhibit_id);
              const sourceTable = exhibit.source_table;
              const validTable = isSourceTable(sourceTable);
              const amountCol = isSourceTable(sourceTable) ? AMOUNT_COLUMN[sourceTable] : undefined;
              return (
                <tr key={`${exhibit.exhibit_id}-${index}`} id={anchor} className="scroll-mt-24 border-t border-paper-border align-top odd:bg-paper-sheet even:bg-paper-raised target:bg-evidence-held-soft">
                  <td className="px-3 py-2 font-mono font-bold">
                    {exhibit.exhibit_id}
                    {isDuplicate && <span className="ml-1 text-evidence-proven">duplicate</span>}
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono">{exhibit.source_table}</span>
                    {!validTable && <span className="ml-1 text-evidence-proven">invalid table</span>}
                    {validTable && amountCol && (
                      <p className="mt-0.5 text-[11px] text-paper-muted">
                        {exhibit.amount !== null ? `${amountCol}: ${formatPesos(exhibit.amount)}` : `${amountCol}: amount not supplied`}
                      </p>
                    )}
                  </td>
                  <td className="break-all px-3 py-2 font-mono">
                    {exhibit.record_id}
                    <EstateBadge estate={finding.exhibitEstate[exhibit.exhibit_id]} table={isSourceTable(sourceTable) ? sourceTable : null} />
                  </td>
                  <td className="px-3 py-2 font-serif">{exhibit.note}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4} className="px-3 py-2 text-[11px] text-paper-muted">
                Amount-bearing columns used for reconciliation: invoices.total, bank_txns.amount, purchase_orders.amount, contracts.value.
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <IssueNotice issues={issues} />
    </div>
  );
};

const EstateBadge: React.FC<{ estate: FindingView["exhibitEstate"][string] | undefined; table: import("@/types/caseFile").SourceTable | null }> = ({
  estate,
  table,
}) => {
  if (!estate || estate.status === "not_checked") return null;
  if (estate.status === "missing") {
    return (
      <span className="ml-1 inline-flex items-center gap-1 rounded-sm bg-evidence-proven-soft px-1 text-[10px] font-semibold text-evidence-proven">
        <CircleX className="h-3 w-3" aria-hidden="true" />
        not in estate
      </span>
    );
  }
  const columns = table ? ESTATE_SCHEMA[table] : [];
  return (
    <div className="mt-0.5">
      <span className="inline-flex items-center gap-1 rounded-sm bg-evidence-reconciled-soft px-1 text-[10px] font-semibold text-evidence-reconciled">
        <CircleCheck className="h-3 w-3" aria-hidden="true" />
        in estate
      </span>
      {estate.record && (
        <details data-print="hide" data-export="exclude" className="mt-0.5 text-[11px] text-paper-muted">
          <summary className="cursor-pointer">View record</summary>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
            {columns.map((col) => (
              <React.Fragment key={col.name}>
                <dt className="font-mono">{col.name}</dt>
                <dd className="break-all">{estate.record![col.name] === null ? "—" : String(estate.record![col.name])}</dd>
              </React.Fragment>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
};
