"use client";

// Task 6: the plain-language "what happened" narrative, strictly under 150 words. The word counter
// is a development-only aid -- validate.ts's E_NARRATIVE_WORDS error is the one judges' tooling checks.

import React from "react";
import { MAX_NARRATIVE_WORDS } from "@/lib/caseFile/constants";

interface FindingNarrativeProps {
  narrative: string;
  words: number;
}

export const FindingNarrative: React.FC<FindingNarrativeProps> = ({ narrative, words }) => {
  const overLimit = words > MAX_NARRATIVE_WORDS;
  return (
    <div>
      <p className="max-w-prose whitespace-pre-line font-serif text-base leading-7">{narrative}</p>
      {process.env.NODE_ENV !== "production" && (
        <p data-print="hide" data-export="exclude" className={`mt-1 font-mono text-[11px] ${overLimit ? "text-evidence-proven" : "text-paper-muted"}`}>
          {words} / {MAX_NARRATIVE_WORDS} words
        </p>
      )}
    </div>
  );
};
