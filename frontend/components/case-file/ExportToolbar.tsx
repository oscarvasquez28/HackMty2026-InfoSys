"use client";

// Task 13: the export toolbar -- Print/PDF (via @media print in globals.css), a self-contained HTML
// file, and Markdown with the money trail embedded as a ```mermaid fence. Also surfaces the source
// and format-check chips. Export buttons wait for every diagram to finish rendering
// (diagramsSettled) so an export never fires mid-render with a missing source.

import React from "react";
import Link from "next/link";
import { FileArchive, FileCode2, FileJson, FileText, Printer } from "lucide-react";
import { useCaseFileExports } from "@/hooks/useCaseFileExports";
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
  const { ready, buildMarkdown, buildHtml, printDocument, downloadHtml, downloadMarkdown, downloadJson, downloadZip } = useCaseFileExports(
    loaded,
    view,
    estateChecked
  );

  const estateErrorCount = issues.filter((i) => i.code.startsWith("E_ESTATE_")).length;
  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;

  React.useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    window.__caseFileDebug = { buildMarkdown, buildHtml, issues };
    return () => {
      delete window.__caseFileDebug;
    };
  }, [buildMarkdown, buildHtml, issues]);

  // Auto-download the full export bundle once per loaded case file, as soon as every diagram has
  // settled. The ref guard also absorbs React StrictMode's double-effect run in dev.
  const autoDownloadedRef = React.useRef<number | null>(null);
  React.useEffect(() => {
    if (!ready || autoDownloadedRef.current === loaded.loadId) return;
    autoDownloadedRef.current = loaded.loadId;
    try {
      downloadZip();
    } catch (error) {
      autoDownloadedRef.current = null;
      // eslint-disable-next-line no-console
      console.warn("[case-file] automatic bundle download failed:", error);
    }
  }, [ready, loaded.loadId, downloadZip]);

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

  const exportButtons: Array<{ label: string; icon: typeof Printer; onClick: () => void }> = [
    { label: "All (.zip)", icon: FileArchive, onClick: downloadZip },
    { label: "Print / PDF", icon: Printer, onClick: printDocument },
    { label: "HTML", icon: FileCode2, onClick: downloadHtml },
    { label: "Markdown", icon: FileText, onClick: downloadMarkdown },
    { label: "JSON", icon: FileJson, onClick: downloadJson },
  ];

  return (
    <div data-print="hide" className="border-b border-surface-border bg-surface-deep/95">
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

        {exportButtons.map(({ label, icon: Icon, onClick }) => (
          <button
            key={label}
            type="button"
            onClick={onClick}
            disabled={!ready}
            title={ready ? undefined : "Rendering diagrams…"}
            className="app-button flex items-center gap-1.5 text-xs"
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
};
