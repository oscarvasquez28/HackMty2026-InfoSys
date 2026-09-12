// Case file contract types. Superset of student-materials/forensic-auditor/submission_schema.json:
// official field names and enums are load-bearing (validate_format.py checks them); anything the
// official schema does not have is an optional extension consumed only by the frontend renderer.

export const SCHEME_TYPES = [
  "phantom_vendor",
  "kickback",
  "round_tripping",
  "threshold_splitting",
  "revenue_inflation",
] as const;
export type SchemeType = (typeof SCHEME_TYPES)[number];

export const SOURCE_TABLES = [
  "ledger",
  "invoices",
  "bank_txns",
  "vendors",
  "efos_list",
  "purchase_orders",
  "contracts",
  "employees",
] as const;
export type SourceTable = (typeof SOURCE_TABLES)[number];

export const CONFIDENCE_LEVELS = ["proven", "probable"] as const;
export type Confidence = (typeof CONFIDENCE_LEVELS)[number];

export const CLOSED_BY_VALUES = ["investigator", "challenger", "validator"] as const;
export type ClosedBy = (typeof CLOSED_BY_VALUES)[number];

export const CLOSURE_CATEGORIES = [
  "materiality_verified",
  "administrative_error",
  "no_bank_correlation",
  "other",
] as const;
export type ClosureCategory = (typeof CLOSURE_CATEGORIES)[number];

export interface MoneyTrailStep {
  from: string;
  to: string;
  amount: number | null;
  date: string;
  exhibit_id: string;
}

export interface Exhibit {
  exhibit_id: string;
  source_table: string;
  record_id: string;
  note: string;
  amount: number | null;
}

export interface RuleDetail {
  code: string;
  authority: string;
  article: string;
  legal_text_citation: string;
}

export interface ReconciliationTableSubtotal {
  table: string;
  subtotal: number;
}

export interface Reconciliation {
  claimed_pesos: number;
  exhibits_sum: number;
  variance_percentage: number;
  matched_table: string | null;
  per_table_breakdown: ReconciliationTableSubtotal[];
}

export interface AdversarialReview {
  challenger_argument: string;
  why_finding_held: string;
  reviewer_agent_role: string;
}

export interface CaseFinding {
  finding_id: string | null;
  scheme_type: string;
  entities: string[];
  narrative: string;
  rule_broken: string;
  rule_detail: RuleDetail | null;
  peso_amount: number | null;
  confidence: string;
  money_trail: MoneyTrailStep[] | null;
  mermaid_source: string | null;
  exhibits: Exhibit[];
  reconciliation: Reconciliation | null;
  adversarial_review: AdversarialReview | null;
}

export interface LeadNotPursued {
  entity: string;
  signal: string;
  reason: string;
  tool_calls_made: string[] | null;
  closed_by: string | null;
  closure_category: string | null;
}

export interface RunMetadata {
  llm_calls: number | null;
  mxn_cost: number | null;
  wall_clock_seconds: number | null;
  cost_by_role: Record<string, number>; // only finite numeric values kept
  deterministic: boolean | null; // null = not reported
}

export interface CaseHeader {
  company: string;
  company_rfc: string | null;
  audit_period: { start: string; end: string } | null;
}

export interface MethodAndLimits {
  architecture_summary: string;
  out_of_scope: string[];
  undetectable_fraud_types: string[];
  reproducibility_steps: string[];
}

export interface CaseFileDocument {
  seed: number | null;
  header: CaseHeader | null;
  executive_summary: { plain_narrative: string } | null;
  entity_names: Record<string, string>;
  findings: CaseFinding[];
  leads_not_pursued: LeadNotPursued[];
  run_metadata: RunMetadata;
  method_and_limits: MethodAndLimits | null;
}

export type IssueSeverity = "error" | "warning";

export interface ValidationIssue {
  severity: IssueSeverity;
  code: string;
  path: string;
  message: string;
}
