"use client";

// Closing state after "Conclude report": a drawn check, the verdict in one line, and the export
// actions. Exports stay disabled until every diagram in the printable document has rendered.

import React from "react";
import { FileCode2, FileJson, FileText, Plus, Printer, Undo2 } from "lucide-react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { UseCaseFileExportsReturn } from "@/hooks/useCaseFileExports";
import { formatPesos } from "@/lib/utils";
import { riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourConcludedProps {
  view: CaseFileView;
  exports: UseCaseFileExportsReturn;
  onRevisit: () => void;
  onReset?: () => void;
}

export const TourConcluded: React.FC<TourConcludedProps> = ({ view, exports, onRevisit, onReset }) => {
  const { summary } = view;
  const company = view.document.header?.company || "this company";
  const actions: Array<{ label: string; detail: string; icon: typeof Printer; onClick: () => void }> = [
    { label: "Print / PDF", detail: "Full document, print layout", icon: Printer, onClick: exports.printDocument },
    { label: "HTML", detail: "Self-contained file with source JSON", icon: FileCode2, onClick: exports.downloadHtml },
    { label: "Markdown", detail: "Money trails as mermaid fences", icon: FileText, onClick: exports.downloadMarkdown },
    { label: "JSON", detail: "The original submission", icon: FileJson, onClick: exports.downloadJson },
  ];

  return (
    <div className="mx-auto grid w-full max-w-[1200px] gap-12 px-4 py-14 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16 lg:py-20">
      <div>
        <div className="relative h-20 w-20">
          <span aria-hidden="true" className="tour-ring absolute inset-0 rounded-full border border-brand-500/60" />
          <svg viewBox="0 0 80 80" className="relative h-20 w-20" aria-hidden="true">
            <circle cx="40" cy="40" r="38" className="fill-brand-500/10 stroke-brand-500/40" strokeWidth="1.5" />
            <path d="M24 41 L35 52 L57 29" pathLength={1} className="tour-check-path fill-none stroke-brand-500" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <p className="section-label tour-rise mt-8" style={riseStyle(1)}>
          Case file · seed {view.document.seed ?? "unknown"}
        </p>
        <h2 data-chapter-heading tabIndex={-1} className="tour-mask mt-3 text-[clamp(2rem,4.5vw,3.25rem)] font-semibold leading-[1.05] tracking-tight outline-none">
          <span style={{ "--mask-delay": "300ms" } as React.CSSProperties}>Review concluded</span>
        </h2>
        <p className="tour-rise mt-5 max-w-[48ch] text-base leading-7 text-muted" style={riseStyle(3)}>
          You reviewed the case file for <span className="text-foreground">{company}</span>: {summary.findingsCount} finding(s) totaling{" "}
          <span className="font-mono text-foreground">{formatPesos(summary.totalExposure)}</span>, and {summary.closedLeadsCount} lead(s) closed without
          an accusation.
        </p>
        <div className="tour-rise mt-8 flex flex-wrap gap-3" style={riseStyle(4)}>
          <button type="button" onClick={onRevisit} className="app-button flex items-center gap-2 text-sm active:translate-y-px">
            <Undo2 className="h-4 w-4" aria-hidden="true" />
            Revisit the report
          </button>
          {onReset && (
            <button type="button" onClick={onReset} className="app-button flex items-center gap-2 text-sm active:translate-y-px">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Open another file
            </button>
          )}
        </div>
      </div>

      <div className="self-center">
        <p className="section-label tour-rise" style={riseStyle(3)}>
          Take it with you
        </p>
        <ul className="mt-5 grid gap-3">
          {actions.map(({ label, detail, icon: Icon, onClick }, i) => (
            <li key={label} className="tour-rise" style={riseStyle(4 + i)}>
              <button
                type="button"
                onClick={onClick}
                disabled={!exports.ready}
                className="group flex min-h-16 w-full items-center gap-4 rounded-lg border border-surface-border bg-surface px-5 py-3 text-left transition-[transform,border-color,background-color] duration-300 hover:-translate-y-0.5 hover:border-brand-500/50 hover:bg-surface-blue active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-500">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-foreground">{label}</span>
                  <span className="block truncate text-xs text-muted">{exports.ready ? detail : "Rendering diagrams…"}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
