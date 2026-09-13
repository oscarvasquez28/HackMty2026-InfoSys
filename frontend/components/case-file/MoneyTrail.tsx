"use client";

// Task 7: the rendered money-trail diagram (never prose-only, per case_file_structure.md) plus the
// chronological step timeline underneath it, each step citing an exhibit id. The printable document
// shows a static figure; the guided tour hands the same diagram to MoneyTrailPlayer.

import React, { useState } from "react";
import type { FindingView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { MermaidDiagram, type DiagramZoom } from "@/components/case-file/MermaidDiagram";
import { MoneyTrailTimeline } from "@/components/case-file/MoneyTrailTimeline";
import { IssueNotice } from "@/components/case-file/IssueNotice";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";
import { MoneyTrailPlayer } from "@/components/case-file/tour/MoneyTrailPlayer";

interface MoneyTrailProps {
  finding: FindingView;
  figureNumber: number;
  issues: ValidationIssue[];
  variant?: "document" | "tour";
}

export const MoneyTrail: React.FC<MoneyTrailProps> = ({ finding, figureNumber, issues, variant = "document" }) => {
  const [zoom, setZoom] = useState<DiagramZoom>("fit");
  const { trail, mermaidPrimary, mermaidGenerated } = finding;
  const { diagrams } = useCaseFileUi();
  const diagramState = diagrams[finding.anchorId];

  if (trail === null) {
    return (
      <div>
        <div className="rounded-sm border border-dashed border-paper-border p-4 text-sm text-paper-muted">
          No money trail was supplied for this finding.
        </div>
        <IssueNotice issues={issues} />
      </div>
    );
  }

  const hasSource = Boolean(mermaidPrimary || mermaidGenerated);
  const usedFallback = diagramState?.usedFallback ?? !mermaidPrimary;
  const sourceDescription = `${usedFallback || !mermaidPrimary ? "generated from money_trail steps" : "supplied by the run"}${
    usedFallback && mermaidPrimary ? " (supplied diagram failed to render)" : ""
  }`;
  const renderedSource = diagramState?.renderedSource ?? null;

  if (variant === "tour" && hasSource) {
    return (
      <div>
        <MoneyTrailPlayer finding={finding} figureNumber={figureNumber} sourceDescription={sourceDescription} renderedSource={renderedSource} />
        <IssueNotice issues={issues} />
      </div>
    );
  }

  return (
    <div>
      {hasSource && (
        <figure className="case-avoid-break rounded-sm border border-paper-border bg-paper-sheet p-4">
          <div data-print="hide" data-export="exclude" role="group" aria-label="Diagram zoom" className="mb-2 flex justify-end gap-1">
            <button
              type="button"
              aria-pressed={zoom === "fit"}
              onClick={() => setZoom("fit")}
              className={`rounded-sm px-2 py-0.5 text-[11px] ${zoom === "fit" ? "bg-paper-ink text-paper" : "border border-paper-border text-paper-muted"}`}
            >
              Fit
            </button>
            <button
              type="button"
              aria-pressed={zoom === "full"}
              onClick={() => setZoom("full")}
              className={`rounded-sm px-2 py-0.5 text-[11px] ${zoom === "full" ? "bg-paper-ink text-paper" : "border border-paper-border text-paper-muted"}`}
            >
              100%
            </button>
          </div>
          <div className={zoom === "full" ? "case-scroll overflow-x-auto" : ""}>
            <MermaidDiagram
              diagramId={finding.anchorId}
              primarySource={mermaidPrimary}
              fallbackSource={mermaidGenerated}
              ariaLabel={`Money trail diagram for finding ${finding.number}`}
              variant={variant}
              zoom={zoom}
            />
          </div>
          <figcaption className="mt-3 font-mono text-[11px] text-paper-muted">
            Figure {figureNumber}. Money trail — {trail.length} step(s). Diagram source: {sourceDescription}.
          </figcaption>
          <details data-print="hide" data-export="exclude" className="mt-2 text-xs text-paper-muted">
            <summary className="cursor-pointer">View diagram source</summary>
            <pre className="mt-1 overflow-x-auto font-mono text-xs">{renderedSource ?? mermaidPrimary ?? mermaidGenerated}</pre>
          </details>
        </figure>
      )}

      <div className="mt-4">
        <MoneyTrailTimeline trail={trail} />
      </div>
      <IssueNotice issues={issues} />
    </div>
  );
};
