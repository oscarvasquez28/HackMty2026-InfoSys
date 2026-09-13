"use client";

// Task 1: forensic header and audit telemetry -- company/period identification, cost figures, and
// the reproducibility badge that tells a judge whether re-running this seed is expected to match.

import React from "react";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import type { CaseFileDocument } from "@/types/caseFile";
import { formatInteger, formatPesos, formatSeconds } from "@/lib/utils";

interface CaseHeaderProps {
  document: CaseFileDocument;
}

function DeterminismBadge({ deterministic, seed }: { deterministic: boolean | null; seed: number | null }) {
  const base = "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[11px] font-bold";
  if (deterministic === true) {
    return (
      <span className={`${base} bg-evidence-reconciled text-evidence-on`}>
        <ShieldCheck className="h-3 w-3" aria-hidden="true" />
        REPRODUCIBLE (SEED {seed ?? "?"})
      </span>
    );
  }
  if (deterministic === false) {
    return (
      <span className={`${base} bg-evidence-probable text-evidence-on`}>
        <TriangleAlert className="h-3 w-3" aria-hidden="true" />
        NON-DETERMINISTIC RUN
      </span>
    );
  }
  return <span className={`${base} bg-paper-muted text-evidence-on`}>DETERMINISM NOT REPORTED</span>;
}

export const CaseHeader: React.FC<CaseHeaderProps> = ({ document }) => {
  const { header, run_metadata: meta, seed } = document;
  const roleKeys = Object.keys(meta.cost_by_role).sort();

  return (
    <header id="case-header">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-paper-muted">Forensic case file · 1. Header</p>
      <h1 className="mt-1 font-serif text-3xl font-semibold">
        {header?.company || <span className="text-paper-muted">Company not reported</span>}
      </h1>
      <p className="mt-1 font-mono text-sm text-paper-muted">
        RFC {header?.company_rfc || "not reported"} · Audit period{" "}
        {header?.audit_period ? `${header.audit_period.start || "?"} → ${header.audit_period.end || "?"}` : "not reported"}
      </p>

      <dl className="mt-6 grid grid-cols-2 overflow-hidden rounded-sm border border-paper-ink bg-paper-ink font-mono text-paper sm:grid-cols-5">
        <div className="border-paper/15 px-4 py-3 sm:border-l sm:first:border-l-0">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-paper/60">Seed</dt>
          <dd className="mt-1 text-sm font-semibold tabular-nums">{seed !== null ? `#${seed}` : <span className="text-paper/60">Not reported</span>}</dd>
        </div>
        <div className="border-paper/15 px-4 py-3 sm:border-l sm:first:border-l-0">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-paper/60">LLM calls</dt>
          <dd className="mt-1 text-sm font-semibold tabular-nums">
            {meta.llm_calls !== null ? formatInteger(meta.llm_calls) : <span className="text-paper/60">Not reported</span>}
          </dd>
        </div>
        <div className="border-paper/15 px-4 py-3 sm:border-l sm:first:border-l-0">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-paper/60">MXN cost</dt>
          <dd className="mt-1 text-sm font-semibold tabular-nums">
            {meta.mxn_cost !== null ? formatPesos(meta.mxn_cost) : <span className="text-paper/60">Not reported</span>}
          </dd>
        </div>
        <div className="border-paper/15 px-4 py-3 sm:border-l sm:first:border-l-0">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-paper/60">Wall clock</dt>
          <dd className="mt-1 text-sm font-semibold tabular-nums">
            {meta.wall_clock_seconds !== null ? formatSeconds(meta.wall_clock_seconds) : <span className="text-paper/60">Not reported</span>}
          </dd>
        </div>
        <div className="border-paper/15 px-4 py-3 sm:border-l sm:first:border-l-0">
          <dt className="text-[10px] uppercase tracking-[0.16em] text-paper/60">Determinism</dt>
          <dd className="mt-1 text-sm font-semibold tabular-nums">
            <DeterminismBadge deterministic={meta.deterministic} seed={seed} />
          </dd>
        </div>
      </dl>

      {roleKeys.length > 0 && (
        <p className="mt-2 font-mono text-xs text-paper-muted">
          Cost by role: {roleKeys.map((key) => `${key} ${formatPesos(meta.cost_by_role[key])}`).join(" · ")}
        </p>
      )}
    </header>
  );
};
