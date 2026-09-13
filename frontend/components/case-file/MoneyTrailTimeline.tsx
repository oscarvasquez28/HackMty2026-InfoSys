"use client";

// Chronological step-by-step breakdown under the money trail diagram: date, sender, receiver,
// amount, and a chip linking to the cited exhibit. Flags a break in the chain when one step's
// destination does not match the next step's source. In the tour, the optional sync props let the
// money trail player highlight the playing step and let the reader drive the diagram from a row.

import React from "react";
import type { TrailStepView } from "@/lib/caseFile/derive";
import { formatPesos } from "@/lib/utils";

interface MoneyTrailTimelineProps {
  trail: TrailStepView[];
  /** Index into `trail` of the step highlighted in the diagram. */
  activeStep?: number | null;
  onStepPreview?: (index: number | null) => void;
  onStepSelect?: (index: number) => void;
}

export const MoneyTrailTimeline: React.FC<MoneyTrailTimelineProps> = ({ trail, activeStep = null, onStepPreview, onStepSelect }) => {
  const interactive = Boolean(onStepSelect);

  return (
    <ol onMouseLeave={onStepPreview ? () => onStepPreview(null) : undefined}>
      {trail.map((step, index) => {
        const active = activeStep === index;
        return (
          <li
            key={`${step.stepOrder}-${step.step.exhibit_id}`}
            data-active={active ? "" : undefined}
            onMouseEnter={onStepPreview ? () => onStepPreview(index) : undefined}
            className={`case-avoid-break grid grid-cols-[auto_1fr] gap-4 ${
              interactive ? `-mx-3 rounded-md px-3 transition-colors duration-300 ${active ? "bg-evidence-held-soft" : "hover:bg-paper-raised"}` : ""
            }`}
          >
            <div className="flex flex-col items-center">
              {interactive ? (
                <button
                  type="button"
                  onClick={() => onStepSelect?.(index)}
                  onFocus={onStepPreview ? () => onStepPreview(index) : undefined}
                  onBlur={onStepPreview ? () => onStepPreview(null) : undefined}
                  aria-pressed={active}
                  aria-label={`Show step ${step.stepOrder} in the diagram`}
                  className={`mt-2 grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 font-mono text-xs transition-colors duration-300 ${
                    active ? "border-evidence-held bg-evidence-held text-evidence-on" : "border-paper-ink hover:border-evidence-held"
                  }`}
                >
                  {step.stepOrder}
                </button>
              ) : (
                <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 border-paper-ink font-mono text-xs">
                  {step.stepOrder}
                </div>
              )}
              {index < trail.length - 1 && <div className={`mt-1 w-px flex-1 ${active ? "bg-evidence-held" : "bg-paper-border"}`} />}
            </div>
            <div className={interactive ? "py-2 pb-4" : "pb-4"}>
              <p className="font-mono text-xs text-paper-muted">{step.step.date}</p>
              <p className="mt-0.5 text-sm">
                {step.fromName && <span className="font-serif">{step.fromName} </span>}
                <span className="font-mono">{step.step.from}</span> →{" "}
                {step.toName && <span className="font-serif">{step.toName} </span>}
                <span className="font-mono">{step.step.to}</span>
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold tabular-nums">
                  {step.step.amount === null ? "Amount not reported" : formatPesos(step.step.amount)}
                </span>
                {step.exhibitResolved && step.exhibitAnchor ? (
                  <a
                    href={`#${step.exhibitAnchor}`}
                    data-exhibit-ref
                    className="rounded-sm border border-evidence-held bg-evidence-held-soft px-1.5 font-mono text-[11px] text-evidence-held"
                  >
                    {step.step.exhibit_id}
                  </a>
                ) : (
                  <span
                    title="Not found in this finding's exhibits"
                    className="rounded-sm border border-evidence-proven bg-evidence-proven-soft px-1.5 font-mono text-[11px] text-evidence-proven"
                  >
                    {step.step.exhibit_id || "(no exhibit)"}
                  </span>
                )}
              </div>
              {step.breaksAfter && index < trail.length - 1 && (
                <p className="mt-2 border-t border-dashed border-evidence-probable pt-2 text-[11px] text-evidence-probable">
                  Trail breaks here: step {step.stepOrder} ends at {step.step.to}, step {trail[index + 1].stepOrder} starts at{" "}
                  {trail[index + 1].step.from}.
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
};
