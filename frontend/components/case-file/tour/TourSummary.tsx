"use client";

// Chapter 2: the executive summary as a narrative plus an asymmetric grid of headline figures.

import React from "react";
import type { SummaryView } from "@/lib/caseFile/derive";
import { formatInteger, formatPesos } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";
import { ConfidenceBadge } from "@/components/case-file/ConfidenceBadge";
import { TourChapterFrame, riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourSummaryProps {
  summary: SummaryView;
  number: number;
  total: number;
  purpose: string;
}

export const TourSummary: React.FC<TourSummaryProps> = ({ summary, number, total, purpose }) => {
  const exposure = useCountUp(summary.totalExposure, { delayMs: 500, durationMs: 1500 });
  const findings = useCountUp(summary.findingsCount, { delayMs: 650 });
  const leads = useCountUp(summary.closedLeadsCount, { delayMs: 750 });
  const judged = summary.proven + summary.probable;

  return (
    <TourChapterFrame number={number} total={total} eyebrow="The result" title="Executive summary" purpose={purpose}>
      <p className="tour-rise max-w-[65ch] text-lg leading-8 text-foreground/90 sm:text-xl sm:leading-9" style={riseStyle(1)}>
        {summary.narrative}
      </p>
      {summary.narrativeOrigin === "derived" && (
        <p className="tour-rise mt-3 text-xs text-muted" style={riseStyle(2)}>
          Summary generated from the findings data (the run supplied no narrative).
        </p>
      )}

      <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6 sm:col-span-2" style={riseStyle(3)}>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Total exposure</p>
          <p className="mt-3 font-mono text-[clamp(1.75rem,4vw,2.75rem)] font-semibold leading-none tabular-nums text-foreground">
            {formatPesos(exposure)}
          </p>
          <p className="mt-3 text-xs text-muted">Sum of the amounts at issue across every finding.</p>
        </div>

        <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6" style={riseStyle(4)}>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Findings</p>
          <p className="mt-3 font-mono text-5xl font-semibold leading-none tabular-nums">{formatInteger(findings)}</p>
          <p className="mt-3 text-xs text-muted">validated accusations</p>
        </div>

        <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6 sm:col-span-2" style={riseStyle(5)}>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Overall confidence</p>
          <div className="tour-stamp mt-3 inline-block" style={{ "--stamp-delay": "800ms" } as React.CSSProperties}>
            <ConfidenceBadge value={summary.globalConfidence} size="lg" />
          </div>
          {judged > 0 && (
            <div className="mt-5">
              <div className="tour-grow-x flex h-2 overflow-hidden rounded-full bg-surface-border" style={riseStyle(6)}>
                <span className="bg-evidence-proven" style={{ width: `${(summary.proven / judged) * 100}%` }} />
                <span className="bg-evidence-probable" style={{ width: `${(summary.probable / judged) * 100}%` }} />
              </div>
              <p className="mt-2 text-xs text-muted">
                <span className="text-evidence-proven">{summary.proven} proven</span> ·{" "}
                <span className="text-evidence-probable">{summary.probable} probable</span>
                {summary.invalid > 0 ? ` · ${summary.invalid} invalid` : ""}
              </p>
            </div>
          )}
        </div>

        <div className="tour-rise rounded-lg border border-surface-border bg-surface p-6" style={riseStyle(6)}>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Leads closed</p>
          <p className="mt-3 font-mono text-5xl font-semibold leading-none tabular-nums">{formatInteger(leads)}</p>
          <p className="mt-3 text-xs text-muted">investigated without an accusation</p>
        </div>
      </div>
    </TourChapterFrame>
  );
};
