"use client";

// Assembles the full case file document in the order case_file_structure.md requires: Header,
// Executive summary, one section per finding, Leads investigated and closed, Method and limits.
// This is the DOM node exported by Print/PDF, the HTML export, and read for the JSON export's
// context -- see ExportToolbar.tsx and lib/caseFile/toHtml.ts.

import React from "react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { CaseFileSource } from "@/hooks/useCaseFileSource";
import type { ValidationIssue } from "@/types/caseFile";
import { CaseHeader } from "@/components/case-file/CaseHeader";
import { ExecutiveSummary } from "@/components/case-file/ExecutiveSummary";
import { FindingSection } from "@/components/case-file/FindingSection";
import { LeadsNotPursued } from "@/components/case-file/LeadsNotPursued";
import { MethodAndLimits } from "@/components/case-file/MethodAndLimits";
import { issuesForPath } from "@/components/case-file/IssueNotice";

interface CaseFileDocumentProps {
  view: CaseFileView;
  source: CaseFileSource;
  issues: ValidationIssue[];
}

export const CaseFileDocument: React.FC<CaseFileDocumentProps> = ({ view, source, issues }) => {
  const { document, findings, leads, summary } = view;
  const errorCount = issues.filter((i) => i.severity === "error").length;

  return (
    <article
      id="case-file-document"
      className="case-paper mx-auto max-w-[960px] rounded-sm bg-paper px-6 py-8 text-paper-ink shadow-panel ring-1 ring-paper-border sm:px-12 sm:py-12"
    >
      {source.kind === "sample" && (
        <div className="mb-6 border border-evidence-held bg-evidence-held-soft px-3 py-2 font-mono text-xs text-evidence-held">
          Sample data — illustrative, fictional entities. Not a real audit.
        </div>
      )}

      <CaseHeader document={document} />

      <nav aria-label="Contents" id="contents" className="mt-8 rounded-sm border border-paper-border bg-paper-raised p-4 text-sm">
        <ol className="list-decimal space-y-1 pl-5">
          <li>
            <a href="#executive-summary">Executive summary</a>
          </li>
          <li>
            <a href="#findings">Findings</a>
            {findings.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-5 pt-1 text-xs">
                {findings.map((f) => (
                  <li key={f.anchorId}>
                    <a href={`#${f.anchorId}`}>
                      Finding {f.number}: {f.finding.entities.join(", ")}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </li>
          <li>
            <a href="#leads-not-pursued">Leads investigated and closed</a>
          </li>
          <li>
            <a href="#method-and-limits">Method and limits</a>
          </li>
        </ol>
      </nav>

      <ExecutiveSummary summary={summary} />

      <section id="findings">
        <h2 className="mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight text-paper-ink">
          3. Findings
        </h2>
        {findings.length === 0 ? (
          <p className="text-sm text-paper-muted">No findings were validated in this run.</p>
        ) : (
          findings.map((finding, i) => (
            <FindingSection
              key={finding.anchorId}
              finding={finding}
              total={findings.length}
              figureNumber={i + 1}
              issues={issuesForPath(issues, `findings[${finding.index}]`)}
            />
          ))
        )}
      </section>

      <LeadsNotPursued view={view} issues={issues} />

      <MethodAndLimits method={document.method_and_limits} />

      <footer className="mt-12 border-t border-paper-border pt-4 font-mono text-[11px] text-paper-muted">
        Case file for estate seed {document.seed ?? "unknown"} · Format check: {errorCount === 0 ? "PASS" : `${errorCount} error(s)`}
      </footer>
    </article>
  );
};
