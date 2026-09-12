"use client";

// Task 13: the export toolbar -- Print/PDF (via @media print in globals.css), a self-contained HTML
// file, and Markdown with the money trail embedded as a ```mermaid fence. Also surfaces the source
// and format-check chips and the expand/collapse controls. Export buttons wait for every diagram to
// finish rendering (diagramsSettled) so an export never fires mid-render with a missing source.

import React from "react";
import Link from "next/link";
import { FileCode2, FileJson, FileText, Printer } from "lucide-react";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";
import { buildCaseFileMarkdown } from "@/lib/caseFile/toMarkdown";
import { buildStandaloneHtml } from "@/lib/caseFile/toHtml";
import { downloadTextFile } from "@/lib/caseFile/download";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { LoadedCaseFile } from "@/hooks/useCaseFileSource";
import type { ValidationIssue } from "@/types/caseFile";

declare global {
  interface Window {
    __caseFileDebug?: {
      buildMarkdown: () => string;
      buildHtml: () => string;
      issues: ValidationIssue[];
    };
  }
}

interface ExportToolbarProps {
  loaded: LoadedCaseFile;
  view: CaseFileView;
  issues: ValidationIssue[];
  estateChecked: boolean;
  showValidation: boolean;
  onToggleValidation: () => void;
}

export const ExportToolbar: React.FC<ExportToolbarProps> = ({ loaded, view, issues, estateChecked, showValidation, onToggleValidation }) => {
  const { expandAll, collapseAll, diagrams, diagramsSettled } = useCaseFileUi();

  const estateErrorCount = issues.filter((i) => i.code.startsWith("E_ESTATE_")).length;
  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;
  const seedLabel = loaded.document.seed ?? "unknown";
  const isSample = loaded.source.kind === "sample";

  const renderedSources = React.useMemo(() => {
    const map: Record<string, string | null> = {};
    for (const [id, state] of Object.entries(diagrams)) {
      map[id] = state.renderedSource;
    }
    return map;
  }, [diagrams]);

  const buildMarkdown = React.useCallback(
    () => buildCaseFileMarkdown(view, { isSample, renderedSources, estateChecked }),
    [view, isSample, renderedSources, estateChecked]
  );

  const buildHtml = React.useCallback(() => {
    const el = document.getElementById("case-file-document");
    if (!el) throw new Error("case-file-document not mounted");
    return buildStandaloneHtml({ documentElement: el, title: `Case file · seed ${seedLabel}`, raw: loaded.raw });
  }, [seedLabel, loaded.raw]);

  React.useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    window.__caseFileDebug = { buildMarkdown, buildHtml, issues };
    return () => {
      delete window.__caseFileDebug;
    };
  }, [buildMarkdown, buildHtml, issues]);

  const handlePrint = () => window.print();
  const handleHtml = () => downloadTextFile(`case-file-seed-${seedLabel}.html`, buildHtml(), "text/html;charset=utf-8");
  const handleMarkdown = () => downloadTextFile(`case-file-seed-${seedLabel}.md`, buildMarkdown(), "text/markdown;charset=utf-8");
  const handleJson = () => downloadTextFile(`submission-seed-${seedLabel}.json`, `${JSON.stringify(loaded.raw, null, 2)}\n`, "application/json");

  const formatChipClass =
    errorCount > 0
      ? "border-status-danger/40 bg-status-danger/10 text-status-danger"
      : "border-status-success/40 bg-status-success/10 text-status-success";
  const formatChipLabel =
    errorCount > 0
      ? `Format check: ${errorCount} error(s) · ${warningCount} warning(s)`
      : warningCount > 0
      ? `Format check: PASS · ${warningCount} warning(s)`
      : "Format check: PASS";

  return (
    <div data-print="hide" className="sticky top-0 z-30 border-b border-surface-border bg-surface-deep/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-2 px-4 py-2">
        <span className="rounded-md border border-surface-border px-2 py-1 text-xs text-muted">{loaded.source.label}</span>
        <button
          type="button"
          onClick={onToggleValidation}
          aria-pressed={showValidation}
          className={`rounded-md border px-2 py-1 text-xs ${formatChipClass}`}
        >
          {formatChipLabel}
        </button>
        {estateChecked ? (
          <span
            className={`rounded-md border px-2 py-1 text-xs ${
              estateErrorCount > 0
                ? "border-status-danger/40 bg-status-danger/10 text-status-danger"
                : "border-status-success/40 bg-status-success/10 text-status-success"
            }`}
          >
            {estateErrorCount > 0 ? `Estate check: ${estateErrorCount} error(s)` : "Estate check: PASS"}
          </span>
        ) : (
          <Link href="/investigate/data" className="rounded-md border border-surface-border px-2 py-1 text-xs text-muted hover:text-foreground">
            Estate: not loaded
          </Link>
        )}

        <span className="mx-1 hidden h-5 w-px bg-surface-border sm:inline" aria-hidden="true" />

        <button type="button" onClick={expandAll} className="app-button text-xs">
          Expand all
        </button>
        <button type="button" onClick={collapseAll} className="app-button text-xs">
          Collapse all
        </button>

        <span className="mx-1 hidden h-5 w-px bg-surface-border sm:inline" aria-hidden="true" />

        <button
          type="button"
          onClick={handlePrint}
          disabled={!diagramsSettled}
          title={diagramsSettled ? undefined : "Rendering diagrams…"}
          className="app-button flex items-center gap-1.5 text-xs"
        >
          <Printer className="h-3.5 w-3.5" aria-hidden="true" />
          Print / PDF
        </button>
        <button
          type="button"
          onClick={handleHtml}
          disabled={!diagramsSettled}
          title={diagramsSettled ? undefined : "Rendering diagrams…"}
          className="app-button flex items-center gap-1.5 text-xs"
        >
          <FileCode2 className="h-3.5 w-3.5" aria-hidden="true" />
          HTML
        </button>
        <button
          type="button"
          onClick={handleMarkdown}
          disabled={!diagramsSettled}
          title={diagramsSettled ? undefined : "Rendering diagrams…"}
          className="app-button flex items-center gap-1.5 text-xs"
        >
          <FileText className="h-3.5 w-3.5" aria-hidden="true" />
          Markdown
        </button>
        <button
          type="button"
          onClick={handleJson}
          disabled={!diagramsSettled}
          title={diagramsSettled ? undefined : "Rendering diagrams…"}
          className="app-button flex items-center gap-1.5 text-xs"
        >
          <FileJson className="h-3.5 w-3.5" aria-hidden="true" />
          JSON
        </button>
      </div>
    </div>
  );
};
