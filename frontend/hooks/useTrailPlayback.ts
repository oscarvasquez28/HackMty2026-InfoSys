"use client";

// Drives the money trail player over an indexed Mermaid scene. Every visual is a pure function of
// (stop, elapsed ms) rendered from one requestAnimationFrame loop, so pause/resume, jumping to a
// step mid-animation, and toggling motion always land on a correct final state without depending on
// animationend/transitionend. JS-driven motion is unaffected by the global reduced-motion CSS
// override; whether to animate at all is decided by `motionAllowed`.

import { useCallback, useEffect, useRef, useState } from "react";
import { createSvgElement, type TrailScene, type TrailSceneStop } from "@/lib/caseFile/trailScene";

/** Choreography per stop (ms). */
const DRAW_MS = 820;
const LABEL_DELAY_MS = 380;
const LABEL_FADE_MS = 280;
const ARRIVE_MS = 560;
const GAP_MS = 380;
const STOP_MS = DRAW_MS + ARRIVE_MS + GAP_MS;
/** Discrete advance interval when motion is not allowed. */
const STATIC_STOP_MS = 1900;

type TrailState = "pending" | "active" | "dim" | null;

export interface UseTrailPlaybackReturn {
  stopCount: number;
  /** Stop currently highlighted: the playing stop, else the selected one; null in overview. */
  current: number | null;
  /** Stop shown while hovering a step pill / timeline row (display only). */
  previewing: number | null;
  playing: boolean;
  finished: boolean;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  replay: () => void;
  goTo: (stop: number) => void;
  next: () => void;
  prev: () => void;
  clear: () => void;
  preview: (stop: number | null) => void;
  hoverNode: (nodeId: string | null) => void;
  /** Ref callback for an element whose scaleX follows the current stop's progress. */
  progressRef: (el: HTMLElement | null) => void;
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 4);
const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);

function setState(el: Element | null | undefined, state: TrailState) {
  if (!el) return;
  if (state) el.setAttribute("data-trail-state", state);
  else el.removeAttribute("data-trail-state");
}

function resetEdgeInline(stop: TrailSceneStop) {
  const { path, label } = stop.edge;
  path.style.removeProperty("stroke-dasharray");
  path.style.removeProperty("stroke-dashoffset");
  path.style.removeProperty("marker-end");
  label?.style.removeProperty("opacity");
}

export function useTrailPlayback(scene: TrailScene | null, motionAllowed: boolean): UseTrailPlaybackReturn {
  const stopCount = scene?.stops.length ?? 0;
  const [current, setCurrent] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [finished, setFinished] = useState(false);
  const [previewing, setPreviewing] = useState<number | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const elapsedRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);
  const currentRef = useRef<number | null>(null);
  const playingRef = useRef(false);
  const motionRef = useRef(motionAllowed);
  const progressElRef = useRef<HTMLElement | null>(null);
  const fxRef = useRef<{ packet: SVGGElement; ring: SVGRectElement | null; flow: SVGPathElement; flowAnim: Animation | null } | null>(null);

  motionRef.current = motionAllowed;
  currentRef.current = current;
  playingRef.current = playing;

  // ---- effects layer (packet, arrival ring, active-edge flow) -------------------------------------
  const ensureFx = useCallback(() => {
    if (!scene) return null;
    if (fxRef.current && fxRef.current.packet.isConnected) return fxRef.current;
    const packet = createSvgElement("g", { class: "trail-packet-group", opacity: 0 });
    packet.appendChild(createSvgElement("circle", { class: "trail-packet-halo", r: 11 }));
    packet.appendChild(createSvgElement("circle", { class: "trail-packet", r: 4.5 }));
    const flow = createSvgElement("path", { class: "trail-flow", d: "", opacity: 0 });
    scene.overlay.appendChild(flow);
    scene.overlay.appendChild(packet);
    fxRef.current = { packet, ring: null, flow, flowAnim: null };
    return fxRef.current;
  }, [scene]);

  const clearRing = useCallback(() => {
    fxRef.current?.ring?.remove();
    if (fxRef.current) fxRef.current.ring = null;
  }, []);

  const stopFlow = useCallback(() => {
    const fx = fxRef.current;
    if (!fx) return;
    fx.flowAnim?.cancel();
    fx.flowAnim = null;
    fx.flow.setAttribute("opacity", "0");
  }, []);

  const startFlow = useCallback(
    (stop: TrailSceneStop) => {
      const fx = ensureFx();
      if (!fx || !motionRef.current || typeof fx.flow.animate !== "function") return;
      stopFlow();
      fx.flow.setAttribute("d", stop.edge.path.getAttribute("d") ?? "");
      fx.flow.setAttribute("opacity", "0.9");
      // A few passes of "money moving" along the selected edge — not a perpetual decorative loop.
      fx.flowAnim = fx.flow.animate([{ strokeDashoffset: 24 }, { strokeDashoffset: 0 }], { duration: 900, iterations: 4, easing: "linear" });
      fx.flowAnim.onfinish = () => fx.flow.setAttribute("opacity", "0");
    },
    [ensureFx, stopFlow]
  );

  // ---- state painting ---------------------------------------------------------------------------
  /** Paints data-trail-state for every edge/label/node given the focus stop and playback mode. */
  const paintStates = useCallback(
    (focus: number | null, mode: "playing" | "focus" | "overview", node: string | null = null) => {
      if (!scene) return;
      const { stops, nodes } = scene;
      const activeNodes = new Set<string>();

      stops.forEach((stop, i) => {
        let state: TrailState = null;
        if (mode === "playing" && focus !== null) state = i < focus ? null : i === focus ? "active" : "pending";
        else if (mode === "focus" && focus !== null) state = i === focus ? "active" : "dim";
        else if (node) state = stop.edge.from === node || stop.edge.to === node ? "active" : "dim";
        setState(stop.edge.path, state);
        setState(stop.edge.label, state);
        if (state === "active") {
          if (stop.edge.from) activeNodes.add(stop.edge.from);
          if (stop.edge.to) activeNodes.add(stop.edge.to);
        }
      });

      const dimOthers = mode === "focus" || (mode === "overview" && node !== null);
      nodes.forEach((n) => {
        if (activeNodes.has(n.id) || n.id === node) setState(n.el, mode === "playing" ? null : "active");
        else setState(n.el, dimOthers ? "dim" : null);
      });
    },
    [scene]
  );

  /** Renders the in-flight visuals of `stopIndex` at `elapsed` ms (motion mode). */
  const renderFrame = useCallback(
    (stopIndex: number, elapsed: number) => {
      if (!scene) return;
      const stop = scene.stops[stopIndex];
      if (!stop) return;
      const fx = ensureFx();
      const { path, label, length, to } = stop.edge;
      const animate = motionRef.current && length > 0;

      const d = animate ? clamp01(elapsed / DRAW_MS) : 1;
      const e = easeOut(d);
      if (animate && d < 1) {
        path.style.strokeDasharray = `${length} ${length}`;
        path.style.strokeDashoffset = String(length * (1 - e));
        path.style.markerEnd = "none";
      } else {
        path.style.removeProperty("stroke-dasharray");
        path.style.removeProperty("stroke-dashoffset");
        path.style.removeProperty("marker-end");
      }

      if (label) {
        const labelT = animate ? clamp01((elapsed - LABEL_DELAY_MS) / LABEL_FADE_MS) : 1;
        if (labelT < 1) label.style.opacity = String(labelT);
        else label.style.removeProperty("opacity");
      }

      if (fx) {
        if (animate && elapsed < DRAW_MS + 240) {
          const point = path.getPointAtLength(length * e);
          const fade = d < 1 ? 1 : 1 - clamp01((elapsed - DRAW_MS) / 240);
          fx.packet.setAttribute("transform", `translate(${point.x} ${point.y})`);
          fx.packet.setAttribute("opacity", String(fade));
        } else {
          fx.packet.setAttribute("opacity", "0");
        }

        const target = to ? scene.nodes.get(to) : undefined;
        const ringT = (elapsed - DRAW_MS + 60) / ARRIVE_MS;
        if (animate && target && ringT > 0 && ringT < 1) {
          if (!fx.ring || fx.ring.parentNode !== target.el) {
            clearRing();
            const shape = target.el.querySelector<SVGGraphicsElement>("rect, polygon, circle, path");
            const box = (shape ?? target.el).getBBox();
            fx.ring = createSvgElement("rect", {
              class: "trail-ring",
              x: box.x,
              y: box.y,
              width: box.width,
              height: box.height,
              rx: 4,
            });
            if (target.flagged) fx.ring.setAttribute("data-flagged", "");
            target.el.appendChild(fx.ring);
          }
          const r = easeOut(ringT);
          fx.ring.style.transform = `scale(${1 + 0.14 * r})`;
          fx.ring.style.opacity = String(0.95 * (1 - ringT));
        } else {
          clearRing();
        }
      }

      if (progressElRef.current) {
        const total = motionRef.current ? STOP_MS : STATIC_STOP_MS;
        progressElRef.current.style.transform = `scaleX(${clamp01(elapsed / total)})`;
      }
    },
    [scene, ensureFx, clearRing]
  );

  const cancelLoop = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    lastTsRef.current = null;
  }, []);

  const settleStop = useCallback(
    (stopIndex: number | null) => {
      if (!scene || stopIndex === null) return;
      const stop = scene.stops[stopIndex];
      if (!stop) return;
      resetEdgeInline(stop);
      const fx = fxRef.current;
      if (fx) fx.packet.setAttribute("opacity", "0");
      clearRing();
    },
    [scene, clearRing]
  );

  // ---- loop -------------------------------------------------------------------------------------
  const tick = useCallback(
    (ts: number) => {
      if (!scene || !playingRef.current) return;
      const last = lastTsRef.current ?? ts;
      lastTsRef.current = ts;
      elapsedRef.current += Math.min(ts - last, 64);
      const index = currentRef.current ?? 0;
      const total = motionRef.current ? STOP_MS : STATIC_STOP_MS;

      if (elapsedRef.current >= total) {
        settleStop(index);
        const nextIndex = index + 1;
        if (nextIndex >= scene.stops.length) {
          // Finished: return to the full overview.
          playingRef.current = false;
          currentRef.current = null;
          elapsedRef.current = 0;
          setPlaying(false);
          setCurrent(null);
          setFinished(true);
          paintStates(null, "overview");
          if (progressElRef.current) progressElRef.current.style.transform = "scaleX(0)";
          rafRef.current = null;
          return;
        }
        elapsedRef.current = 0;
        currentRef.current = nextIndex;
        setCurrent(nextIndex);
        paintStates(nextIndex, "playing");
      }
      renderFrame(currentRef.current ?? 0, elapsedRef.current);
      rafRef.current = requestAnimationFrame(tick);
    },
    [scene, paintStates, renderFrame, settleStop]
  );

  const startLoop = useCallback(() => {
    cancelLoop();
    rafRef.current = requestAnimationFrame(tick);
  }, [cancelLoop, tick]);

  // ---- actions ----------------------------------------------------------------------------------
  const play = useCallback(() => {
    if (!scene || scene.stops.length === 0) return;
    stopFlow();
    // Resume the paused/selected stop, or start over from the first one.
    let index = currentRef.current;
    if (index === null) {
      index = 0;
      elapsedRef.current = 0;
    }
    setFinished(false);
    currentRef.current = index;
    playingRef.current = true;
    setCurrent(index);
    setPlaying(true);
    paintStates(index, "playing");
    renderFrame(index, elapsedRef.current);
    startLoop();
  }, [scene, paintStates, renderFrame, startLoop, stopFlow]);

  const pause = useCallback(() => {
    if (!playingRef.current) return;
    playingRef.current = false;
    cancelLoop();
    setPlaying(false);
    const index = currentRef.current;
    // Paused mid-step: freeze the frame; the reader can resume or jump.
    if (index !== null) paintStates(index, "playing");
  }, [cancelLoop, paintStates]);

  const goTo = useCallback(
    (stopIndex: number) => {
      if (!scene || scene.stops.length === 0) return;
      const index = Math.max(0, Math.min(scene.stops.length - 1, stopIndex));
      playingRef.current = false;
      cancelLoop();
      settleStop(currentRef.current);
      scene.stops.forEach(resetEdgeInline);
      elapsedRef.current = 0;
      currentRef.current = index;
      setPlaying(false);
      setFinished(false);
      setCurrent(index);
      paintStates(index, "focus");
      // A short replay of the selected hop: draw + packet + arrival, then a few flow passes.
      if (motionRef.current) {
        let start: number | null = null;
        const stepTick = (ts: number) => {
          if (playingRef.current || currentRef.current !== index) return;
          start = start ?? ts;
          const elapsed = ts - start;
          renderFrame(index, elapsed);
          if (elapsed < DRAW_MS + ARRIVE_MS) rafRef.current = requestAnimationFrame(stepTick);
          else {
            rafRef.current = null;
            settleStop(index);
            startFlow(scene.stops[index]);
          }
        };
        rafRef.current = requestAnimationFrame(stepTick);
      } else {
        renderFrame(index, STOP_MS);
      }
      if (progressElRef.current) progressElRef.current.style.transform = "scaleX(1)";
    },
    [scene, cancelLoop, settleStop, paintStates, renderFrame, startFlow]
  );

  const clear = useCallback(() => {
    playingRef.current = false;
    cancelLoop();
    settleStop(currentRef.current);
    scene?.stops.forEach(resetEdgeInline);
    stopFlow();
    elapsedRef.current = 0;
    currentRef.current = null;
    setPlaying(false);
    setCurrent(null);
    paintStates(null, "overview");
    if (progressElRef.current) progressElRef.current.style.transform = "scaleX(0)";
  }, [scene, cancelLoop, settleStop, stopFlow, paintStates]);

  const replay = useCallback(() => {
    clear();
    if (!scene || scene.stops.length === 0) return;
    currentRef.current = 0;
    elapsedRef.current = 0;
    playingRef.current = true;
    setFinished(false);
    setCurrent(0);
    setPlaying(true);
    paintStates(0, "playing");
    renderFrame(0, 0);
    startLoop();
  }, [clear, scene, paintStates, renderFrame, startLoop]);

  const toggle = useCallback(() => (playingRef.current ? pause() : play()), [pause, play]);
  const next = useCallback(() => goTo((currentRef.current ?? -1) + 1), [goTo]);
  const prev = useCallback(() => goTo((currentRef.current ?? stopCount) - 1), [goTo, stopCount]);
  const preview = useCallback((stop: number | null) => setPreviewing(stop), []);
  const hoverNode = useCallback((nodeId: string | null) => setHoveredNode(nodeId), []);
  const progressRef = useCallback((el: HTMLElement | null) => {
    progressElRef.current = el;
  }, []);

  // Hover previews repaint over the committed state without touching playback.
  useEffect(() => {
    if (!scene || playingRef.current) return;
    if (previewing !== null) paintStates(previewing, "focus");
    else if (hoveredNode !== null && current === null) paintStates(null, "overview", hoveredNode);
    else if (current !== null) paintStates(current, "focus");
    else paintStates(null, "overview");
  }, [scene, previewing, hoveredNode, current, paintStates]);

  // Switching motion off mid-play settles the in-flight frame immediately.
  useEffect(() => {
    if (motionAllowed || !scene) return;
    stopFlow();
    const index = currentRef.current;
    if (index !== null) renderFrame(index, STOP_MS);
  }, [motionAllowed, scene, renderFrame, stopFlow]);

  // New scene (re-render, zoom-independent): reset playback and tear down effects.
  useEffect(() => {
    playingRef.current = false;
    currentRef.current = null;
    elapsedRef.current = 0;
    setPlaying(false);
    setCurrent(null);
    setFinished(false);
    setPreviewing(null);
    setHoveredNode(null);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      fxRef.current?.flowAnim?.cancel();
      fxRef.current = null;
    };
  }, [scene]);

  return { stopCount, current, previewing, playing, finished, play, pause, toggle, replay, goTo, next, prev, clear, preview, hoverNode, progressRef };
}
