"use client";

// Full-listing counterpart to IssueNotice: every structural error and renderer warning for the
// currently loaded case file, grouped by severity. Screen-only (data-print="hide") -- the printed
// and exported case file itself never carries this chrome.

import React from "react";
import type { ValidationIssue } from "@/types/caseFile";

interface ValidationPanelProps {
  issues: ValidationIssue[];
  open: boolean;
}

export const ValidationPanel: React.FC<ValidationPanelProps> = ({ issues, open }) => {
  if (!open) return null;

  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  return (
    <div data-print="hide" className="border-b border-surface-border bg-surface">
      <div className="mx-auto max-w-[1200px] px-4 py-4 sm:px-6">
        <h2 className="text-sm font-medium text-foreground">Format check (mirrors validate_format.py)</h2>
        <p className="mt-1 text-xs text-muted">Structure only. Exhibit records are checked only when a data estate is loaded.</p>

        {errors.length === 0 && warnings.length === 0 ? (
          <p className="mt-3 text-xs text-status-success">No format errors or warnings.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {errors.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-status-danger">Errors ({errors.length})</h3>
                <ul className="mt-2 space-y-1.5">
                  {errors.map((issue) => (
                    <li key={`${issue.code}-${issue.path}-${issue.message}`} className="font-mono text-xs leading-5 text-muted">
                      <span className="text-status-danger">{issue.path}</span>: {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {warnings.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-status-warning">Warnings ({warnings.length})</h3>
                <ul className="mt-2 space-y-1.5">
                  {warnings.map((issue) => (
                    <li key={`${issue.code}-${issue.path}-${issue.message}`} className="font-mono text-xs leading-5 text-muted">
                      <span className="text-status-warning">{issue.path}</span>: {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
