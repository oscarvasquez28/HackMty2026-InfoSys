"use client";

// A finding chapter. With `part` null the whole finding is one screen: a sticky block index with
// scrollspy and blocks that reveal as the reader scrolls. With a `part`, only that step's blocks are
// shown and a part switcher sits under the heading. Blocks reuse the document components, which pick
// up the portal palette from the surrounding .case-tour scope.

import React, { useEffect, useState } from "react";
import type { FindingView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { FINDING_PARTS, type FindingPart } from "@/lib/caseFile/tour";
import { formatPesos } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";
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
import { TourReveal } from "@/components/case-file/tour/TourReveal";
import { riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourFindingProps {
  finding: FindingView;
  total: number;
  figureNumber: number;
  issues: ValidationIssue[];
  part: FindingPart | null;
  number: number;
  chapterCount: number;
  purpose: string;
  onSelectPart: (part: FindingPart) => void;
}

interface Block {
  key: string;
  part: FindingPart;
  title: string;
  render: () => React.ReactNode;
}

export const TourFinding: React.FC<TourFindingProps> = ({ finding, total, figureNumber, issues, part, number, chapterCount, purpose, onSelectPart }) => {
  const p = `findings[${finding.index}]`;
  const amount = useCountUp(finding.finding.peso_amount ?? 0, { delayMs: 450 });
  const blockId = (key: string) => `tour-${finding.anchorId}-${key}`;

  const blocks: Block[] = [
    {
      key: "rule",
      part: "accusation",
      title: "Rule broken",
      render: () => (
        <RuleBrokenCallout
          rule={finding.rule}
          hasRuleDetail={finding.finding.rule_detail !== null}
          issues={[...issuesForPath(issues, `${p}.rule_broken`), ...issuesForPath(issues, `${p}.rule_detail`)]}
        />
      ),
    },
    {
      key: "amount",
      part: "accusation",
      title: "Amount and confidence",
      render: () => <AmountConfidence amount={finding.finding.peso_amount} confidence={finding.finding.confidence || null} />,
    },
    {
      key: "narrative",
      part: "trail",
      title: "What happened",
      render: () => (
        <>
          <FindingNarrative narrative={finding.finding.narrative} words={finding.narrativeWords} />
          <IssueNotice issues={issuesForPath(issues, `${p}.narrative`)} />
        </>
      ),
    },
    {
      key: "trail",
      part: "trail",
      title: "Money trail",
      render: () => (
        <MoneyTrail
          finding={finding}
          figureNumber={figureNumber}
          variant="tour"
          issues={[...issuesForPath(issues, `${p}.money_trail`), ...issuesForPath(issues, `${p}.mermaid_source`)]}
        />
      ),
    },
    {
      key: "exhibits",
      part: "evidence",
      title: "Exhibits",
      render: () => <ExhibitsTable finding={finding} issues={issuesForPath(issues, `${p}.exhibits`)} />,
    },
    {
      key: "reconciliation",
      part: "evidence",
      title: "Reconciliation",
      render: () => <ReconciliationBlock reconciliation={finding.reconciliation} />,
    },
    {
      key: "review",
      part: "review",
      title: "Adversarial review",
      render: () => <AdversarialReview review={finding.finding.adversarial_review} />,
    },
  ];

  const visibleBlocks = part ? blocks.filter((b) => b.part === part) : blocks;
  const [spyKey, setSpyKey] = useState(blocks[0].key);

  // Scrollspy for the one-screen layout's block index.
  useEffect(() => {
    if (part || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setSpyKey(visible[0].target.getAttribute("data-block-key") ?? blocks[0].key);
      },
      { rootMargin: "-35% 0px -55% 0px" }
    );
    document.querySelectorAll(`[data-tour-finding="${finding.anchorId}"] [data-block-key]`).forEach((el) => observer.observe(el));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [part, finding.anchorId]);

  const scrollToBlock = (key: string) => {
    document.getElementById(blockId(key))?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const partIndex = part ? FINDING_PARTS.findIndex((x) => x.part === part) : -1;

  return (
    <div data-tour-finding={finding.anchorId} className="mx-auto w-full max-w-[1200px] px-4 py-10 sm:px-6 lg:py-14">
      {/* Heading band */}
      <header className="grid gap-6 border-b border-surface-border pb-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          <p className="tour-mask font-mono text-[clamp(3rem,7vw,5rem)] font-semibold leading-none tracking-tight text-brand-500/20" aria-hidden="true">
            <span>{String(number).padStart(2, "0")}</span>
          </p>
          <p className="section-label tour-rise mt-3" style={riseStyle(0)}>
            Finding {finding.number} of {total} · Workpaper {finding.workpaperId} · Chapter {number} of {chapterCount}
          </p>
          <h2 data-chapter-heading tabIndex={-1} className="tour-mask mt-3 text-[clamp(1.5rem,3vw,2.25rem)] font-semibold leading-tight tracking-tight outline-none">
            <span style={{ "--mask-delay": "200ms" } as React.CSSProperties}>{part ? FINDING_PARTS[partIndex].label : "The finding"}</span>
          </h2>
          <div className="tour-rise mt-4 flex flex-wrap items-baseline gap-x-4 gap-y-2" style={riseStyle(1)}>
            {finding.entities.map((entity) => (
              <EntityId key={entity.id} entity={entity} />
            ))}
            <SchemeTypeBadge value={finding.finding.scheme_type} />
          </div>
          <p className="tour-rise mt-3 max-w-[60ch] text-sm leading-6 text-muted" style={riseStyle(2)}>
            {purpose}
          </p>
        </div>
        <div className="tour-rise flex flex-wrap items-center gap-4 lg:flex-col lg:items-end" style={riseStyle(3)}>
          <p className="font-mono text-[clamp(1.5rem,3vw,2.25rem)] font-semibold tabular-nums leading-none">
            {finding.finding.peso_amount !== null ? formatPesos(amount) : <span className="text-base text-muted">Amount n/a</span>}
          </p>
          <span className="tour-stamp inline-block" style={{ "--stamp-delay": "750ms" } as React.CSSProperties}>
            <ConfidenceBadge value={finding.confidence} size="lg" />
          </span>
        </div>
      </header>

      {part && (
        <div role="group" aria-label="Finding parts" className="tour-rise mt-6 flex flex-wrap gap-2" style={riseStyle(4)}>
          {FINDING_PARTS.map((entry, i) => (
            <button
              key={entry.part}
              type="button"
              aria-pressed={entry.part === part}
              onClick={() => onSelectPart(entry.part)}
              className={`flex min-h-9 items-center gap-2 rounded-md border px-3 text-xs transition-colors duration-200 ${
                entry.part === part
                  ? "border-brand-500/60 bg-brand-500/10 text-foreground"
                  : "border-surface-border text-muted hover:border-brand-500/40 hover:text-foreground"
              }`}
            >
              <span className="font-mono text-[10px] text-brand-500">{String(i + 1).padStart(2, "0")}</span>
              {entry.label}
            </button>
          ))}
        </div>
      )}

      <div className={`mt-10 grid gap-10 ${part ? "" : "lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-14"}`}>
        {!part && (
          <nav aria-label="Finding sections" className="hidden self-start lg:sticky lg:top-32 lg:block">
            <ol className="space-y-1 border-l border-surface-border">
              {blocks.map((block, i) => {
                const active = spyKey === block.key;
                return (
                  <li key={block.key} className="tour-rise" style={riseStyle(4 + i)}>
                    <button
                      type="button"
                      onClick={() => scrollToBlock(block.key)}
                      className={`-ml-px flex min-h-9 w-full items-center gap-2 border-l-2 pl-4 text-left text-xs transition-colors duration-300 ${
                        active ? "border-brand-500 text-foreground" : "border-transparent text-muted hover:text-foreground"
                      }`}
                    >
                      <span className="font-mono text-[10px] text-brand-500/80">{String(i + 1).padStart(2, "0")}</span>
                      {block.title}
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        )}

        <div className="min-w-0 space-y-14">
          {visibleBlocks.map((block, i) => {
            const content = (
              <>
                <h3 className="mb-4 flex items-baseline gap-3 text-lg font-semibold tracking-tight">
                  <span className="font-mono text-xs text-brand-500">{String(blocks.indexOf(block) + 1).padStart(2, "0")}</span>
                  {block.title}
                </h3>
                {block.render()}
              </>
            );
            // Step-by-step parts are short: choreograph them on entry. One-screen blocks reveal on scroll.
            return part ? (
              <section key={block.key} id={blockId(block.key)} data-block-key={block.key} className="tour-rise scroll-mt-32" style={riseStyle(5 + i)}>
                {content}
              </section>
            ) : (
              <section key={block.key} data-block-key={block.key} className="scroll-mt-32" id={blockId(block.key)}>
                <TourReveal>{content}</TourReveal>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
};
