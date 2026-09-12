"use client";

// Renders a mermaid source into an inline SVG, trying the run-supplied source first and falling
// back to the generated one if it fails to parse/render. Reports its settled state to
// CaseFileUiContext so export buttons know every diagram has finished attempting to render.

import React, { useEffect, useRef, useState } from "react";
import { renderMermaidSvg } from "@/lib/caseFile/mermaid";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";

interface MermaidDiagramProps {
  diagramId: string;
  primarySource: string | null;
  fallbackSource: string | null;
  ariaLabel: string;
}

type State = { status: "pending" } | { status: "ready"; svg: string } | { status: "failed"; error: string };

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ diagramId, primarySource, fallbackSource, ariaLabel }) => {
  const { reportDiagram } = useCaseFileUi();
  const [state, setState] = useState<State>({ status: "pending" });
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    setState({ status: "pending" });
    reportDiagram(diagramId, { status: "pending", renderedSource: null, usedFallback: false });

    async function run() {
      const primary = primarySource;
      if (primary) {
        try {
          const svg = await renderMermaidSvg(`${diagramId}-svg`, primary);
          if (cancelledRef.current) return;
          setState({ status: "ready", svg });
          reportDiagram(diagramId, { status: "ready", renderedSource: primary, usedFallback: false });
          return;
        } catch {
          // fall through to fallback source below
        }
      }
      const fallback = fallbackSource;
      if (fallback) {
        try {
          const svg = await renderMermaidSvg(`${diagramId}-svg-fallback`, fallback);
          if (cancelledRef.current) return;
          setState({ status: "ready", svg });
          reportDiagram(diagramId, { status: "ready", renderedSource: fallback, usedFallback: true });
          return;
        } catch (e) {
          if (cancelledRef.current) return;
          const message = e instanceof Error ? e.message : String(e);
          setState({ status: "failed", error: message });
          reportDiagram(diagramId, { status: "failed", renderedSource: null, usedFallback: true });
          return;
        }
      }
      if (cancelledRef.current) return;
      setState({ status: "failed", error: "No diagram source was available." });
      reportDiagram(diagramId, { status: "failed", renderedSource: null, usedFallback: false });
    }

    void run();
    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramId, primarySource, fallbackSource]);

  if (state.status === "pending") {
    return <p className="text-sm text-paper-muted">Rendering diagram…</p>;
  }
  if (state.status === "failed") {
    return (
      <div>
        <p className="text-sm text-evidence-probable">The money trail diagram could not be rendered.</p>
        <details data-print="hide" data-export="exclude" className="mt-1 text-xs text-paper-muted">
          <summary className="cursor-pointer">Error detail</summary>
          <pre className="mt-1 overflow-x-auto font-mono text-[11px]">{state.error}</pre>
        </details>
      </div>
    );
  }
  return <div role="img" aria-label={ariaLabel} dangerouslySetInnerHTML={{ __html: state.svg }} />;
};
