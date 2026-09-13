// Indexes a rendered Mermaid money-trail SVG so the tour's player can choreograph it: which path and
// label belong to which edge, which nodes an edge connects, and which money_trail step each edge
// depicts. Pure DOM reading plus one overlay group; no React. Mermaid 11 markup assumed:
//   <g class="node default flagged" id="{svgId}-flowchart-{nodeId}-{n}" transform=...>
//   <path class="... flowchart-link" data-id="L_{from}_{to}_{n}" d=...>
//   <g class="edgeLabel"><g class="label" data-id="L_{from}_{to}_{n}">...</g></g>

import type { TrailStepView } from "@/lib/caseFile/derive";

const SVG_NS = "http://www.w3.org/2000/svg";

export interface TrailSceneNode {
  id: string;
  el: SVGGElement;
  flagged: boolean;
}

export interface TrailSceneEdge {
  index: number;
  path: SVGPathElement;
  label: SVGGElement | null;
  from: string | null;
  to: string | null;
  length: number;
}

/** One playback stop: a money_trail step (when synced) or a raw edge in definition order. */
export interface TrailSceneStop {
  edge: TrailSceneEdge;
  stepIndex: number | null;
}

export interface TrailScene {
  svg: SVGSVGElement;
  overlay: SVGGElement;
  nodes: Map<string, TrailSceneNode>;
  edges: TrailSceneEdge[];
  stops: TrailSceneStop[];
  /** True when every stop maps to exactly one money_trail step, so the timeline can follow along. */
  synced: boolean;
  /** Removes everything the scene added to the SVG. */
  dispose: () => void;
}

const STEP_RE = /\bStep\s+(\d+)\b/i;

function nodeIdFromElement(el: Element, svgId: string): string | null {
  const prefix = `${svgId}-flowchart-`;
  if (!el.id.startsWith(prefix)) return null;
  return el.id.slice(prefix.length).replace(/-\d+$/, "");
}

/** Splits "L_{from}_{to}_{n}" against known node ids, tolerating underscores inside ids. */
function endpointsFromDataId(dataId: string | null, nodeIds: Set<string>): { from: string | null; to: string | null } {
  if (!dataId) return { from: null, to: null };
  const core = dataId.replace(/^L_/, "").replace(/_\d+$/, "");
  const parts = core.split("_");
  for (let i = 1; i < parts.length; i++) {
    const from = parts.slice(0, i).join("_");
    const to = parts.slice(i).join("_");
    if (nodeIds.has(from) && nodeIds.has(to)) return { from, to };
  }
  return { from: null, to: null };
}

function safeLength(path: SVGPathElement): number {
  try {
    return path.getTotalLength();
  } catch {
    return 0;
  }
}

export function buildTrailScene(svg: SVGSVGElement, trail: TrailStepView[] | null): TrailScene {
  const nodes = new Map<string, TrailSceneNode>();
  svg.querySelectorAll<SVGGElement>("g.node").forEach((el) => {
    const id = nodeIdFromElement(el, svg.id);
    if (id && !nodes.has(id)) nodes.set(id, { id, el, flagged: el.classList.contains("flagged") });
  });
  const nodeIds = new Set(nodes.keys());

  const labelsByDataId = new Map<string, SVGGElement>();
  svg.querySelectorAll<SVGGElement>("g.edgeLabel").forEach((edgeLabel) => {
    const dataId = edgeLabel.querySelector("[data-id]")?.getAttribute("data-id");
    if (dataId && !labelsByDataId.has(dataId)) labelsByDataId.set(dataId, edgeLabel);
  });

  const edges: TrailSceneEdge[] = Array.from(svg.querySelectorAll<SVGPathElement>("path.flowchart-link")).map((path, index) => {
    const dataId = path.getAttribute("data-id");
    return {
      index,
      path,
      label: dataId ? labelsByDataId.get(dataId) ?? null : null,
      ...endpointsFromDataId(dataId, nodeIds),
      length: safeLength(path),
    };
  });

  // Map edges to steps: explicit "Step N" in the label wins; otherwise 1:1 by definition order.
  const stepCount = trail?.length ?? 0;
  let stops: TrailSceneStop[] = edges.map((edge) => ({ edge, stepIndex: null }));
  let synced = false;
  if (stepCount > 0 && edges.length > 0) {
    const parsed = edges.map((edge) => {
      const match = edge.label?.textContent?.match(STEP_RE);
      const n = match ? Number(match[1]) - 1 : NaN;
      return Number.isInteger(n) && n >= 0 && n < stepCount ? n : null;
    });
    const uniqueParsed = new Set(parsed.filter((n): n is number => n !== null));
    if (parsed.every((n) => n !== null) && uniqueParsed.size === edges.length) {
      stops = edges.map((edge, i) => ({ edge, stepIndex: parsed[i] })).sort((a, b) => a.stepIndex! - b.stepIndex!);
      synced = true;
    } else if (edges.length === stepCount) {
      stops = edges.map((edge, i) => ({ edge, stepIndex: i }));
      synced = true;
    }
  }

  // Overlay sits in the same coordinate system as the edges, above nodes, so packets read on top.
  const layerParent = (svg.querySelector("g.edgePaths")?.parentNode as SVGGElement | null) ?? svg;
  const overlay = document.createElementNS(SVG_NS, "g") as SVGGElement;
  overlay.setAttribute("class", "trail-overlay");
  overlay.setAttribute("aria-hidden", "true");
  layerParent.appendChild(overlay);

  return {
    svg,
    overlay,
    nodes,
    edges,
    stops,
    synced,
    dispose: () => {
      overlay.remove();
      svg.querySelectorAll(".trail-ring").forEach((el) => el.remove());
      svg.querySelectorAll("[data-trail-state]").forEach((el) => el.removeAttribute("data-trail-state"));
      edges.forEach(({ path, label }) => {
        path.style.removeProperty("stroke-dasharray");
        path.style.removeProperty("stroke-dashoffset");
        path.style.removeProperty("marker-end");
        label?.style.removeProperty("opacity");
      });
    },
  };
}

export function createSvgElement<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>): SVGElementTagNameMap[K] {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}
