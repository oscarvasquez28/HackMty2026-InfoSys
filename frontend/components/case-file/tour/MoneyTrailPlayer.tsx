"use client";

// Guided-tour money trail: the Mermaid diagram as a step-by-step player. Each hop draws in order
// with a money packet travelling the edge and a pulse on the receiving entity, synced with the step
// timeline underneath. Follows the OS reduced-motion preference by default (no autoplay, instant
// highlights) with an "Animate" toggle to force motion for the session; stepping always works.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pause, Play, RotateCcw, SkipBack, SkipForward, Sparkles } from "lucide-react";
import type { FindingView } from "@/lib/caseFile/derive";
import { buildTrailScene, type TrailScene } from "@/lib/caseFile/trailScene";
import { formatPesos } from "@/lib/utils";
import { MermaidDiagram, type DiagramZoom } from "@/components/case-file/MermaidDiagram";
import { MoneyTrailTimeline } from "@/components/case-file/MoneyTrailTimeline";
import { useTrailPlayback } from "@/hooks/useTrailPlayback";
import { useTrailMotionPreference } from "@/hooks/useTrailMotionPreference";
import { useRevealOnView } from "@/hooks/useRevealOnView";

interface MoneyTrailPlayerProps {
  finding: FindingView;
  figureNumber: number;
  sourceDescription: string;
  renderedSource: string | null;
}

const iconButton =
  "grid h-11 w-11 place-items-center rounded-md border border-surface-border text-muted transition-colors duration-200 hover:border-brand-500/50 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 active:translate-y-px";

export const MoneyTrailPlayer: React.FC<MoneyTrailPlayerProps> = ({ finding, figureNumber, sourceDescription, renderedSource }) => {
  const trail = finding.trail ?? [];
  const [zoom, setZoom] = useState<DiagramZoom>("fit");
  const [svgEl, setSvgEl] = useState<SVGSVGElement | null>(null);
  const [scene, setScene] = useState<TrailScene | null>(null);
  const { motionAllowed, reducedByOs, forced, setForced } = useTrailMotionPreference();
  const playback = useTrailPlayback(scene, motionAllowed);
  const { ref: revealRef, revealed } = useRevealOnView<HTMLElement>(0.35);
  const autoplayedRef = useRef(false);
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleReady = useCallback((svg: SVGSVGElement | null) => setSvgEl(svg), []);

  // Index the mounted SVG; dispose overlays when it is replaced or the chapter unmounts.
  useEffect(() => {
    if (!svgEl) {
      setScene(null);
      return;
    }
    const next = buildTrailScene(svgEl, finding.trail);
    setScene(next);
    return () => next.dispose();
  }, [svgEl, finding.trail]);

  // Autoplay once, when the diagram is on screen and motion is allowed.
  useEffect(() => {
    if (!scene || !revealed || !motionAllowed || autoplayedRef.current || scene.stops.length === 0) return;
    autoplayedRef.current = true;
    const id = window.setTimeout(() => playback.play(), 350);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, revealed, motionAllowed]);

  // Pause when scrolled away or the tab is hidden, so motion never runs unseen.
  const { pause } = playback;
  useEffect(() => {
    const el = canvasRef.current;
    const onVisibility = () => {
      if (document.hidden) pause();
    };
    document.addEventListener("visibilitychange", onVisibility);
    let observer: IntersectionObserver | null = null;
    if (el && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver((entries) => {
        if (entries.every((entry) => !entry.isIntersecting)) pause();
      });
      observer.observe(el);
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, [pause, scene]);

  // Pointer interaction on the diagram itself: hover an entity to trace its flows, click a hop to select it.
  const { goTo, hoverNode, preview } = playback;
  useEffect(() => {
    if (!scene) return;
    const cleanups: Array<() => void> = [];
    const listen = (el: Element, type: string, fn: () => void) => {
      el.addEventListener(type, fn);
      cleanups.push(() => el.removeEventListener(type, fn));
    };
    scene.nodes.forEach((node) => {
      listen(node.el, "mouseenter", () => hoverNode(node.id));
      listen(node.el, "mouseleave", () => hoverNode(null));
    });
    scene.stops.forEach((stop, i) => {
      for (const el of [stop.edge.path, stop.edge.label]) {
        if (!el) continue;
        listen(el, "mouseenter", () => preview(i));
        listen(el, "mouseleave", () => preview(null));
        listen(el, "click", () => goTo(i));
      }
    });
    return () => cleanups.forEach((fn) => fn());
  }, [scene, goTo, hoverNode, preview]);

  const stopCount = playback.stopCount;
  const shown = playback.previewing ?? playback.current;
  const shownStop = scene && shown !== null ? scene.stops[shown] : null;
  const shownStep = shownStop?.stepIndex !== null && shownStop?.stepIndex !== undefined ? trail[shownStop.stepIndex] : null;
  const disabled = !scene || stopCount === 0;

  const activeStep = scene?.synced && shownStop ? shownStop.stepIndex : null;
  const stopForStep = (stepIndex: number): number | null => {
    if (!scene?.synced) return null;
    const found = scene.stops.findIndex((stop) => stop.stepIndex === stepIndex);
    return found === -1 ? null : found;
  };

  const onCanvasKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;
    const handlers: Record<string, () => void> = {
      ArrowRight: playback.next,
      ArrowLeft: playback.prev,
      Home: () => goTo(0),
      End: () => goTo(stopCount - 1),
      " ": playback.toggle,
      Escape: playback.clear,
    };
    const handler = handlers[event.key];
    if (handler) {
      event.preventDefault();
      handler();
    }
  };

  let caption: string;
  if (disabled) caption = "Preparing the money trail…";
  else if (shownStep) {
    const amount = shownStep.step.amount === null ? "amount n/a" : formatPesos(shownStep.step.amount);
    caption = `Step ${shownStep.stepOrder} of ${trail.length} · ${amount} · ${shownStep.step.date} · ${shownStep.step.exhibit_id || "no exhibit"}`;
  } else if (shown !== null) caption = `Hop ${shown + 1} of ${stopCount}`;
  else if (playback.finished) caption = `Trail complete · ${trail.length} step(s)`;
  else caption = `${trail.length} step(s) · press play or pick a step`;

  return (
    <figure ref={revealRef} className="case-avoid-break overflow-hidden rounded-md border border-paper-border bg-paper-sheet">
      <div data-print="hide" data-export="exclude" className="flex flex-wrap items-center justify-between gap-3 border-b border-paper-border px-4 py-3">
        <p aria-live="polite" className="min-w-0 font-mono text-xs tabular-nums text-paper-ink">
          <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-evidence-held align-middle" aria-hidden="true" />
          {caption}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Playback" className="flex items-center gap-1.5">
            <button type="button" className={iconButton} onClick={playback.prev} disabled={disabled} aria-label="Previous step">
              <SkipBack className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={playback.toggle}
              disabled={disabled}
              aria-label={playback.playing ? "Pause money trail" : "Play money trail"}
              className="grid h-11 w-11 place-items-center rounded-md bg-brand-500 text-brand-ink transition-colors duration-200 hover:bg-brand-300 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40"
            >
              {playback.playing ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
            </button>
            <button type="button" className={iconButton} onClick={playback.next} disabled={disabled} aria-label="Next step">
              <SkipForward className="h-4 w-4" aria-hidden="true" />
            </button>
            <button type="button" className={iconButton} onClick={playback.replay} disabled={disabled} aria-label="Replay from the first step">
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <span className="mx-1 hidden h-6 w-px bg-paper-border sm:block" aria-hidden="true" />
          {reducedByOs && (
            <button
              type="button"
              aria-pressed={forced}
              onClick={() => setForced(!forced)}
              title="Your system asks for reduced motion. Turn this on to animate the money trail anyway."
              className={`flex h-11 items-center gap-2 rounded-md border px-3 text-xs transition-colors duration-200 ${
                forced ? "border-brand-500/60 bg-brand-500/10 text-foreground" : "border-surface-border text-muted hover:text-foreground"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Animate
            </button>
          )}
          <div role="group" aria-label="Diagram zoom" className="flex h-11 items-center rounded-md border border-surface-border p-1">
            {(["fit", "full"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={zoom === mode}
                onClick={() => setZoom(mode)}
                className={`h-full rounded px-2.5 text-[11px] transition-colors duration-200 ${
                  zoom === mode ? "bg-paper-ink text-paper" : "text-paper-muted hover:text-paper-ink"
                }`}
              >
                {mode === "fit" ? "Fit" : "100%"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {stopCount > 1 && (
        <div data-print="hide" data-export="exclude" role="group" aria-label="Trail steps" className="case-scroll flex gap-1.5 overflow-x-auto px-4 pt-3">
          {Array.from({ length: stopCount }, (_, i) => {
            const active = playback.current === i;
            const stepIndex = scene?.stops[i]?.stepIndex;
            const label = stepIndex !== null && stepIndex !== undefined ? stepIndex + 1 : i + 1;
            return (
              <button
                key={i}
                type="button"
                aria-pressed={active}
                aria-label={`Show step ${label}`}
                onClick={() => goTo(i)}
                onMouseEnter={() => preview(i)}
                onMouseLeave={() => preview(null)}
                onFocus={() => preview(i)}
                onBlur={() => preview(null)}
                className={`relative min-h-9 min-w-11 overflow-hidden rounded-md border px-2.5 font-mono text-[11px] tabular-nums transition-colors duration-200 ${
                  active ? "border-brand-500/60 bg-brand-500/10 text-foreground" : "border-surface-border text-muted hover:border-brand-500/40 hover:text-foreground"
                }`}
              >
                {String(label).padStart(2, "0")}
                {active && (
                  <span
                    ref={playback.progressRef}
                    aria-hidden="true"
                    className="absolute inset-x-0 bottom-0 h-0.5 origin-left bg-brand-500"
                    style={{ transform: "scaleX(0)" }}
                  />
                )}
              </button>
            );
          })}
        </div>
      )}

      <div
        ref={canvasRef}
        tabIndex={0}
        onKeyDown={onCanvasKeyDown}
        aria-label={`Money trail diagram for finding ${finding.number}. Use left and right arrows to move between steps and space to play or pause.`}
        className={`trail-canvas p-4 sm:p-6 ${zoom === "full" ? "case-scroll overflow-x-auto" : ""}`}
      >
        <MermaidDiagram
          diagramId={finding.anchorId}
          primarySource={finding.mermaidPrimary}
          fallbackSource={finding.mermaidGenerated}
          ariaLabel={`Money trail diagram for finding ${finding.number}`}
          variant="tour"
          zoom={zoom}
          onReady={handleReady}
        />
      </div>

      <div className="border-t border-paper-border px-4 py-3">
        <figcaption className="font-mono text-[11px] text-paper-muted">
          Figure {figureNumber}. Money trail — {trail.length} step(s). Diagram source: {sourceDescription}.
          {scene && !scene.synced && stopCount > 0 && " Steps in this diagram could not be matched to the timeline one-to-one."}
        </figcaption>
        <details data-print="hide" data-export="exclude" className="mt-2 text-xs text-paper-muted">
          <summary className="cursor-pointer">View diagram source</summary>
          <pre className="mt-1 overflow-x-auto font-mono text-xs">{renderedSource ?? finding.mermaidPrimary ?? finding.mermaidGenerated}</pre>
        </details>
      </div>

      <div className="border-t border-paper-border px-4 pt-4">
        <MoneyTrailTimeline
          trail={trail}
          activeStep={activeStep}
          onStepPreview={
            scene?.synced
              ? (index) => preview(index === null ? null : stopForStep(index))
              : undefined
          }
          onStepSelect={
            scene?.synced
              ? (index) => {
                  const stop = stopForStep(index);
                  if (stop !== null) goTo(stop);
                }
              : undefined
          }
        />
      </div>
    </figure>
  );
};
