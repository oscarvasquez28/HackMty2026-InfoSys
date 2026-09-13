"use client";

// Renders a mermaid source into an inline SVG, trying the run-supplied source first and falling
// back to the generated one if it fails to parse/render. The "document" variant (the printable
// document) reports its settled state to CaseFileUiContext so export buttons know every diagram has
// finished attempting to render; the "tour" variant renders in the portal palette, does not report,
// and tags edges/nodes so globals.css can draw the trail in.

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { renderMermaidSvg, themeGeneratedSource } from "@/lib/caseFile/mermaid";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";

interface MermaidDiagramProps {
  diagramId: string;
  primarySource: string | null;
  fallbackSource: string | null;
  ariaLabel: string;
  variant?: "document" | "tour";
}

type State = { status: "pending" } | { status: "ready"; svg: string } | { status: "failed"; error: string };

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ diagramId, primarySource, fallbackSource, ariaLabel, variant = "document" }) => {
  const { reportDiagram } = useCaseFileUi();
  const [state, setState] = useState<State>({ status: "pending" });
  const cancelledRef = useRef(false);
  const svgHostRef = useRef<HTMLDivElement>(null);
  const isTour = variant === "tour";

  useEffect(() => {
    cancelledRef.current = false;
    const theme = isTour ? "dark" : "light";
    const idSuffix = isTour ? "-tour" : "";
    const report: typeof reportDiagram = (id, next) => {
      if (!isTour) reportDiagram(id, next);
    };
    setState({ status: "pending" });
    report(diagramId, { status: "pending", renderedSource: null, usedFallback: false });

    async function run() {
      const primary = primarySource;
      if (primary) {
        try {
          const svg = await renderMermaidSvg(`${diagramId}${idSuffix}-svg`, primary, theme);
          if (cancelledRef.current) return;
          setState({ status: "ready", svg });
          report(diagramId, { status: "ready", renderedSource: primary, usedFallback: false });
          return;
        } catch {
          // fall through to fallback source below
        }
      }
      const fallback = fallbackSource;
      if (fallback) {
        try {
          const svg = await renderMermaidSvg(`${diagramId}${idSuffix}-svg-fallback`, themeGeneratedSource(fallback, theme), theme);
          if (cancelledRef.current) return;
          setState({ status: "ready", svg });
          report(diagramId, { status: "ready", renderedSource: fallback, usedFallback: true });
          return;
        } catch (e) {
          if (cancelledRef.current) return;
          const message = e instanceof Error ? e.message : String(e);
          setState({ status: "failed", error: message });
          report(diagramId, { status: "failed", renderedSource: null, usedFallback: true });
          return;
        }
      }
      if (cancelledRef.current) return;
      setState({ status: "failed", error: "No diagram source was available." });
      report(diagramId, { status: "failed", renderedSource: null, usedFallback: false });
    }

    void run();
    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramId, primarySource, fallbackSource, isTour]);

  // Tour only: normalize edge lengths and stagger indices so CSS can draw the trail step by step.
  useLayoutEffect(() => {
    if (!isTour || state.status !== "ready" || !svgHostRef.current) return;
    const host = svgHostRef.current;
    host.querySelectorAll<SVGPathElement>(".flowchart-link").forEach((path, i) => {
      path.setAttribute("pathLength", "1");
      path.style.setProperty("--edge-i", String(i));
    });
    host.querySelectorAll<SVGGElement>(".edgeLabel").forEach((label, i) => label.style.setProperty("--edge-i", String(i)));
    host.querySelectorAll<SVGGElement>(".node").forEach((node, i) => node.style.setProperty("--node-i", String(i)));
  }, [isTour, state]);

  if (state.status === "pending") {
    return isTour ? (
      <div className="h-48 w-full animate-pulse rounded-md bg-paper-raised" aria-label="Rendering diagram" />
    ) : (
      <p className="text-sm text-paper-muted">Rendering diagram…</p>
    );
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
  return (
    <div
      ref={svgHostRef}
      role="img"
      aria-label={ariaLabel}
      data-trail-animate={isTour ? "" : undefined}
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  );
};
