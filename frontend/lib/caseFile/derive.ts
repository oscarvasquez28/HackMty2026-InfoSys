// Derives presentation-ready view models from a normalized CaseFileDocument: entity display names,
// reconciliation arithmetic (mirrors validate_format.py::validate_against_estate), money-trail
// step linking, and the executive summary table. Pure and deterministic: same document -> same view.

import type {
  CaseFileDocument,
  CaseFinding,
  Confidence,
  LeadNotPursued,
  MoneyTrailStep,
  ReconciliationTableSubtotal,
  SchemeType,
} from "@/types/caseFile";
import { AMOUNT_COLUMN, ID_COLUMN, isClosedBy, isClosureCategory, isConfidence, isSchemeType, isSourceTable } from "@/lib/caseFile/constants";
import { formatPesos } from "@/lib/utils";
import { buildMermaidFromTrail } from "@/lib/caseFile/mermaid";
import type { ClosedBy, ClosureCategory } from "@/types/caseFile";
import type { EstateRow, EstateTables } from "@/types/estate";

export interface EntityRef {
  id: string;
  prefix: string | null;
  kindLabel: string | null;
  name: string | null;
}

export interface TrailStepView {
  stepOrder: number;
  step: MoneyTrailStep;
  fromName: string | null;
  toName: string | null;
  exhibitAnchor: string | null;
  exhibitResolved: boolean;
  breaksAfter: boolean;
}

export type ReconciliationOrigin = "estate" | "backend" | "derived" | "none";

export interface ReconciliationView {
  status: "reconciled" | "not_reconciled" | "unverifiable";
  origin: ReconciliationOrigin;
  claimed: number | null;
  matchedTable: string | null;
  matchedSubtotal: number | null;
  delta: number | null;
  variancePct: number | null;
  perTable: ReconciliationTableSubtotal[];
}

export interface RuleView {
  title: string;
  code: string | null;
  authority: string | null;
  citation: string | null;
  citedAs: string;
}

export interface FindingView {
  index: number;
  number: number;
  anchorId: string;
  workpaperId: string;
  finding: CaseFinding;
  schemeType: SchemeType | null;
  confidence: Confidence | null;
  entities: EntityRef[];
  narrativeWords: number;
  rule: RuleView;
  trail: TrailStepView[] | null;
  mermaidPrimary: string | null;
  mermaidGenerated: string | null;
  exhibitAnchors: Record<string, string>;
  duplicateExhibitIds: string[];
  exhibitEstate: Record<string, { status: "not_checked" | "found" | "missing"; record: EstateRow | null }>;
  reconciliation: ReconciliationView;
}

export interface SummaryView {
  findingsCount: number;
  proven: number;
  probable: number;
  invalid: number;
  globalConfidence: Confidence | null;
  totalExposure: number;
  closedLeadsCount: number;
  narrative: string;
  narrativeOrigin: "run" | "derived";
}

export interface LeadView {
  index: number;
  anchorId: string;
  lead: LeadNotPursued;
  name: string | null;
  closedBy: ClosedBy | null;
  category: ClosureCategory | null;
  toolCount: number;
}

export interface CaseFileView {
  document: CaseFileDocument;
  summary: SummaryView;
  findings: FindingView[];
  leads: LeadView[];
}

export function exhibitAnchor(findingAnchor: string, exhibitId: string): string {
  return `${findingAnchor}-exhibit-${exhibitId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function entityKind(id: string): { prefix: string | null; rest: string } {
  const colonIndex = id.indexOf(":");
  if (colonIndex === -1) return { prefix: null, rest: id };
  return { prefix: id.slice(0, colonIndex), rest: id.slice(colonIndex + 1) };
}

function buildEntityRef(id: string, entityNames: Record<string, string>): EntityRef {
  const { prefix } = entityKind(id);
  const kindLabel = prefix === "RFC" ? "Vendor / company" : prefix === "EMP" ? "Employee" : null;
  return { id, prefix, kindLabel, name: entityNames[id] ?? null };
}

/** Computes per-table exhibit subtotals in first-appearance order, mirroring validate_format.py. */
export function computePerTableSubtotals(finding: CaseFinding): ReconciliationTableSubtotal[] {
  const order: string[] = [];
  const totals = new Map<string, number>();
  for (const exhibit of finding.exhibits) {
    const col = AMOUNT_COLUMN[exhibit.source_table as keyof typeof AMOUNT_COLUMN];
    if (!col || exhibit.amount === null) continue;
    if (!totals.has(exhibit.source_table)) {
      order.push(exhibit.source_table);
      totals.set(exhibit.source_table, 0);
    }
    totals.set(exhibit.source_table, (totals.get(exhibit.source_table) ?? 0) + exhibit.amount);
  }
  return order.map((table) => ({ table, subtotal: totals.get(table) ?? 0 }));
}

/** Picks the best-matching table for a claimed amount: minimum |claimed - subtotal|, ties keep the
 * first table to appear (mirrors validate_format.py's `min(..., key=...)` over an insertion-ordered dict). */
export function pickBestMatch(
  claimed: number,
  perTable: ReconciliationTableSubtotal[]
): { table: string; subtotal: number } | null {
  if (perTable.length === 0) return null;
  let best = perTable[0];
  let bestDelta = Math.abs(claimed - best.subtotal);
  for (const entry of perTable.slice(1)) {
    const delta = Math.abs(claimed - entry.subtotal);
    if (delta < bestDelta) {
      best = entry;
      bestDelta = delta;
    }
  }
  return { table: best.table, subtotal: best.subtotal };
}

/** Per-exhibit estate lookup: does the cited record_id actually exist in the loaded estate table? */
function buildExhibitEstate(
  finding: CaseFinding,
  estate: EstateTables | null
): Record<string, { status: "not_checked" | "found" | "missing"; record: EstateRow | null }> {
  const result: FindingView["exhibitEstate"] = {};
  for (const exhibit of finding.exhibits) {
    if (!estate || !isSourceTable(exhibit.source_table)) {
      result[exhibit.exhibit_id] = { status: "not_checked", record: null };
      continue;
    }
    const pkColumn = ID_COLUMN[exhibit.source_table];
    const record = estate[exhibit.source_table].find((row) => String(row[pkColumn] ?? "") === String(exhibit.record_id)) ?? null;
    result[exhibit.exhibit_id] = { status: record ? "found" : "missing", record };
  }
  return result;
}

/** Per-table subtotals computed from the estate's own amount columns (not the exhibit's self-reported
 * `amount`), mirroring validate_format.py::validate_against_estate. Only exhibits found in the estate
 * contribute; a missing record is a structural error handled separately (estateCheck.ts). */
function computePerTableSubtotalsFromEstate(
  finding: CaseFinding,
  exhibitEstate: Record<string, { status: string; record: EstateRow | null }>
): ReconciliationTableSubtotal[] {
  const order: string[] = [];
  const totals = new Map<string, number>();
  for (const exhibit of finding.exhibits) {
    if (!isSourceTable(exhibit.source_table)) continue;
    const col = AMOUNT_COLUMN[exhibit.source_table];
    const entry = exhibitEstate[exhibit.exhibit_id];
    if (!col || !entry || entry.status !== "found" || !entry.record) continue;
    const amount = Number(entry.record[col] ?? 0);
    if (!totals.has(exhibit.source_table)) {
      order.push(exhibit.source_table);
      totals.set(exhibit.source_table, 0);
    }
    totals.set(exhibit.source_table, (totals.get(exhibit.source_table) ?? 0) + amount);
  }
  return order.map((table) => ({ table, subtotal: totals.get(table) ?? 0 }));
}

function buildReconciliation(
  finding: CaseFinding,
  exhibitEstate: Record<string, { status: string; record: EstateRow | null }>,
  hasEstate: boolean
): ReconciliationView {
  const perTable = computePerTableSubtotals(finding);

  if (hasEstate) {
    const estatePerTable = computePerTableSubtotalsFromEstate(finding, exhibitEstate);
    if (estatePerTable.length > 0 && finding.peso_amount !== null) {
      const claimed = finding.peso_amount;
      const best = pickBestMatch(claimed, estatePerTable)!;
      const delta = claimed - best.subtotal;
      const variancePct = (Math.abs(delta) / Math.max(best.subtotal, 1)) * 100;
      const status: ReconciliationView["status"] =
        Math.abs(delta) <= 0.02 * Math.max(best.subtotal, 1) ? "reconciled" : "not_reconciled";
      return { status, origin: "estate", claimed, matchedTable: best.table, matchedSubtotal: best.subtotal, delta, variancePct, perTable: estatePerTable };
    }
  }

  if (finding.reconciliation) {
    const r = finding.reconciliation;
    const delta = r.claimed_pesos - r.exhibits_sum;
    const status: ReconciliationView["status"] = r.variance_percentage <= 2 ? "reconciled" : "not_reconciled";
    return {
      status,
      origin: "backend",
      claimed: r.claimed_pesos,
      matchedTable: r.matched_table,
      matchedSubtotal: r.exhibits_sum,
      delta,
      variancePct: r.variance_percentage,
      perTable: r.per_table_breakdown.length > 0 ? r.per_table_breakdown : perTable,
    };
  }

  if (perTable.length > 0 && finding.peso_amount !== null) {
    const claimed = finding.peso_amount;
    const best = pickBestMatch(claimed, perTable)!;
    const delta = claimed - best.subtotal;
    const variancePct = (Math.abs(delta) / Math.max(best.subtotal, 1)) * 100;
    const status: ReconciliationView["status"] =
      Math.abs(delta) <= 0.02 * Math.max(best.subtotal, 1) ? "reconciled" : "not_reconciled";
    return {
      status,
      origin: "derived",
      claimed,
      matchedTable: best.table,
      matchedSubtotal: best.subtotal,
      delta,
      variancePct,
      perTable,
    };
  }

  return {
    status: "unverifiable",
    origin: "none",
    claimed: finding.peso_amount,
    matchedTable: null,
    matchedSubtotal: null,
    delta: null,
    variancePct: null,
    perTable,
  };
}

function buildRule(finding: CaseFinding): RuleView {
  const code = finding.rule_detail?.code || null;
  const catalog = code ? RULE_CATALOG_LOOKUP[code] : undefined;
  const authority = finding.rule_detail?.authority || catalog?.authority || null;
  const article = finding.rule_detail?.article || catalog?.article || finding.rule_broken;
  const title = authority ? `${authority} — ${article}` : article;
  const citation = finding.rule_detail?.legal_text_citation || null;
  return { title, code, authority, citation, citedAs: finding.rule_broken };
}

// Imported lazily to avoid a hard dependency cycle at module-eval time; constants.ts has no
// dependency on derive.ts so a direct import is safe.
import { RULE_CATALOG as RULE_CATALOG_LOOKUP } from "@/lib/caseFile/constants";

function buildTrail(
  finding: CaseFinding,
  entityNames: Record<string, string>,
  exhibitAnchors: Record<string, string>
): TrailStepView[] | null {
  if (finding.money_trail === null) return null;
  const steps = finding.money_trail;
  const exhibitIds = new Set(finding.exhibits.map((e) => e.exhibit_id));
  return steps.map((step, index) => {
    const nextStep = steps[index + 1];
    return {
      stepOrder: index + 1,
      step,
      fromName: entityNames[step.from] ?? null,
      toName: entityNames[step.to] ?? null,
      exhibitAnchor: step.exhibit_id ? exhibitAnchors[step.exhibit_id] ?? null : null,
      exhibitResolved: exhibitIds.has(step.exhibit_id),
      breaksAfter: nextStep !== undefined && nextStep.from !== step.to,
    };
  });
}

function buildFindingView(
  finding: CaseFinding,
  index: number,
  total: number,
  entityNames: Record<string, string>,
  estate: EstateTables | null
): FindingView {
  const number = index + 1;
  const anchorId = `finding-${number}`;
  const workpaperId = finding.finding_id ?? `F-${String(number).padStart(2, "0")}`;

  const exhibitAnchors: Record<string, string> = {};
  const seenExhibitIds = new Set<string>();
  const duplicateExhibitIds: string[] = [];
  for (const exhibit of finding.exhibits) {
    if (seenExhibitIds.has(exhibit.exhibit_id)) {
      duplicateExhibitIds.push(exhibit.exhibit_id);
    }
    seenExhibitIds.add(exhibit.exhibit_id);
    exhibitAnchors[exhibit.exhibit_id] = exhibitAnchor(anchorId, exhibit.exhibit_id);
  }

  const trail = buildTrail(finding, entityNames, exhibitAnchors);
  const mermaidPrimary = finding.mermaid_source?.trim() || null;
  const mermaidGenerated = trail && trail.length > 0 ? buildMermaidFromTrail(finding.money_trail!, entityNames, finding.entities) : null;
  const exhibitEstate = buildExhibitEstate(finding, estate);

  return {
    index,
    number,
    anchorId,
    workpaperId,
    finding,
    schemeType: isSchemeType(finding.scheme_type) ? finding.scheme_type : null,
    confidence: isConfidence(finding.confidence) ? finding.confidence : null,
    entities: finding.entities.map((id) => buildEntityRef(id, entityNames)),
    narrativeWords: countWordsSimple(finding.narrative),
    rule: buildRule(finding),
    trail,
    mermaidPrimary,
    mermaidGenerated,
    exhibitAnchors,
    duplicateExhibitIds,
    exhibitEstate,
    reconciliation: buildReconciliation(finding, exhibitEstate, estate !== null),
  };
}

function countWordsSimple(text: string): number {
  const trimmed = text.trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}

function buildLeadView(lead: LeadNotPursued, index: number, entityNames: Record<string, string>): LeadView {
  return {
    index,
    anchorId: `lead-${slug(lead.entity)}`,
    lead,
    name: entityNames[lead.entity] ?? null,
    closedBy: lead.closed_by !== null && isClosedBy(lead.closed_by) ? lead.closed_by : null,
    category: lead.closure_category !== null && isClosureCategory(lead.closure_category) ? lead.closure_category : null,
    toolCount: lead.tool_calls_made?.length ?? 0,
  };
}

function dedupeLeadAnchors(leads: LeadView[]): LeadView[] {
  const seen = new Map<string, number>();
  return leads.map((lead) => {
    const count = seen.get(lead.anchorId) ?? 0;
    seen.set(lead.anchorId, count + 1);
    if (count === 0) return lead;
    return { ...lead, anchorId: `${lead.anchorId}-${count + 1}` };
  });
}

function buildSummary(document: CaseFileDocument, findings: FindingView[]): SummaryView {
  const findingsCount = findings.length;
  const proven = findings.filter((f) => f.confidence === "proven").length;
  const probable = findings.filter((f) => f.confidence === "probable").length;
  const invalid = findings.filter((f) => f.confidence === null).length;
  const globalConfidence: Confidence | null =
    findingsCount === 0 ? null : proven === findingsCount ? "proven" : "probable";
  const totalExposure = document.findings.reduce((sum, f) => sum + (f.peso_amount ?? 0), 0);
  const closedLeadsCount = document.leads_not_pursued.length;

  const runNarrative = document.executive_summary?.plain_narrative?.trim() ?? "";
  let narrative = runNarrative;
  let narrativeOrigin: SummaryView["narrativeOrigin"] = "run";
  if (runNarrative === "") {
    narrativeOrigin = "derived";
    if (findingsCount === 0) {
      narrative = `No accusation was made in this run. ${closedLeadsCount} lead(s) were investigated and closed with documentary reasons.`;
    } else {
      narrative = `${findingsCount} finding(s) with a total exposure of ${formatPesos(totalExposure)}: ${proven} proven and ${probable} probable. ${closedLeadsCount} lead(s) were investigated and closed without an accusation.`;
    }
  }

  return { findingsCount, proven, probable, invalid, globalConfidence, totalExposure, closedLeadsCount, narrative, narrativeOrigin };
}

export function buildCaseFileView(document: CaseFileDocument, estate: EstateTables | null = null): CaseFileView {
  const findings = document.findings.map((finding, index) =>
    buildFindingView(finding, index, document.findings.length, document.entity_names, estate)
  );
  const leads = dedupeLeadAnchors(document.leads_not_pursued.map((lead, index) => buildLeadView(lead, index, document.entity_names)));
  const summary = buildSummary(document, findings);
  return { document, summary, findings, leads };
}
