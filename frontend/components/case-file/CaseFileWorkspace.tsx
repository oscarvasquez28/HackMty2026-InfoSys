"use client";

// Top-level shell for /investigate: wires the loaded case file (from InvestigateSessionProvider)
// through validation and derivation, then renders either the source-selection empty state or the
// guided tour with its export toolbar. The full document stays mounted (hidden on screen) as the
// source for Print and the HTML export. See doc/frontend/README.md §10.

import React, { useEffect, useMemo, useState } from "react";
import { useInvestigateSession } from "@/components/investigate/InvestigateSessionProvider";
import { InvestigateAppBar } from "@/components/investigate/InvestigateAppBar";
import { CaseFileSourcePanel } from "@/components/case-file/CaseFileSourcePanel";
import { CaseFileUiProvider } from "@/components/case-file/CaseFileUiContext";
import { ExportToolbar } from "@/components/case-file/ExportToolbar";
import { ValidationPanel } from "@/components/case-file/ValidationPanel";
import { CaseFileDocument } from "@/components/case-file/CaseFileDocument";
import { CaseFileTour } from "@/components/case-file/tour/CaseFileTour";
import { buildCaseFileView } from "@/lib/caseFile/derive";
import { collectWarnings } from "@/lib/caseFile/validate";
import { validateAgainstEstate } from "@/lib/estate/estateCheck";
import type { ValidationIssue } from "@/types/caseFile";

const API_ENABLED = process.env.NEXT_PUBLIC_CASE_FILE_API === "enabled";

export const CaseFileWorkspace: React.FC = () => {
  const { caseFile, estate } = useInvestigateSession();
  const { loaded, error, status, loadFixture, loadFile, loadFromApi, reset } = caseFile;
  const [showValidation, setShowValidation] = useState(false);

  const view = useMemo(
    () => (loaded ? buildCaseFileView(loaded.document, estate.hasEstate ? estate.tables : null) : null),
    [loaded, estate.hasEstate, estate.tables]
  );
  const issues = useMemo<ValidationIssue[]>(() => {
    if (!loaded || !view) return [];
    const estateIssues = estate.hasEstate ? validateAgainstEstate(loaded.document, estate.tables) : [];
    return [...loaded.structureIssues, ...collectWarnings(view), ...estateIssues];
  }, [loaded, view, estate.hasEstate, estate.tables]);

  useEffect(() => {
    if (!loaded || process.env.NODE_ENV === "production") return;
    for (const issue of issues) {
      // eslint-disable-next-line no-console
      console.warn(`[case-file] ${issue.path}: ${issue.message}`);
    }
  }, [loaded, issues]);

  useEffect(() => {
    if (!loaded) return;
    const previous = document.title;
    document.title = `case-file-seed-${loaded.document.seed ?? "unknown"}`;
    return () => {
      document.title = previous;
    };
  }, [loaded]);

  const expectedDiagramIds = useMemo(
    () => (view ? view.findings.filter((f) => f.mermaidPrimary || f.mermaidGenerated).map((f) => f.anchorId) : []),
    [view]
  );

  return (
    <div className="case-workspace min-h-[100dvh] bg-background text-foreground">
      <InvestigateAppBar sourceLabel={loaded?.source.label} onReset={loaded ? reset : undefined} />
      {!loaded || !view ? (
        <CaseFileSourcePanel
          error={error}
          isLoading={status === "loading"}
          onLoadFixture={loadFixture}
          onLoadFile={loadFile}
          onLoadFromApi={API_ENABLED ? loadFromApi : undefined}
          apiEnabled={API_ENABLED}
          estateNote={estate.hasEstate ? `Data estate loaded (${estate.totalRows.toLocaleString("en-US")} rows). Exhibits will be checked against it.` : null}
        />
      ) : (
        <CaseFileUiProvider key={loaded.loadId} expectedDiagramIds={expectedDiagramIds}>
          <ExportToolbar
            loaded={loaded}
            view={view}
            issues={issues}
            estateChecked={estate.hasEstate}
            showValidation={showValidation}
            onToggleValidation={() => setShowValidation((v) => !v)}
          />
          <ValidationPanel issues={issues} open={showValidation} />
          <main className="print:p-0">
            {/* Screen: the guided tour. It comes first so in-page #anchors resolve to it. */}
            <CaseFileTour loaded={loaded} view={view} issues={issues} estateChecked={estate.hasEstate} onReset={reset} />
            {/* Print and HTML/Markdown exports: the full vertical document, hidden on screen. */}
            <div className="hidden print:block">
              <CaseFileDocument view={view} source={loaded.source} issues={issues} />
            </div>
          </main>
        </CaseFileUiProvider>
      )}
    </div>
  );
};
