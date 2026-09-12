"use client";

// Task 5: the exact peso amount at issue, sized for a courtroom read, paired with the two-state
// evidentiary confidence (proven / probable) and its full description.

import React from "react";
import { formatPesos } from "@/lib/utils";
import { ConfidenceBadge } from "@/components/case-file/ConfidenceBadge";

interface AmountConfidenceProps {
  amount: number | null;
  confidence: string | null;
}

export const AmountConfidence: React.FC<AmountConfidenceProps> = ({ amount, confidence }) => {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper-muted">Amount at issue</p>
        {amount !== null ? (
          <p className="mt-1 font-mono text-3xl font-semibold tabular-nums">{formatPesos(amount)}</p>
        ) : (
          <p className="mt-1 font-mono text-3xl font-semibold text-evidence-probable">Amount not reported</p>
        )}
      </div>
      <ConfidenceBadge value={confidence} size="lg" showDescription />
    </div>
  );
};
