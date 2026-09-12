"use client";

// Flat listing of every estate-wide validation issue (format checks, referential integrity),
// grouped by severity. Capped at 500 rows per group so a badly malformed upload doesn't freeze the page.

import React from "react";
import type { EstateIssue } from "@/types/estate";

interface EstateIssuesPanelProps {
  issues: EstateIssue[];
}

const MAX_ROWS = 500;

function IssueTable({ issues }: { issues: EstateIssue[] }) {
  const shown = issues.slice(0, MAX_ROWS);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-xs">
        <thead>
          <tr className="border-b border-surface-border text-left uppercase tracking-wide text-muted">
            <th className="py-1.5 pr-3">Severity</th>
            <th className="py-1.5 pr-3">Table</th>
            <th className="py-1.5 pr-3">Column</th>
            <th className="py-1.5 pr-3">File</th>
            <th className="py-1.5">Message</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((issue, i) => (
            <tr key={i} className="border-b border-surface-border/50 align-top">
              <td className={`py-1.5 pr-3 font-mono ${issue.severity === "error" ? "text-status-danger" : "text-status-warning"}`}>{issue.severity}</td>
              <td className="py-1.5 pr-3 font-mono">{issue.table ?? "—"}</td>
              <td className="py-1.5 pr-3 font-mono">{issue.column ?? "—"}</td>
              <td className="py-1.5 pr-3">{issue.fileName ?? "—"}</td>
              <td className="py-1.5 text-muted">{issue.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {issues.length > MAX_ROWS && <p className="mt-1 text-xs text-muted">…and {issues.length - MAX_ROWS} more</p>}
    </div>
  );
}

export const EstateIssuesPanel: React.FC<EstateIssuesPanelProps> = ({ issues }) => {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  if (issues.length === 0) {
    return <p className="text-sm text-status-success">No estate-wide issues.</p>;
  }

  return (
    <div className="space-y-4">
      {errors.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-status-danger">Errors ({errors.length})</h3>
          <div className="mt-2">
            <IssueTable issues={errors} />
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-status-warning">Warnings ({warnings.length})</h3>
          <div className="mt-2">
            <IssueTable issues={warnings} />
          </div>
        </div>
      )}
    </div>
  );
};
