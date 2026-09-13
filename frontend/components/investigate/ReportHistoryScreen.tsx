"use client";

// Audit history screen: lists persisted forensic audit reports (PostgreSQL
// audit_reports table, keyed by run_id) and reopens them inside the shared
// case-file session so the Case File Viewer replays the report step by step.

import React, { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Database, FileClock, FolderOpen, RefreshCw } from "lucide-react";
import { InvestigateAppBar } from "@/components/investigate/InvestigateAppBar";
import { useInvestigateSession } from "@/components/investigate/InvestigateSessionProvider";
import { useAuditReports } from "@/hooks/useAuditReports";
import { formatCurrencyMXN } from "@/lib/utils";

const RISK_LABELS: Record<string, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

const RISK_STYLES: Record<string, string> = {
  CRITICAL: "border-status-danger/40 bg-status-danger/10 text-status-danger",
  HIGH: "border-status-warning/40 bg-status-warning/10 text-status-warning",
  MEDIUM: "border-brand-500/40 bg-brand-500/10 text-brand-300",
  LOW: "border-status-success/40 bg-status-success/10 text-status-success",
};

function riskBadge(level: string | null): React.ReactNode {
  if (!level) return <span className="text-muted">—</span>;
  const key = level.toUpperCase();
  const style = RISK_STYLES[key] ?? "border-surface-border bg-surface-raised text-muted";
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-medium ${style}`}>
      {RISK_LABELS[key] ?? level}
    </span>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export const ReportHistoryScreen: React.FC = () => {
  const router = useRouter();
  const { caseFile } = useInvestigateSession();
  const {
    reports,
    total,
    totalPages,
    page,
    isLoading,
    error,
    databaseEnabled,
    fetchPage,
    refresh,
    loadReportDetail,
  } = useAuditReports();

  const [openingRunId, setOpeningRunId] = useState<string | null>(null);

  const handleOpen = useCallback(
    async (runId: string) => {
      setOpeningRunId(runId);
      const detail = await loadReportDetail(runId);
      if (detail && detail.report && Object.keys(detail.report).length > 0) {
        caseFile.loadRaw(detail.report, {
          kind: "api",
          label: `Audit run ${runId}`,
        });
        router.push("/investigate");
        return;
      }
      setOpeningRunId(null);
    },
    [caseFile, loadReportDetail, router]
  );

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <InvestigateAppBar />

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-medium tracking-tight text-foreground">
              <FileClock className="h-5 w-5 text-brand-300" aria-hidden="true" />
              Audit history
            </h1>
            <p className="mt-1 text-sm text-muted">
              Persisted forensic audit runs. Open one to replay its case file step by step.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={isLoading}
            className="app-button flex items-center gap-2 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} aria-hidden="true" />
            Refresh
          </button>
        </div>

        {databaseEnabled === false && (
          <div className="mt-6 flex items-start gap-3 rounded-xl border border-status-warning/40 bg-status-warning/10 p-4">
            <Database className="mt-0.5 h-4 w-4 shrink-0 text-status-warning" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-foreground">Persistent history is not configured</p>
              <p className="mt-0.5 text-xs text-muted">
                The backend is running without DATABASE_URL, so audit reports are not being stored.
                Completed audits can still be exported manually from the case file viewer.
              </p>
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm text-status-danger">
            {error}
          </p>
        )}

        <div className="mt-6 overflow-hidden rounded-xl border border-surface-border bg-surface-deep">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 text-right font-medium">Amount (MXN)</th>
                <th className="px-4 py-3 text-right font-medium">Findings</th>
                <th className="px-4 py-3 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && reports.length === 0 &&
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-surface-border/60">
                    {Array.from({ length: 7 }).map((__, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-3.5 w-full max-w-28 animate-pulse rounded bg-surface-raised" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!isLoading && reports.length === 0 && databaseEnabled !== false && !error && (
                <tr>
                  <td colSpan={7} className="px-4 py-14 text-center">
                    <p className="text-sm font-medium text-foreground">No audit runs recorded yet</p>
                    <p className="mt-1 text-xs text-muted">
                      Run a forensic audit from the{" "}
                      <Link href="/investigate" className="text-brand-300 underline hover:text-brand-100">
                        case file workspace
                      </Link>{" "}
                      and its report will appear here.
                    </p>
                  </td>
                </tr>
              )}

              {reports.map((report) => (
                <tr
                  key={report.run_id}
                  className="border-b border-surface-border/60 last:border-0 hover:bg-surface-raised/50"
                >
                  <td className="px-4 py-3">
                    <span className="block max-w-44 truncate font-mono text-xs text-foreground" title={report.run_id}>
                      {report.run_id}
                    </span>
                    <span className="text-[11px] text-muted">seed {report.seed ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="block max-w-52 truncate text-foreground">
                      {report.company_name ?? "—"}
                    </span>
                    {report.company_rfc && (
                      <span className="font-mono text-[11px] text-muted">{report.company_rfc}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">{formatDate(report.created_at)}</td>
                  <td className="px-4 py-3">{riskBadge(report.risk_level)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-foreground">
                    {report.total_amount_mxn != null ? formatCurrencyMXN(report.total_amount_mxn) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-foreground">
                    {report.findings_count}
                    <span className="text-muted"> / {report.leads_count} leads</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => void handleOpen(report.run_id)}
                      disabled={openingRunId !== null}
                      className="app-button inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs"
                    >
                      <FolderOpen className="h-3.5 w-3.5" aria-hidden="true" />
                      {openingRunId === report.run_id ? "Opening…" : "Open report"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between text-xs text-muted">
            <span>
              {total} report{total === 1 ? "" : "s"} — page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void fetchPage(page - 1)}
                disabled={isLoading || page <= 1}
                className="app-button px-3 py-1.5"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => void fetchPage(page + 1)}
                disabled={isLoading || page >= totalPages}
                className="app-button px-3 py-1.5"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
