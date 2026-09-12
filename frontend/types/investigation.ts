export interface ThoughtEvent {
  step: number;
  phase: string;
  message: string;
  timestamp: string;
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
  confidence_score: number;
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
