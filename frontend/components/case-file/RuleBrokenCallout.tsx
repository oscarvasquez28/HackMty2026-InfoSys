"use client";

// Task 4: the specific rule or article a finding relies on -- never a description of a statistical
// pattern. Renders as a legal-alert box with a contrasting left border, per case_file_structure.md.

import React from "react";
import { Scale } from "lucide-react";
import type { RuleView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { IssueNotice } from "@/components/case-file/IssueNotice";

interface RuleBrokenCalloutProps {
  rule: RuleView;
  hasRuleDetail: boolean;
  issues: ValidationIssue[];
}

export const RuleBrokenCallout: React.FC<RuleBrokenCalloutProps> = ({ rule, hasRuleDetail, issues }) => {
  return (
    <div>
      <aside role="note" className="case-avoid-break border-l-4 border-evidence-proven bg-evidence-proven-soft/60 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Scale className="h-4 w-4 shrink-0 text-evidence-proven" aria-hidden="true" />
          <p className="font-serif text-lg font-semibold">{rule.title}</p>
          {rule.code && (
            <code className="rounded-sm border border-evidence-proven/40 px-1.5 font-mono text-[11px] text-evidence-proven">
              {rule.code}
            </code>
          )}
        </div>
        {rule.citation && <blockquote className="mt-2 font-serif italic leading-7">&ldquo;{rule.citation}&rdquo;</blockquote>}
        {hasRuleDetail && <p className="mt-2 font-mono text-[11px] text-paper-muted">Cited as: {rule.citedAs}</p>}
      </aside>
      <IssueNotice issues={issues} />
    </div>
  );
};
