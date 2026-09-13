// Types mirroring the /api/v1/reports contract (snake_case on the wire).

export interface AuditReportSummary {
  run_id: string;
  seed: number | null;
  company_name: string | null;
  company_rfc: string | null;
  estate_source: string | null;
  status: string;
  risk_level: string | null;
  total_amount_mxn: number | null;
  findings_count: number;
  leads_count: number;
  created_at: string;
}

export interface AuditReportListResponse {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  database_enabled: boolean;
  items: AuditReportSummary[];
}

export interface AuditReportDetail extends AuditReportSummary {
  report: Record<string, unknown>;
  case_file_markdown: string;
  verdict: Record<string, unknown> | null;
  record_counts: Record<string, number>;
}
