"use client";

// Chapter 1: who was audited and how the run behaved, plus the route this review will follow.

import React from "react";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import type { CaseFileDocument } from "@/types/caseFile";
import type { TourChapter } from "@/lib/caseFile/tour";
import { groupTourChapters } from "@/lib/caseFile/tour";
import { formatInteger, formatPesos, formatSeconds } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";
import { TourChapterFrame, riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourOpeningProps {
  document: CaseFileDocument;
  isSample: boolean;
  chapters: TourChapter[];
  number: number;
  onGoTo: (index: number) => void;
}

const Metric: React.FC<{ label: string; className?: string; index: number; children: React.ReactNode }> = ({ label, className, index, children }) => (
  <div className={`tour-rise rounded-lg border border-surface-border bg-surface p-5 ${className ?? ""}`} style={riseStyle(index)}>
    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">{label}</p>
    <div className="mt-2 font-mono text-lg font-semibold tabular-nums text-foreground">{children}</div>
  </div>
);

const NotReported = () => <span className="text-sm font-normal text-muted">Not reported</span>;

export const TourOpening: React.FC<TourOpeningProps> = ({ document, isSample, chapters, number, onGoTo }) => {
  const { header, run_metadata: meta, seed } = document;
  const cost = useCountUp(meta.mxn_cost ?? 0, { delayMs: 500 });
  const calls = useCountUp(meta.llm_calls ?? 0, { delayMs: 600 });
  const seconds = useCountUp(meta.wall_clock_seconds ?? 0, { delayMs: 700 });
  const groups = groupTourChapters(chapters);
  const roleKeys = Object.keys(meta.cost_by_role).sort();

  return (
    <TourChapterFrame
      number={number}
      total={chapters.length}
      eyebrow="Forensic case file"
      title={header?.company || "Company not reported"}
      purpose={chapters[0].purpose}
      aside={
        <div className="space-y-3">
          <p className="font-mono text-sm text-muted">
            RFC <span className="text-foreground">{header?.company_rfc || "not reported"}</span>
          </p>
          <p className="font-mono text-sm text-muted">
            Audit period{" "}
            <span className="text-foreground">
              {header?.audit_period ? `${header.audit_period.start || "?"} → ${header.audit_period.end || "?"}` : "not reported"}
            </span>
          </p>
          {isSample && (
            <p className="inline-flex rounded-md border border-brand-500/30 bg-brand-500/10 px-3 py-1.5 font-mono text-xs text-brand-300">
              Sample data — illustrative, fictional entities. Not a real audit.
            </p>
          )}
        </div>
      }
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
        <Metric label="MXN cost of the run" className="col-span-2 sm:col-span-4" index={2}>
          {meta.mxn_cost !== null ? <span className="text-[clamp(1.6rem,3.2vw,2.4rem)]">{formatPesos(cost)}</span> : <NotReported />}
        </Metric>
        <Metric label="Seed" className="col-span-2" index={3}>
          {seed !== null ? `#${seed}` : <NotReported />}
        </Metric>
        <Metric label={`LLM calls${meta.llm_usage_estimated ? " (est.)" : ""}`} className="sm:col-span-2" index={4}>
          {meta.llm_calls !== null ? formatInteger(calls) : <NotReported />}
        </Metric>
        <Metric label={`LLM tokens${meta.llm_usage_estimated ? " (est.)" : ""}`} className="sm:col-span-2" index={4}>
          {meta.llm_tokens !== null ? formatInteger(meta.llm_tokens) : <NotReported />}
        </Metric>
        <Metric label="Wall clock" className="sm:col-span-2" index={5}>
          {meta.wall_clock_seconds !== null ? formatSeconds(seconds) : <NotReported />}
        </Metric>
        <Metric label="Determinism" className="col-span-2" index={6}>
          <span className="tour-stamp inline-block" style={{ "--stamp-delay": "900ms" } as React.CSSProperties}>
            {meta.deterministic === true ? (
              <span className="inline-flex items-center gap-1.5 text-sm text-status-success">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Reproducible
              </span>
            ) : meta.deterministic === false ? (
              <span className="inline-flex items-center gap-1.5 text-sm text-status-warning">
                <TriangleAlert className="h-4 w-4" aria-hidden="true" />
                Non-deterministic
              </span>
            ) : (
              <NotReported />
            )}
          </span>
        </Metric>
      </div>
      {roleKeys.length > 0 && (
        <p className="tour-rise mt-3 font-mono text-xs text-muted" style={riseStyle(7)}>
          Cost by role: {roleKeys.map((key) => `${key} ${formatPesos(meta.cost_by_role[key])}`).join(" · ")}
        </p>
      )}

      <div className="mt-12">
        <p className="section-label tour-rise" style={riseStyle(7)}>
          Route of this review
        </p>
        <ol className="relative mt-5">
          <span aria-hidden="true" className="tour-grow-y absolute bottom-3 left-[11px] top-3 w-px bg-gradient-to-b from-brand-500/60 via-surface-border to-surface-border" />
          {groups.map((group, i) => (
            <li key={group.baseKey} className="tour-rise relative" style={riseStyle(8 + i)}>
              <button
                type="button"
                onClick={() => onGoTo(group.startIndex)}
                className="group flex min-h-11 w-full items-center gap-4 rounded-md py-1.5 pr-3 text-left transition-colors duration-200 hover:bg-surface/60"
              >
                <span
                  className={`relative grid h-6 w-6 shrink-0 place-items-center rounded-full border font-mono text-[10px] ${
                    i === 0 ? "border-brand-500 bg-brand-500 text-brand-ink" : "border-surface-border bg-background text-muted group-hover:border-brand-500/60"
                  }`}
                >
                  {i + 1}
                </span>
                <span className="text-sm text-foreground">{chapters[group.startIndex].kind === "finding" ? group.label : chapters[group.startIndex].label}</span>
                {group.indices.length > 1 && <span className="font-mono text-[11px] text-muted">{group.indices.length} steps</span>}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </TourChapterFrame>
  );
};
