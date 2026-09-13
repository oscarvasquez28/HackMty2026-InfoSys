// Compiles a CaseFileView into a standalone Markdown document with the money trail embedded as a
// ```mermaid fence, per case_file_structure.md's "any format a judge can open and read" rule.
// Deterministic: same view + same renderedSources -> byte-identical output.

import type { CaseFileView, FindingView } from "@/lib/caseFile/derive";
import { formatPesos, formatSeconds, formatInteger } from "@/lib/utils";
import { CLOSED_BY_LABELS, SCHEME_LABELS } from "@/lib/caseFile/constants";

export interface BuildMarkdownOptions {
  isSample: boolean;
  renderedSources: Record<string, string | null>;
  estateChecked: boolean;
}

function escapeCell(value: string): string {
  return value.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}

function orNotReported(value: string | number | null): string {
  return value === null || value === "" ? "Not reported" : String(value);
}

function deterministicText(deterministic: boolean | null, seed: number | null): string {
  if (deterministic === true) return `Yes — reproducible with seed ${seed ?? "unknown"}`;
  if (deterministic === false) return "No";
  return "Not reported";
}

function buildHeaderSection(view: CaseFileView): string[] {
  const { document } = view;
  const header = document.header;
  const meta = document.run_metadata;
  const company = header?.company || null;
  const lines: string[] = [];

  lines.push(`# Forensic Case File — ${company ?? "Company not reported"}`);
  lines.push("");
  lines.push("## 1. Header");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|---|---|");
  const companyCell = company
    ? `${escapeCell(company)}${header?.company_rfc ? ` (RFC ${escapeCell(header.company_rfc)})` : ""}`
    : "Not reported";
  lines.push(`| Company | ${companyCell} |`);
  const period = header?.audit_period;
  const periodCell = period ? `${orNotReported(period.start)} to ${orNotReported(period.end)}` : "Not reported";
  lines.push(`| Audit period | ${periodCell} |`);
  lines.push(`| Estate seed | ${orNotReported(document.seed)} |`);
  const estSuffix = meta.llm_usage_estimated ? " (est.)" : "";
  lines.push(`| LLM calls | ${meta.llm_calls === null ? "Not reported" : `${formatInteger(meta.llm_calls)}${estSuffix}`} |`);
  lines.push(`| LLM tokens | ${meta.llm_tokens === null ? "Not reported" : `${formatInteger(meta.llm_tokens)}${estSuffix}`} |`);
  lines.push(`| MXN cost | ${meta.mxn_cost === null ? "Not reported" : `${formatPesos(meta.mxn_cost)}${estSuffix}`} |`);
  lines.push(`| Wall-clock seconds | ${meta.wall_clock_seconds === null ? "Not reported" : formatSeconds(meta.wall_clock_seconds)} |`);
  lines.push(`| Deterministic | ${deterministicText(meta.deterministic, document.seed)} |`);
  const roleKeys = Object.keys(meta.cost_by_role).sort();
  if (roleKeys.length > 0) {
    const costByRole = roleKeys.map((key) => `${key} ${formatPesos(meta.cost_by_role[key])}`).join(" · ");
    lines.push(`| Cost by role | ${escapeCell(costByRole)} |`);
  }
  lines.push("");
  return lines;
}

function buildExecutiveSummarySection(view: CaseFileView): string[] {
  const { summary } = view;
  return [
    "## 2. Executive summary",
    "",
    summary.narrative,
    "",
    "| | |",
    "|---|---|",
    `| Findings | ${summary.findingsCount} (${summary.proven} proven, ${summary.probable} probable) |`,
    `| Total exposure | ${formatPesos(summary.totalExposure)} |`,
    `| Leads investigated and closed | ${summary.closedLeadsCount} |`,
    "",
  ];
}

function buildFindingSection(finding: FindingView, options: BuildMarkdownOptions): string[] {
  const lines: string[] = [];
  const f = finding.finding;
  const schemeLabel = finding.schemeType ? SCHEME_LABELS[finding.schemeType] : f.scheme_type || "Unknown";
  const entityIds = f.entities.join(", ");
  lines.push(`### Finding ${finding.number} — ${entityIds} · ${schemeLabel} (\`${f.scheme_type}\`)`);
  lines.push("");

  const namedEntities = finding.entities.filter((e) => e.name);
  if (namedEntities.length > 0) {
    lines.push(`**Entities:** ${namedEntities.map((e) => `${e.id} — ${e.name}`).join("; ")}`);
    lines.push("");
  }

  lines.push(`**Rule broken:** ${finding.rule.title}`);
  if (finding.rule.citation) {
    lines.push(`> ${finding.rule.citation}`);
  }
  if (f.rule_detail) {
    lines.push(`Cited as: \`${finding.rule.citedAs}\``);
  }
  lines.push("");

  lines.push(`**Amount:** ${f.peso_amount === null ? "Not reported" : formatPesos(f.peso_amount)} · **Confidence:** ${f.confidence || "not reported"}`);
  lines.push("");

  lines.push("#### What happened");
  lines.push("");
  lines.push(f.narrative);
  lines.push("");

  lines.push("#### Money trail");
  lines.push("");
  const renderedSource = options.renderedSources[finding.anchorId] ?? finding.mermaidPrimary ?? finding.mermaidGenerated;
  if (renderedSource) {
    lines.push("```mermaid");
    lines.push(renderedSource);
    lines.push("```");
    lines.push("");
  }
  if (finding.trail === null) {
    lines.push("No money trail was supplied for this finding.");
    lines.push("");
  } else {
    lines.push("| Step | Date | From | To | Amount | Exhibit |");
    lines.push("|---|---|---|---|---|---|");
    finding.trail.forEach((step) => {
      const amountCell = step.step.amount === null ? "Not reported" : formatPesos(step.step.amount);
      lines.push(
        `| ${step.stepOrder} | ${escapeCell(step.step.date)} | ${escapeCell(step.step.from)} | ${escapeCell(step.step.to)} | ${amountCell} | ${escapeCell(step.step.exhibit_id)} |`
      );
    });
    lines.push("");
  }

  lines.push("#### Exhibits");
  lines.push("");
  lines.push("| Exhibit ID | Source table | Record ID | What it proves |");
  lines.push("|---|---|---|---|");
  f.exhibits.forEach((exhibit) => {
    lines.push(
      `| ${escapeCell(exhibit.exhibit_id)} | ${escapeCell(exhibit.source_table)} | ${escapeCell(exhibit.record_id)} | ${escapeCell(exhibit.note)} |`
    );
  });
  lines.push("");

  lines.push("#### Reconciliation");
  lines.push("");
  const rec = finding.reconciliation;
  lines.push("| | Amount |");
  lines.push("|---|---|");
  lines.push(`| Claimed amount | ${rec.claimed === null ? "Not reported" : formatPesos(rec.claimed)} |`);
  const matchedLabel = rec.matchedTable
    ? `Sum of cited exhibits (best-matching table: \`${rec.matchedTable}\`)`
    : "Sum of cited exhibits";
  lines.push(`| ${matchedLabel} | ${rec.matchedSubtotal === null ? "Not reported" : formatPesos(rec.matchedSubtotal)} |`);
  const varianceCell =
    rec.delta === null || rec.variancePct === null
      ? "Not applicable"
      : `${formatPesos(rec.delta)} (${rec.variancePct.toFixed(2)}%)`;
  lines.push(`| Variance (Δ) | ${varianceCell} |`);
  lines.push("");
  const statusText =
    rec.status === "reconciled"
      ? "RECONCILED (≤ 2% variance)"
      : rec.status === "not_reconciled"
      ? "NOT RECONCILED — variance exceeds 2%"
      : "NOT VERIFIABLE — no exhibit amounts supplied";
  lines.push(`**Status:** ${statusText}`);
  if (rec.perTable.length > 0) {
    lines.push(`Per-table subtotals: ${rec.perTable.map((t) => `\`${t.table}\` ${formatPesos(t.subtotal)}`).join(" · ")}`);
  }
  if (options.estateChecked) {
    lines.push("Amounts verified against the loaded data estate.");
  }
  lines.push("");

  lines.push("#### Adversarial review");
  lines.push("");
  if (f.adversarial_review) {
    lines.push(`**Defense position (challenger · ${f.adversarial_review.reviewer_agent_role}):** ${f.adversarial_review.challenger_argument}`);
    lines.push(`**Why the finding held:** ${f.adversarial_review.why_finding_held}`);
  } else {
    lines.push("No adversarial review was recorded for this finding.");
  }
  lines.push("");

  return lines;
}

function buildFindingsSection(view: CaseFileView, options: BuildMarkdownOptions): string[] {
  const lines: string[] = ["## 3. Findings", ""];
  if (view.findings.length === 0) {
    lines.push("No findings were validated in this run.");
    lines.push("");
    return lines;
  }
  for (const finding of view.findings) {
    lines.push(...buildFindingSection(finding, options));
  }
  return lines;
}

function buildLeadsSection(view: CaseFileView): string[] {
  const lines: string[] = ["## 4. Leads investigated and closed", ""];
  if (view.leads.length === 0) {
    lines.push("No leads were closed in this run.");
    lines.push("");
    return lines;
  }
  lines.push("| Entity | Signal | Reason closed | Tools called | Closed by |");
  lines.push("|---|---|---|---|---|");
  for (const leadView of view.leads) {
    const { lead } = leadView;
    const entityCell = leadView.name ? `${lead.entity} (${leadView.name})` : lead.entity;
    const tools = lead.tool_calls_made ?? [];
    const toolsCell = `${tools.length}: ${tools.length > 0 ? tools.join(", ") : "none"}`;
    const closedByCell = leadView.closedBy
      ? CLOSED_BY_LABELS[leadView.closedBy]
      : lead.closed_by
      ? lead.closed_by
      : "Not recorded";
    lines.push(
      `| ${escapeCell(entityCell)} | ${escapeCell(lead.signal)} | ${escapeCell(lead.reason)} | ${escapeCell(toolsCell)} | ${escapeCell(closedByCell)} |`
    );
  }
  lines.push("");
  return lines;
}

function buildMethodSection(view: CaseFileView): string[] {
  const method = view.document.method_and_limits;
  const lines: string[] = ["## 5. Method and limits", ""];

  lines.push("### Architecture");
  lines.push("");
  lines.push(method?.architecture_summary || "Not provided by this run.");
  lines.push("");

  lines.push("### Out of scope for this run");
  lines.push("");
  if (method && method.out_of_scope.length > 0) {
    method.out_of_scope.forEach((item) => lines.push(`- ${item}`));
  } else {
    lines.push("Not provided by this run.");
  }
  lines.push("");

  lines.push("### What this system cannot detect");
  lines.push("");
  if (method && method.undetectable_fraud_types.length > 0) {
    method.undetectable_fraud_types.forEach((item) => lines.push(`- ${item}`));
  } else {
    lines.push("Not provided by this run.");
  }
  lines.push("");

  lines.push("### Reproducibility");
  lines.push("");
  if (method && method.reproducibility_steps.length > 0) {
    method.reproducibility_steps.forEach((item, i) => lines.push(`${i + 1}. ${item}`));
  } else {
    lines.push("Not provided by this run.");
  }
  lines.push("");

  return lines;
}

export function buildCaseFileMarkdown(view: CaseFileView, options: BuildMarkdownOptions): string {
  const lines: string[] = [];
  const headerLines = buildHeaderSection(view);
  lines.push(headerLines[0]); // "# Forensic Case File — ..."
  lines.push("");
  if (options.isSample) {
    lines.push("> Sample data — illustrative, fictional entities. Not a real audit.");
    lines.push("");
  }
  lines.push(...headerLines.slice(2)); // everything after the title + blank line
  lines.push(...buildExecutiveSummarySection(view));
  lines.push(...buildFindingsSection(view, options));
  lines.push(...buildLeadsSection(view));
  lines.push(...buildMethodSection(view));

  // Collapse any accidental run of 2+ blank lines and ensure exactly one trailing newline.
  const collapsed: string[] = [];
  for (const line of lines) {
    if (line === "" && collapsed[collapsed.length - 1] === "") continue;
    collapsed.push(line);
  }
  while (collapsed[collapsed.length - 1] === "") collapsed.pop();
  return `${collapsed.join("\n")}\n`;
}
