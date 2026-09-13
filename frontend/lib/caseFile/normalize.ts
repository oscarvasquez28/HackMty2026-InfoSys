// Converts an arbitrary parsed JSON value into a lenient CaseFileDocument the renderer can always
// walk without crashing. This is NOT the validator: validate.ts checks the raw JSON for format
// errors in parallel. Normalization only decides defaults for missing/malformed fields so the UI
// has something safe to render, and surfaces those defects as warnings (see validate.ts).

import { isRecord } from "@/types/investigation";
import type {
  CaseFileDocument,
  CaseFinding,
  CaseHeader,
  LeadNotPursued,
  MethodAndLimits,
  MoneyTrailStep,
  Exhibit,
  Reconciliation,
  ReconciliationTableSubtotal,
  RuleDetail,
  AdversarialReview,
  RunMetadata,
} from "@/types/caseFile";

export type NormalizeResult = { ok: true; document: CaseFileDocument } | { ok: false; error: string };

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asFiniteNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function normalizeHeader(value: unknown): CaseHeader | null {
  if (!isRecord(value)) return null;
  const periodRaw = value.audit_period;
  const audit_period = isRecord(periodRaw)
    ? { start: asString(periodRaw.start), end: asString(periodRaw.end) }
    : null;
  return {
    company: asString(value.company),
    company_rfc: asStringOrNull(value.company_rfc),
    audit_period,
  };
}

function normalizeRuleDetail(value: unknown): RuleDetail | null {
  if (!isRecord(value)) return null;
  return {
    code: asString(value.code),
    authority: asString(value.authority),
    article: asString(value.article),
    legal_text_citation: asString(value.legal_text_citation),
  };
}

function normalizeMoneyTrail(value: unknown): MoneyTrailStep[] | null {
  if (!Array.isArray(value)) return null;
  return value.map((step): MoneyTrailStep => {
    const record = isRecord(step) ? step : {};
    return {
      from: asString(record.from),
      to: asString(record.to),
      amount: asFiniteNumberOrNull(record.amount),
      date: asString(record.date),
      exhibit_id: asString(record.exhibit_id),
    };
  });
}

function normalizeExhibits(value: unknown): Exhibit[] {
  if (!Array.isArray(value)) return [];
  return value.map((exhibit): Exhibit => {
    const record = isRecord(exhibit) ? exhibit : {};
    return {
      exhibit_id: asString(record.exhibit_id),
      source_table: asString(record.source_table),
      record_id: asString(record.record_id),
      note: asString(record.note),
      amount: asFiniteNumberOrNull(record.amount),
    };
  });
}

function normalizeReconciliationSubtotals(value: unknown): ReconciliationTableSubtotal[] {
  if (!Array.isArray(value)) return [];
  return value.map((entry): ReconciliationTableSubtotal => {
    const record = isRecord(entry) ? entry : {};
    return { table: asString(record.table), subtotal: asFiniteNumberOrNull(record.subtotal) ?? 0 };
  });
}

function normalizeReconciliation(value: unknown): Reconciliation | null {
  if (!isRecord(value)) return null;
  return {
    claimed_pesos: asFiniteNumberOrNull(value.claimed_pesos) ?? 0,
    exhibits_sum: asFiniteNumberOrNull(value.exhibits_sum) ?? 0,
    variance_percentage: asFiniteNumberOrNull(value.variance_percentage) ?? 0,
    matched_table: asStringOrNull(value.matched_table),
    per_table_breakdown: normalizeReconciliationSubtotals(value.per_table_breakdown),
  };
}

function normalizeAdversarialReview(value: unknown): AdversarialReview | null {
  if (!isRecord(value)) return null;
  return {
    challenger_argument: asString(value.challenger_argument),
    why_finding_held: asString(value.why_finding_held),
    reviewer_agent_role: asString(value.reviewer_agent_role),
  };
}

function normalizeFinding(value: unknown): CaseFinding {
  const record = isRecord(value) ? value : {};
  return {
    finding_id: asStringOrNull(record.finding_id),
    scheme_type: asString(record.scheme_type),
    entities: asStringArray(record.entities),
    narrative: asString(record.narrative),
    rule_broken: asString(record.rule_broken),
    rule_detail: normalizeRuleDetail(record.rule_detail),
    peso_amount: asFiniteNumberOrNull(record.peso_amount),
    confidence: asString(record.confidence),
    money_trail: normalizeMoneyTrail(record.money_trail),
    mermaid_source: asStringOrNull(record.mermaid_source),
    exhibits: normalizeExhibits(record.exhibits),
    reconciliation: normalizeReconciliation(record.reconciliation),
    adversarial_review: normalizeAdversarialReview(record.adversarial_review),
  };
}

function normalizeLead(value: unknown): LeadNotPursued {
  const record = isRecord(value) ? value : {};
  const toolCalls = record.tool_calls_made;
  return {
    entity: asString(record.entity),
    signal: asString(record.signal),
    reason: asString(record.reason),
    tool_calls_made: Array.isArray(toolCalls) ? asStringArray(toolCalls) : null,
    closed_by: asStringOrNull(record.closed_by),
    closure_category: asStringOrNull(record.closure_category),
  };
}

function normalizeRunMetadata(value: unknown): RunMetadata {
  const record = isRecord(value) ? value : {};
  const costByRoleRaw = record.cost_by_role;
  const cost_by_role: Record<string, number> = {};
  if (isRecord(costByRoleRaw)) {
    for (const [key, v] of Object.entries(costByRoleRaw)) {
      const n = asFiniteNumberOrNull(v);
      if (n !== null) cost_by_role[key] = n;
    }
  }
  return {
    llm_calls: asFiniteNumberOrNull(record.llm_calls),
    llm_tokens: asFiniteNumberOrNull(record.llm_tokens),
    llm_usage_estimated: typeof record.llm_usage_estimated === "boolean" ? record.llm_usage_estimated : null,
    mxn_cost: asFiniteNumberOrNull(record.mxn_cost),
    wall_clock_seconds: asFiniteNumberOrNull(record.wall_clock_seconds),
    cost_by_role,
    deterministic: typeof record.deterministic === "boolean" ? record.deterministic : null,
  };
}

function normalizeMethodAndLimits(value: unknown): MethodAndLimits | null {
  if (!isRecord(value)) return null;
  return {
    architecture_summary: asString(value.architecture_summary),
    out_of_scope: asStringArray(value.out_of_scope),
    undetectable_fraud_types: asStringArray(value.undetectable_fraud_types),
    reproducibility_steps: asStringArray(value.reproducibility_steps),
  };
}

function normalizeEntityNames(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {};
  const result: Record<string, string> = {};
  for (const [key, v] of Object.entries(value)) {
    if (typeof v === "string") result[key] = v;
  }
  return result;
}

export function normalizeCaseFile(raw: unknown): NormalizeResult {
  if (!isRecord(raw)) {
    return { ok: false, error: "Expected a JSON object at the top level." };
  }
  const hasAnyExpectedKey =
    "seed" in raw || "findings" in raw || "leads_not_pursued" in raw || "run_metadata" in raw;
  if (!hasAnyExpectedKey) {
    return {
      ok: false,
      error:
        "This JSON does not look like a Forensic Auditor submission (expected seed, findings, leads_not_pursued, run_metadata).",
    };
  }

  const findingsRaw = Array.isArray(raw.findings) ? raw.findings : [];
  const leadsRaw = Array.isArray(raw.leads_not_pursued) ? raw.leads_not_pursued : [];

  const document: CaseFileDocument = {
    seed: Number.isInteger(raw.seed) ? (raw.seed as number) : null,
    header: normalizeHeader(raw.header),
    executive_summary: isRecord(raw.executive_summary)
      ? { plain_narrative: asString(raw.executive_summary.plain_narrative) }
      : null,
    entity_names: normalizeEntityNames(raw.entity_names),
    findings: findingsRaw.map(normalizeFinding),
    leads_not_pursued: leadsRaw.map(normalizeLead),
    run_metadata: normalizeRunMetadata(raw.run_metadata),
    method_and_limits: normalizeMethodAndLimits(raw.method_and_limits),
  };

  return { ok: true, document };
}
