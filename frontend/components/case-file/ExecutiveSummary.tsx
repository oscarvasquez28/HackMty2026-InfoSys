"use client";

// Task 2: the executive summary a judge should be able to read alone and understand the result --
// a plain-language narrative plus the four-card synoptic table (findings, confidence, exposure, leads).

import React from "react";
import type { SummaryView } from "@/lib/caseFile/derive";
import { ConfidenceBadge } from "@/components/case-file/ConfidenceBadge";
import { AudioPlayer } from "@/components/AudioPlayer";
import { formatPesos } from "@/lib/utils";

interface ExecutiveSummaryProps {
  summary: SummaryView;
}

export const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ summary }) => {
  return (
    <section id="executive-summary">
      <h2 className="mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight text-paper-ink">
        2. Executive summary
      </h2>
      <p className="max-w-prose font-serif text-[17px] leading-8">{summary.narrative}</p>
      {summary.narrativeOrigin === "derived" && (
        <p className="mt-2 text-xs text-paper-muted">Summary generated from the findings data (the run supplied no narrative).</p>
      )}
      <div className="mt-4 print:hidden">
        <AudioPlayer textToSynthesize={summary.narrative} label="Listen to executive summary" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 print:grid-cols-4">
        <div className="case-avoid-break rounded-sm border border-paper-border bg-paper-raised p-4">
          <dl>
            <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper-muted">Findings</dt>
            <dd className="mt-2 font-serif text-3xl font-semibold">{summary.findingsCount}</dd>
          </dl>
          <p className="mt-1 text-xs text-paper-muted">validated accusations</p>
        </div>
        <div className="case-avoid-break rounded-sm border border-paper-border bg-paper-raised p-4">
          <dl>
            <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper-muted">Overall confidence</dt>
            <dd className="mt-2">
              <ConfidenceBadge value={summary.globalConfidence} size="lg" />
            </dd>
          </dl>
          <p className="mt-1 text-xs text-paper-muted">
            {summary.proven} proven · {summary.probable} probable
            {summary.invalid > 0 ? ` · ${summary.invalid} invalid` : ""}
          </p>
        </div>
        <div className="case-avoid-break rounded-sm border border-paper-border bg-paper-raised p-4">
          <dl>
            <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper-muted">Total exposure</dt>
            <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{formatPesos(summary.totalExposure)}</dd>
          </dl>
          <p className="mt-1 text-xs text-paper-muted">sum of finding amounts</p>
        </div>
        <div className="case-avoid-break rounded-sm border border-paper-border bg-paper-raised p-4">
          <dl>
            <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper-muted">Leads investigated and closed</dt>
            <dd className="mt-2 font-serif text-3xl font-semibold">{summary.closedLeadsCount}</dd>
          </dl>
          <p className="mt-1 text-xs text-paper-muted">closed without an accusation</p>
        </div>
      </div>
    </section>
  );
};
