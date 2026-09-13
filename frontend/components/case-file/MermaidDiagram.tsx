"use client";

// Renders a mermaid source into an inline SVG, trying the run-supplied source first and falling
// back to the generated one if it fails to parse/render. The "document" variant (the printable
// document) reports its settled state to CaseFileUiContext so export buttons know every diagram has
// finished attempting to render; the "tour" variant renders in the portal palette, does not report,
// and hands the mounted SVG to `onReady` so the money trail player can choreograph it.

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { readViewBoxSize, renderMermaidSvg, themeDiagramSource } from "@/lib/caseFile/mermaid";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";

export type DiagramZoom = "fit" | "full";

interface MermaidDiagramProps {
  diagramId: string;
  primarySource: string | null;
  fallbackSource: string | null;
  ariaLabel: string;
  variant?: "document" | "tour";
  zoom?: DiagramZoom;
  onReady?: (svg: SVGSVGElement | null) => void;
}

type State = { status: "pending" } | { status: "ready"; svg: string } | { status: "failed"; error: string };

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({
  diagramId,
  primarySource,
  fallbackSource,
  ariaLabel,
  variant = "document",
  zoom = "fit",
  onReady,
}) => {
  const { reportDiagram } = useCaseFileUi();
  const [state, setState] = useState<State>({ status: "pending" });
  const cancelledRef = useRef(false);
  const svgHostRef = useRef<HTMLDivElement>(null);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
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
          const svg = await renderMermaidSvg(`${diagramId}${idSuffix}-svg`, themeDiagramSource(primary, theme), theme);
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
          const svg = await renderMermaidSvg(`${diagramId}${idSuffix}-svg-fallback`, themeDiagramSource(fallback, theme), theme);
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

  // Size the SVG for the zoom mode. Mermaid emits width="100%" plus an inline max-width, so "100%"
  // must pin the intrinsic viewBox width instead of stretching to the container.
  useLayoutEffect(() => {
    if (state.status !== "ready" || !svgHostRef.current) return;
    const svg = svgHostRef.current.querySelector<SVGSVGElement>("svg");
    if (!svg) return;
    const size = readViewBoxSize(svg);
    if (zoom === "full" && size) {
      svg.style.width = `${size.width}px`;
      svg.style.maxWidth = "none";
      svg.style.maxHeight = "none";
    } else {
      svg.style.width = "100%";
      svg.style.maxWidth = size ? `${size.width}px` : "100%";
      svg.style.maxHeight = isTour ? "70vh" : "";
    }
    svg.style.height = "auto";
  }, [state, zoom, isTour]);

  useLayoutEffect(() => {
    if (state.status !== "ready" || !svgHostRef.current) {
      onReadyRef.current?.(null);
      return;
    }
    onReadyRef.current?.(svgHostRef.current.querySelector<SVGSVGElement>("svg"));
  }, [state]);

  // Stable object: the App Router's React compares dangerouslySetInnerHTML by identity, so a fresh
  // `{ __html }` per render would replace the SVG (and detach the tour player's scene) on every update.
  const innerHtml = useMemo(() => (state.status === "ready" ? { __html: state.svg } : undefined), [state]);

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
  return <div ref={svgHostRef} role="img" aria-label={ariaLabel} dangerouslySetInnerHTML={innerHtml} />;
};
