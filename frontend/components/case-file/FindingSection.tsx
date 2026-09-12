"use client";

// Assembles one finding's full section (Tasks 3-10) inside a collapsible card: heading with entity
// ids and scheme type, then rule broken, amount & confidence, narrative, money trail, exhibits,
// reconciliation, and adversarial review, in the order case_file_structure.md requires.

import React from "react";
import type { FindingView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { Collapsible } from "@/components/case-file/Collapsible";
import { EntityId } from "@/components/case-file/EntityId";
import { SchemeTypeBadge } from "@/components/case-file/SchemeTypeBadge";
import { ConfidenceBadge } from "@/components/case-file/ConfidenceBadge";
import { RuleBrokenCallout } from "@/components/case-file/RuleBrokenCallout";
import { AmountConfidence } from "@/components/case-file/AmountConfidence";
import { FindingNarrative } from "@/components/case-file/FindingNarrative";
import { MoneyTrail } from "@/components/case-file/MoneyTrail";
import { ExhibitsTable } from "@/components/case-file/ExhibitsTable";
import { ReconciliationBlock } from "@/components/case-file/ReconciliationBlock";
import { AdversarialReview } from "@/components/case-file/AdversarialReview";
import { IssueNotice, issuesForPath } from "@/components/case-file/IssueNotice";
import { formatPesos } from "@/lib/utils";

const H4_CLASS = "mb-2 mt-8 font-mono text-[11px] uppercase tracking-[0.16em] text-paper-muted";

interface FindingSectionProps {
  finding: FindingView;
  total: number;
  figureNumber: number;
  issues: ValidationIssue[];
}

export const FindingSection: React.FC<FindingSectionProps> = ({ finding, total, figureNumber, issues }) => {
  const p = `findings[${finding.index}]`;

  return (
    <section id={finding.anchorId} data-finding-section data-scheme-type={finding.finding.scheme_type} className="mt-10 border-t-2 border-paper-ink pt-6 first:mt-0">
      <Collapsible
        id={finding.anchorId}
        defaultOpen
        summaryClassName="flex w-full flex-wrap items-start justify-between gap-3 text-left"
        summary={
          <>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-paper-muted">
                Finding {finding.number} of {total} · Workpaper {finding.workpaperId}
              </p>
              <h3 className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                {finding.entities.map((entity) => (
                  <EntityId key={entity.id} entity={entity} />
                ))}
                <SchemeTypeBadge value={finding.finding.scheme_type} />
              </h3>
            </div>
            <div className="flex shrink-0 items-center gap-3 sm:ml-auto">
              <span className="font-mono text-sm font-semibold tabular-nums">
                {finding.finding.peso_amount !== null ? formatPesos(finding.finding.peso_amount) : "n/a"}
              </span>
              <ConfidenceBadge value={finding.confidence} size="sm" />
            </div>
          </>
        }
      >
        <div className="pt-4">
          <h4 className={H4_CLASS}>Rule broken</h4>
          <RuleBrokenCallout
            rule={finding.rule}
            hasRuleDetail={finding.finding.rule_detail !== null}
            issues={[...issuesForPath(issues, `${p}.rule_broken`), ...issuesForPath(issues, `${p}.rule_detail`)]}
          />

          <h4 className={H4_CLASS}>Amount and confidence</h4>
          <AmountConfidence amount={finding.finding.peso_amount} confidence={finding.finding.confidence || null} />

          <h4 className={H4_CLASS}>What happened</h4>
          <FindingNarrative narrative={finding.finding.narrative} words={finding.narrativeWords} />
          <IssueNotice issues={issuesForPath(issues, `${p}.narrative`)} />

          <h4 className={H4_CLASS}>Money trail</h4>
          <MoneyTrail
            finding={finding}
            figureNumber={figureNumber}
            issues={[...issuesForPath(issues, `${p}.money_trail`), ...issuesForPath(issues, `${p}.mermaid_source`)]}
          />

          <h4 className={H4_CLASS}>Exhibits</h4>
          <ExhibitsTable finding={finding} issues={issuesForPath(issues, `${p}.exhibits`)} />

          <h4 className={H4_CLASS}>Reconciliation</h4>
          <ReconciliationBlock reconciliation={finding.reconciliation} />

          <h4 className={H4_CLASS}>Adversarial review</h4>
          <AdversarialReview review={finding.finding.adversarial_review} />
        </div>
      </Collapsible>
    </section>
  );
};
