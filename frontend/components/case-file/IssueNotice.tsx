"use client";

// Inline, per-field format-check notice. Renders only outside production so the shipped case file
// never carries development chrome; ValidationPanel is where a reader sees the full list on screen.

import React from "react";
import { TriangleAlert } from "lucide-react";
import type { ValidationIssue } from "@/types/caseFile";

interface IssueNoticeProps {
  issues: ValidationIssue[];
}

export const IssueNotice: React.FC<IssueNoticeProps> = ({ issues }) => {
  if (process.env.NODE_ENV === "production" || issues.length === 0) return null;

  return (
    <div data-print="hide" data-export="exclude" className="mt-2 space-y-1">
      {issues.map((issue) => (
        <div
          key={`${issue.code}-${issue.path}-${issue.message}`}
          className={`flex items-start gap-2 rounded-sm border-l-4 px-3 py-2 font-mono text-[11px] leading-5 ${
            issue.severity === "error"
              ? "border-evidence-proven bg-evidence-proven-soft/60 text-evidence-proven"
              : "border-evidence-probable bg-evidence-probable-soft/60 text-evidence-probable"
          }`}
        >
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>{issue.path}:</strong> {issue.message}
          </span>
        </div>
      ))}
    </div>
  );
};

/** Convenience filter: issues whose `path` starts with the given prefix (dotted-path aware). */
export function issuesForPath(issues: ValidationIssue[], prefix: string): ValidationIssue[] {
  return issues.filter((issue) => issue.path === prefix || issue.path.startsWith(`${prefix}.`) || issue.path.startsWith(`${prefix}[`));
}
