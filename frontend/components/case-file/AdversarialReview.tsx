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
