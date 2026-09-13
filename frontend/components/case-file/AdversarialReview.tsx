"use client";

// Task 10: the two-panel careo -- the defense's own argument, and why the evidence held against it.
// A finding no one tried to break is weaker than one that was attacked and held.

import React from "react";
import { ShieldCheck, Swords } from "lucide-react";
import type { AdversarialReview as AdversarialReviewData } from "@/types/caseFile";

interface AdversarialReviewProps {
  review: AdversarialReviewData | null;
}

export const AdversarialReview: React.FC<AdversarialReviewProps> = ({ review }) => {
  if (!review) {
    return <p className="text-sm italic text-paper-muted">No adversarial review was recorded for this finding.</p>;
  }

  const hasDefense = Boolean(review.challenger_argument.trim());
  const hasHeld = Boolean(review.why_finding_held.trim());

  if (!hasDefense && !hasHeld) {
    return <p className="text-sm italic text-paper-muted">No adversarial review was recorded for this finding.</p>;
  }

  // Single-panel layout for reviews that only carry one side of the careo
  // (e.g. legacy runs that persisted the review as one flat string).
  if (!hasDefense || !hasHeld) {
    const isDefense = hasDefense;
    return (
      <div className="case-avoid-break border border-paper-border">
        <div className={isDefense ? "bg-evidence-neutral-soft p-4" : "bg-evidence-held-soft p-4"}>
          <div className="flex items-center gap-2 text-sm font-medium text-paper-ink">
            {isDefense ? (
              <Swords className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ShieldCheck className="h-4 w-4 text-evidence-held" aria-hidden="true" />
            )}
            {isDefense ? "Adversarial review" : "Why the finding held"}
          </div>
          {isDefense && (
            <p className="mt-1 font-mono text-[11px] text-paper-muted">
              Challenger · {review.reviewer_agent_role || "not reported"}
            </p>
          )}
          <p className="mt-2 font-serif text-sm leading-6">
            {isDefense ? review.challenger_argument : review.why_finding_held}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="case-avoid-break grid border border-paper-border md:grid-cols-2 print:grid-cols-2">
      <div className="bg-evidence-neutral-soft p-4 md:border-r md:border-paper-border">
        <div className="flex items-center gap-2 text-sm font-medium text-paper-ink">
          <Swords className="h-4 w-4" aria-hidden="true" />
          Defense position
        </div>
        <p className="mt-1 font-mono text-[11px] text-paper-muted">Challenger · {review.reviewer_agent_role || "not reported"}</p>
        <p className="mt-2 font-serif text-sm leading-6">{review.challenger_argument}</p>
      </div>
      <div className="bg-evidence-held-soft p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-paper-ink">
          <ShieldCheck className="h-4 w-4 text-evidence-held" aria-hidden="true" />
          Why the finding held
        </div>
        <p className="mt-2 font-serif text-sm leading-6">{review.why_finding_held}</p>
      </div>
    </div>
  );
};
