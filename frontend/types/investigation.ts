export interface ThoughtToolCall {
  name: string;
  label: string;
  outcome: string;
  duration_ms?: number;
}

export interface ThoughtEvent {
  step: number;
  phase: string;
  message: string;
  timestamp: string;
  event_id?: string;
  agent_id?: AgentId;
  action?: ReviewAction;
  source?: ReviewSource;
  evidence_refs?: EvidenceRef[];
  headline?: string;
  metric?: string;
  tool_call?: ThoughtToolCall;
}

export interface VerdictPatternsSummary {
  closed_cycles: number;
  passthrough_accounts: number;
  pruning_efficiency_pct: number;
}

export interface VerdictEvent {
  case_id: string;
  risk_level: "CRÍTICO" | "ALTO" | "MEDIO" | "BAJO";
  fraud_type: string;
  total_amount_mxn: number;
  confidence_score: number | null;
  source?: ReviewSource;
  assessment_method?: string;
  assessment_status?: "SUSPICIOUS_PATTERNS_DETECTED" | "NO_PATTERNS_DETECTED";
  limitations?: string[];
  entities_involved: string[];
  pruned_leads_count: number;
  patterns_summary: VerdictPatternsSummary;
  legal_recommendation: string;
  audit_summary_text: string;
  completed_at: string;
}

export interface GraphNode {
  id: string;
  total_in: number;
  total_out: number;
  in_degree: number;
  out_degree: number;
  reasons: string[];
  risk_score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  amount: number;
  count: number;
  timestamps: number[];
  reasons: string[];
}

export interface InvestigationMetrics {
  total_nodes_analyzed: number;
  suspicious_nodes_count: number;
  pruned_nodes_count: number;
  total_edges_analyzed: number;
  suspicious_edges_count: number;
  pruned_edges_count: number;
  suspicious_volume_mxn: number;
  detected_cycles_count: number;
  passthrough_accounts_count: number;
  pruning_efficiency_pct: number;
}

export interface SubgraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface UploadResponse {
  case_id: string;
  simulation?: boolean;
  source_files?: string[];
  filename?: string;
  ingestion?: {
    total_records: number;
    total_volume: number;
    unique_accounts: number;
    original_columns: string[];
    timestamps_synthetic: boolean;
  };
  preview?: TransactionPreview[];
  message: string;
  metrics: InvestigationMetrics;
  subgraph: SubgraphData;
  patterns: {
    cycles: Array<{ path: string[]; length: number; estimated_volume: number }>;
    passthrough_accounts: Array<{
      account: string;
      total_in: number;
      total_out: number;
      ratio: number;
      time_delta_hours: number;
    }>;
  };
}

export const AGENT_IDS = ["ORCHESTRATOR", "DATA_VALIDATION", "CIRCULAR_FLOWS", "PASSTHROUGH", "RISK_REVIEW"] as const;
export type AgentId = typeof AGENT_IDS[number];
export type ReviewSource = "DETERMINISTIC" | "EXTERNAL" | "SIMULATION";
export type ReviewAction = "started" | "delegated" | "tool" | "finding" | "returned" | "synthesizing" | "fallback";
export type AgentStatus = "waiting" | "available" | "reviewing" | "returned" | "interrupted" | "complete";
export type AgentStatuses = Record<AgentId, AgentStatus>;

export type InvestigationStage = "ingestion" | "discovery" | "synthesis" | "verdict";

export interface AgentDecision {
  task: string;
  decision?: string;
  metric?: string;
  timestamp: string;
  evidence_ref?: EvidenceRef;
}

export interface TeamAdvanceMetric {
  label: string;
  value: string;
  isAlert?: boolean;
}

export interface TeamSituationalState {
  stage: InvestigationStage;
  stageIndex: number;
  progressPct: number;
  stageTitle: string;
  executiveSummary: string;
  advances: TeamAdvanceMetric[];
}

export interface EvidenceRef {
  kind: "dataset" | "cycle" | "passthrough" | "overview";
  id: string;
  label: string;
}

export interface TransactionPreview {
  origin: string;
  destination: string;
  amount: number;
  timestamp: number | null;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const isStrings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === "string");
const hasNumbers = (value: Record<string, unknown>, keys: string[]) => keys.every(key => isNumber(value[key]) && (value[key] as number) >= 0);
const isDate = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));
const isSource = (value: unknown) => value === undefined || value === "DETERMINISTIC" || value === "EXTERNAL" || value === "SIMULATION";

export function isThoughtEvent(value: unknown): value is ThoughtEvent {
  if (!isRecord(value) || !isNumber(value.step) || typeof value.phase !== "string" || typeof value.message !== "string" || !isDate(value.timestamp)) return false;
  return isSource(value.source)
    && (value.event_id === undefined || typeof value.event_id === "string")
    && (value.agent_id === undefined || AGENT_IDS.includes(value.agent_id as AgentId))
    && (value.action === undefined || ["started", "delegated", "tool", "finding", "returned", "synthesizing", "fallback"].includes(value.action as string))
    && (value.evidence_refs === undefined || (Array.isArray(value.evidence_refs) && value.evidence_refs.every(ref =>
      isRecord(ref) && ["dataset", "cycle", "passthrough", "overview"].includes(ref.kind as string) && typeof ref.id === "string" && typeof ref.label === "string")));
}

export function isVerdictEvent(value: unknown): value is VerdictEvent {
  if (!isRecord(value) || !isRecord(value.patterns_summary)) return false;
  return typeof value.case_id === "string" && ["CRÍTICO", "ALTO", "MEDIO", "BAJO"].includes(value.risk_level as string)
    && ["fraud_type", "legal_recommendation", "audit_summary_text"].every(key => typeof value[key] === "string")
    && hasNumbers(value, ["total_amount_mxn", "pruned_leads_count"])
    && (value.confidence_score === null || (isNumber(value.confidence_score) && value.confidence_score >= 0 && value.confidence_score <= 1))
    && isStrings(value.entities_involved) && isDate(value.completed_at) && isSource(value.source)
    && hasNumbers(value.patterns_summary, ["closed_cycles", "passthrough_accounts", "pruning_efficiency_pct"])
    && (value.assessment_status === undefined || ["SUSPICIOUS_PATTERNS_DETECTED", "NO_PATTERNS_DETECTED"].includes(value.assessment_status as string))
    && (value.assessment_method === undefined || typeof value.assessment_method === "string")
    && (value.limitations === undefined || isStrings(value.limitations));
}

export function isUploadResponse(value: unknown): value is UploadResponse {
  if (!isRecord(value) || typeof value.case_id !== "string" || typeof value.message !== "string"
    || !isRecord(value.metrics) || !isRecord(value.subgraph) || !isRecord(value.patterns)) return false;
  if (!hasNumbers(value.metrics, ["total_nodes_analyzed", "suspicious_nodes_count", "pruned_nodes_count", "total_edges_analyzed", "suspicious_edges_count", "pruned_edges_count", "suspicious_volume_mxn", "detected_cycles_count", "passthrough_accounts_count", "pruning_efficiency_pct"])) return false;
  if (!Array.isArray(value.subgraph.nodes) || !value.subgraph.nodes.every(node => isRecord(node) && typeof node.id === "string" && isStrings(node.reasons) && hasNumbers(node, ["total_in", "total_out", "in_degree", "out_degree", "risk_score"]))) return false;
  if (!Array.isArray(value.subgraph.edges) || !value.subgraph.edges.every(edge => isRecord(edge) && typeof edge.source === "string" && typeof edge.target === "string" && hasNumbers(edge, ["amount", "count"]) && isStrings(edge.reasons) && Array.isArray(edge.timestamps) && edge.timestamps.every(isNumber))) return false;
  if (!Array.isArray(value.patterns.cycles) || !value.patterns.cycles.every(cycle => isRecord(cycle) && isStrings(cycle.path) && hasNumbers(cycle, ["length", "estimated_volume"]))) return false;
  if (!Array.isArray(value.patterns.passthrough_accounts) || !value.patterns.passthrough_accounts.every(account => isRecord(account) && typeof account.account === "string" && hasNumbers(account, ["total_in", "total_out", "ratio", "time_delta_hours"]))) return false;
  if (value.simulation !== undefined && typeof value.simulation !== "boolean") return false;
  if (value.source_files !== undefined && !isStrings(value.source_files)) return false;
  if (value.filename !== undefined && typeof value.filename !== "string") return false;
  if (value.ingestion !== undefined && (!isRecord(value.ingestion) || !hasNumbers(value.ingestion, ["total_records", "total_volume", "unique_accounts"]) || !isStrings(value.ingestion.original_columns) || typeof value.ingestion.timestamps_synthetic !== "boolean")) return false;
  return value.preview === undefined || (Array.isArray(value.preview) && value.preview.every(row => isRecord(row) && typeof row.origin === "string" && typeof row.destination === "string" && isNumber(row.amount) && (row.timestamp === null || isNumber(row.timestamp))));
}
