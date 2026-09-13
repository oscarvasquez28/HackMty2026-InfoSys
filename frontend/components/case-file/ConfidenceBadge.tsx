"use client";

// Certainty badge used at three altitudes: the executive summary's overall confidence, a finding
// heading's compact form, and the finding body's full form with its evidentiary-standard description.

import React from "react";
import { Gavel, TriangleAlert } from "lucide-react";
import { CONFIDENCE_COPY } from "@/lib/caseFile/constants";

interface ConfidenceBadgeProps {
  value: string | null;
  size?: "sm" | "lg";
  showDescription?: boolean;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ value, size = "sm", showDescription = false }) => {
  const sizeClass = size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-[11px]";
  const base = `inline-flex items-center gap-1.5 rounded-sm font-bold ${sizeClass}`;

  let badge: React.ReactNode;
  let description: string | null = null;

  if (value === "proven") {
    badge = (
      <span data-confidence={value} className={`${base} bg-evidence-proven text-evidence-on`}>
        <Gavel className="h-3.5 w-3.5" aria-hidden="true" />
        {CONFIDENCE_COPY.proven.label}
      </span>
    );
    description = CONFIDENCE_COPY.proven.description;
  } else if (value === "probable") {
    badge = (
      <span data-confidence={value} className={`${base} bg-evidence-probable text-evidence-on`}>
        <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
        {CONFIDENCE_COPY.probable.label}
      </span>
    );
    description = CONFIDENCE_COPY.probable.description;
  } else if (value === null) {
    badge = (
      <span data-confidence="" className={`${base} bg-evidence-neutral-soft text-evidence-neutral`}>
        NO FINDINGS
      </span>
    );
  } else {
    badge = (
      <span data-confidence={value} className={`${base} border border-evidence-proven text-evidence-proven`}>
        INVALID CONFIDENCE: {value}
      </span>
    );
  }

  if (showDescription && description) {
    return (
      <div>
        {badge}
        <p className="mt-1 text-xs text-paper-muted">{description}</p>
      </div>
    );
  }
  return badge;
};
