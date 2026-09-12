// Mermaid loading, rendering and money-trail diagram generation for the case file viewer.
// mermaid is not safe to call concurrently and React 18 StrictMode double-invokes effects, so every
// render is serialized through a single queue. Never call this module from a server component.

import type { MoneyTrailStep } from "@/types/caseFile";
import { formatPesos } from "@/lib/utils";

type MermaidApi = typeof import("mermaid").default;

let mermaidPromise: Promise<MermaidApi> | null = null;

export function loadMermaid(): Promise<MermaidApi> {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((mod) => {
      const mermaid = mod.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        deterministicIds: true,
        deterministicIDSeed: "polar-case-file",
        flowchart: { htmlLabels: false, curve: "basis", useMaxWidth: true },
        themeVariables: {
          fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
          fontSize: "13px",
          primaryColor: "#FFFFFF",
          primaryTextColor: "#161B22",
          primaryBorderColor: "#161B22",
          lineColor: "#3A4250",
          secondaryColor: "#F2EFE8",
          tertiaryColor: "#FBFAF7",
          edgeLabelBackground: "#FBFAF7",
        },
      });
      return mermaid;
    });
  }
  return mermaidPromise;
}

let renderQueue: Promise<unknown> = Promise.resolve();

export function renderMermaidSvg(renderId: string, source: string): Promise<string> {
  const task = renderQueue.then(async () => {
    const mermaid = await loadMermaid();
    try {
      await mermaid.parse(source);
      const { svg } = await mermaid.render(renderId, source);
      return svg;
    } finally {
      // mermaid leaves a temporary detached node behind on both success and failure.
      document.getElementById(`d${renderId}`)?.remove();
    }
  });
  renderQueue = task.catch(() => undefined);
  return task;
}

function escapeMermaidLabel(value: string): string {
  return value
    .replace(/"/g, "#quot;")
    .replace(/</g, "#lt;")
    .replace(/>/g, "#gt;")
    .replace(/\|/g, "/")
    .replace(/\r?\n/g, " ");
}

/** Builds a flowchart LR from ordered money_trail steps when the run supplied no mermaid_source. */
export function buildMermaidFromTrail(
  steps: MoneyTrailStep[],
  entityNames: Record<string, string>,
  findingEntities: string[]
): string {
  const lines: string[] = ["flowchart LR"];
  const nodeIds = new Map<string, string>();
  let counter = 0;

  const nodeIdFor = (account: string): string => {
    let id = nodeIds.get(account);
    if (!id) {
      counter += 1;
      id = `N${counter}`;
      nodeIds.set(account, id);
      const name = entityNames[account];
      const label = name ? `${name} · ${account}` : account;
      lines.push(`  ${id}["${escapeMermaidLabel(label)}"]`);
    }
    return id;
  };

  for (const step of steps) {
    nodeIdFor(step.from);
    nodeIdFor(step.to);
  }

  steps.forEach((step, index) => {
    const fromId = nodeIdFor(step.from);
    const toId = nodeIdFor(step.to);
    const amountLabel = step.amount === null ? "amount n/a" : formatPesos(step.amount);
    const label = `Step ${index + 1} · ${amountLabel} · ${step.date} · ${step.exhibit_id}`;
    lines.push(`  ${fromId} -->|"${escapeMermaidLabel(label)}"| ${toId}`);
  });

  const flaggedIds = new Set<string>();
  for (const entity of findingEntities) {
    const colonIndex = entity.indexOf(":");
    const rest = colonIndex === -1 ? entity : entity.slice(colonIndex + 1);
    for (const [account, id] of Array.from(nodeIds.entries())) {
      if (account === entity || account === rest) flaggedIds.add(id);
    }
  }
  if (flaggedIds.size > 0) {
    lines.push("  classDef flagged fill:#F6E1DF,stroke:#8E1B1F,stroke-width:2px,color:#161B22");
    lines.push(`  class ${Array.from(flaggedIds).join(",")} flagged`);
  }

  return lines.join("\n");
}
