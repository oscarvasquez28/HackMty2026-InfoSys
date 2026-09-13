"use client";

// Segmented control: show each finding on one screen, or split it into four step-by-step parts.

import React from "react";
import type { FindingLayout } from "@/lib/caseFile/tour";

interface TourFindingLayoutToggleProps {
  value: FindingLayout;
  onChange: (value: FindingLayout) => void;
}

const OPTIONS: Array<{ value: FindingLayout; label: string }> = [
  { value: "single", label: "One screen" },
  { value: "steps", label: "Step by step" },
];

export const TourFindingLayoutToggle: React.FC<TourFindingLayoutToggleProps> = ({ value, onChange }) => {
  const activeIndex = OPTIONS.findIndex((o) => o.value === value);

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-muted sm:inline">Findings</span>
      <div role="group" aria-label="Finding layout" className="relative grid grid-cols-2 rounded-md border border-surface-border bg-surface p-0.5">
        <span
          aria-hidden="true"
          className="absolute inset-y-0.5 left-0.5 w-[calc(50%-2px)] rounded-[5px] bg-surface-raised ring-1 ring-brand-500/40 transition-transform duration-500 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)]"
          style={{ transform: `translateX(${activeIndex * 100}%)` }}
        />
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={option.value === value}
            onClick={() => onChange(option.value)}
            className={`relative min-h-9 whitespace-nowrap px-3 text-xs font-medium transition-colors duration-200 ${
              option.value === value ? "text-foreground" : "text-muted hover:text-foreground"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
};
