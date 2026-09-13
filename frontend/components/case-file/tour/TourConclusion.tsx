"use client";

// Final chapter: a recap of the verdict and a map of every part of the case file, each one a card
// the reader can reopen. Concluding is done from the action bar.

import React from "react";
import { ArrowUpRight, CircleCheck, RotateCcw } from "lucide-react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import { groupTourChapters, type TourChapter } from "@/lib/caseFile/tour";
import { formatPesos } from "@/lib/utils";
import { ConfidenceBadge } from "@/components/case-file/ConfidenceBadge";
import { TourChapterFrame, riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourConclusionProps {
  view: CaseFileView;
  chapters: TourChapter[];
  visited: Set<string>;
  number: number;
  onRevisit: (index: number) => void;
  onRestart: () => void;
}

function cardMetric(chapter: TourChapter, view: CaseFileView): string {
  switch (chapter.kind) {
    case "opening":
      return view.document.header?.company || "Company not reported";
    case "summary":
      return `${view.summary.findingsCount} finding(s) · ${formatPesos(view.summary.totalExposure)}`;
    case "finding": {
      const finding = view.findings[chapter.findingIndex ?? 0];
      const amount = finding.finding.peso_amount !== null ? formatPesos(finding.finding.peso_amount) : "amount n/a";
      return `${finding.entities.map((e) => e.name ?? e.id).join(", ")} · ${amount}`;
    }
    case "leads":
      return `${view.leads.length} lead(s) closed`;
    case "method":
      return "Architecture, scope and reproducibility";
    default:
      return "";
  }
}

export const TourConclusion: React.FC<TourConclusionProps> = ({ view, chapters, visited, number, onRevisit, onRestart }) => {
  const groups = groupTourChapters(chapters).filter((g) => chapters[g.startIndex].kind !== "conclusion");
  const conclusion = chapters[chapters.length - 1];

  return (
    <TourChapterFrame
      number={number}
      total={chapters.length}
      eyebrow="Before you close"
      title="Review route"
      purpose={conclusion.purpose}
      aside={
        <div className="space-y-5">
          <div className="rounded-lg border border-surface-border bg-surface p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Verdict</p>
            <div className="tour-stamp mt-3 inline-block" style={{ "--stamp-delay": "700ms" } as React.CSSProperties}>
              <ConfidenceBadge value={view.summary.globalConfidence} size="lg" />
            </div>
            <p className="mt-3 font-mono text-xl font-semibold tabular-nums">{formatPesos(view.summary.totalExposure)}</p>
            <p className="mt-1 text-xs text-muted">
              {view.summary.findingsCount} finding(s) · {view.summary.closedLeadsCount} lead(s) closed
            </p>
          </div>
          <button type="button" onClick={onRestart} className="app-button flex items-center gap-2 text-sm">
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Restart the tour
          </button>
        </div>
      }
    >
      <p className="section-label tour-rise" style={riseStyle(2)}>
        Revisit a part
      </p>
      <ul className="mt-5 grid gap-3 sm:grid-cols-2">
        {groups.map((group, i) => {
          const chapter = chapters[group.startIndex];
          const isVisited = visited.has(group.baseKey);
          return (
            <li key={group.baseKey} className={`tour-rise ${i === 0 ? "sm:col-span-2" : ""}`} style={riseStyle(3 + i)}>
              <button
                type="button"
                onClick={() => onRevisit(group.startIndex)}
                className="group flex h-full min-h-24 w-full flex-col justify-between gap-4 rounded-lg border border-surface-border bg-surface p-5 text-left transition-[transform,border-color,background-color] duration-300 hover:-translate-y-0.5 hover:border-brand-500/50 hover:bg-surface-blue active:translate-y-0"
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="font-mono text-[10px] text-brand-500">{String(i + 1).padStart(2, "0")}</span>
                    <span className="mt-1 block text-sm font-semibold text-foreground">{chapter.kind === "finding" ? group.label : chapter.label}</span>
                  </span>
                  <ArrowUpRight
                    className="h-4 w-4 shrink-0 text-muted transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-brand-500"
                    aria-hidden="true"
                  />
                </span>
                <span className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate text-xs text-muted">{cardMetric(chapter, view)}</span>
                  {isVisited ? (
                    <span className="flex shrink-0 items-center gap-1 text-[11px] text-status-success">
                      <CircleCheck className="h-3.5 w-3.5" aria-hidden="true" />
                      Reviewed
                    </span>
                  ) : (
                    <span className="shrink-0 text-[11px] text-muted">Not opened</span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </TourChapterFrame>
  );
};
