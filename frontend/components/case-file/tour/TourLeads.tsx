"use client";

// Leads chapter: how the closed leads break down by closure type, then the filterable table.

import React from "react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { CLOSURE_LABELS, UNCLASSIFIED_CLOSURE_LABEL } from "@/lib/caseFile/constants";
import { LeadsTable } from "@/components/case-file/LeadsTable";
import { IssueNotice, issuesForPath } from "@/components/case-file/IssueNotice";
import { TourChapterFrame, riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourLeadsProps {
  view: CaseFileView;
  issues: ValidationIssue[];
  number: number;
  total: number;
  purpose: string;
}

const CATEGORY_BAR: Record<string, string> = {
  materiality_verified: "bg-evidence-reconciled",
  administrative_error: "bg-evidence-probable",
  no_bank_correlation: "bg-evidence-held",
  other: "bg-evidence-neutral",
};

export const TourLeads: React.FC<TourLeadsProps> = ({ view, issues, number, total, purpose }) => {
  const counts = new Map<string, number>();
  for (const lead of view.leads) {
    const key = lead.category ?? "unclassified";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const breakdown = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...breakdown.map(([, n]) => n));

  return (
    <TourChapterFrame number={number} total={total} eyebrow="Due diligence" title="Leads investigated and closed" purpose={purpose} layout="wide">
      {view.leads.length === 0 ? (
        <p className="tour-rise rounded-lg border border-dashed border-surface-border p-8 text-sm text-muted" style={riseStyle(2)}>
          No leads were closed in this run.
        </p>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6" style={riseStyle(2)}>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Closed leads</p>
              <p className="mt-3 font-mono text-5xl font-semibold leading-none tabular-nums">{view.leads.length}</p>
              <p className="mt-3 text-xs text-muted">Each tripped a detector, was investigated, and was closed without an accusation.</p>
            </div>
            <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6" style={riseStyle(3)}>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Why they were closed</p>
              <ul className="mt-4 space-y-3">
                {breakdown.map(([category, n], i) => (
                  <li key={category} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_2rem] items-center gap-3 text-xs">
                    <span className="truncate text-foreground">
                      {category in CLOSURE_LABELS ? CLOSURE_LABELS[category as keyof typeof CLOSURE_LABELS] : UNCLASSIFIED_CLOSURE_LABEL}
                    </span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface-border">
                      <span
                        className={`tour-grow-x block h-full rounded-full ${CATEGORY_BAR[category] ?? "bg-muted"}`}
                        style={{ width: `${(n / max) * 100}%`, ...riseStyle(4 + i) }}
                      />
                    </span>
                    <span className="text-right font-mono tabular-nums text-muted">{n}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="tour-rise mt-8" style={riseStyle(6)}>
            <LeadsTable leads={view.leads} />
          </div>
        </>
      )}
      <IssueNotice issues={issuesForPath(issues, "leads_not_pursued")} />
    </TourChapterFrame>
  );
};
