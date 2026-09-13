"use client";

// Task 11: every lead that was investigated and closed without an accusation, in the body of the
// case file (not an appendix) with quick filters so a judge can find one entity in seconds.

import React from "react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { LeadsTable } from "@/components/case-file/LeadsTable";
import { IssueNotice, issuesForPath } from "@/components/case-file/IssueNotice";

interface LeadsNotPursuedProps {
  view: CaseFileView;
  issues: ValidationIssue[];
}

export const LeadsNotPursued: React.FC<LeadsNotPursuedProps> = ({ view, issues }) => {
  return (
    <section id="leads-not-pursued" className="border-t-2 border-paper-ink pt-6">
      <h2 className="mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight text-paper-ink">
        4. Leads investigated and closed
      </h2>
      <p className="max-w-prose text-sm leading-6 text-paper-muted">
        Each entry is a lead that tripped a detector, was investigated, and was closed without an accusation.
      </p>

      {view.leads.length === 0 ? (
        <p className="mt-4 text-sm text-paper-muted">No leads were closed in this run.</p>
      ) : (
        <LeadsTable leads={view.leads} />
      )}
      <IssueNotice issues={issuesForPath(issues, "leads_not_pursued")} />
    </section>
  );
};
