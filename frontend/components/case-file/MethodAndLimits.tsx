"use client";

// Task 12: the formal boundary of what this system claims -- architecture, out-of-scope items, what
// it cannot detect, and how to reproduce the run. Stated plainly so no judge infers completeness the
// system cannot defend.

import React from "react";
import type { MethodAndLimits as MethodAndLimitsData } from "@/types/caseFile";
import { Collapsible } from "@/components/case-file/Collapsible";

interface MethodAndLimitsProps {
  method: MethodAndLimitsData | null;
}

const NOT_PROVIDED = <p className="italic text-paper-muted">Not provided by this run.</p>;

export const MethodAndLimits: React.FC<MethodAndLimitsProps> = ({ method }) => {
  return (
    <section id="method-and-limits" className="border-t-2 border-paper-ink pt-6">
      <h2 className="mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight text-paper-ink">
        5. Method and limits
      </h2>

      <Collapsible
        id="method-architecture"
        defaultOpen={false}
        className="border-b border-paper-border py-3"
        summary={<span className="font-medium">Architecture</span>}
      >
        <div className="pt-2">
          {method?.architecture_summary ? <p className="max-w-prose text-sm leading-6">{method.architecture_summary}</p> : NOT_PROVIDED}
        </div>
      </Collapsible>

      <Collapsible
        id="method-out-of-scope"
        defaultOpen={false}
        className="border-b border-paper-border py-3"
        summary={<span className="font-medium">Out of scope for this run</span>}
      >
        <div className="pt-2">
          {method && method.out_of_scope.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
              {method.out_of_scope.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          ) : (
            NOT_PROVIDED
          )}
        </div>
      </Collapsible>

      <Collapsible
        id="method-cannot-detect"
        defaultOpen={false}
        className="border-b border-paper-border py-3"
        summary={<span className="font-medium">What this system cannot detect</span>}
      >
        <div className="pt-2">
          {method && method.undetectable_fraud_types.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
              {method.undetectable_fraud_types.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          ) : (
            NOT_PROVIDED
          )}
        </div>
      </Collapsible>

      <Collapsible
        id="method-reproducibility"
        defaultOpen={false}
        className="py-3"
        summary={<span className="font-medium">Reproducibility</span>}
      >
        <div className="pt-2">
          {method && method.reproducibility_steps.length > 0 ? (
            <ol className="list-decimal space-y-1 pl-5 text-sm leading-6">
              {method.reproducibility_steps.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ol>
          ) : (
            NOT_PROVIDED
          )}
        </div>
      </Collapsible>
    </section>
  );
};
