"use client";

import React, { useState } from "react";
import { ShieldCheck, ShieldAlert, ArrowUpRight, ChevronDown, FileCheck2, Scale } from "lucide-react";
import { VerdictEvent, EvidenceRef } from "@/types/investigation";
import { formatCurrencyMXN } from "@/lib/utils";
import { AudioPlayer } from "@/components/AudioPlayer";

interface VerdictCardProps {
  verdict: VerdictEvent;
  onEvidence: (ref: EvidenceRef) => void;
}

const riskLabels = { CRITICAL: "Critical", HIGH: "High", MEDIUM: "Medium", LOW: "Low" };

export const VerdictCard: React.FC<VerdictCardProps> = ({ verdict, onEvidence }) => {
  const [showEntities, setShowEntities] = useState(false);
  const simulated = verdict.source === "SIMULATION";
  const noPatterns = verdict.assessment_status === "NO_PATTERNS_DETECTED";
  const detected = verdict.assessment_status === "SUSPICIOUS_PATTERNS_DETECTED";
  const Icon = noPatterns ? ShieldCheck : detected ? ShieldAlert : FileCheck2;
  const accent = noPatterns ? "text-status-success" : detected ? "text-status-warning" : "text-brand-300";

  return <section className="review-enter overflow-hidden rounded-xl border border-surface-border bg-surface" aria-labelledby="assessment-title">
    {/* Header with Risk Level & Case ID */}
    <div className={`h-0.5 ${noPatterns ? "bg-status-success" : detected ? "bg-status-warning" : "bg-brand-500"}`} />
    <div className="space-y-6 p-5 sm:p-6">
      <div>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-xs text-muted"><FileCheck2 className="h-3.5 w-3.5" aria-hidden="true" /> {simulated ? "Simulated orchestrator assessment" : "Orchestrator assessment"}</span>
          <span className={`rounded border border-current/20 px-2 py-1 text-xs ${accent}`}>{riskLabels[verdict.risk_level]} {simulated ? "simulated risk" : "backend risk"}</span>
        </div>
        <Icon className={`mb-3 h-6 w-6 ${accent}`} strokeWidth={1.5} aria-hidden="true" />
        <h2 id="assessment-title" className="text-balance text-2xl font-medium leading-tight tracking-[-0.035em] text-foreground">{simulated ? "Example warning signs surfaced" : noPatterns ? "No suspicious patterns detected" : detected ? "Suspicious patterns detected" : "Backend assessment received"}</h2>
        <p className="mt-2 text-xs leading-5 text-muted">{simulated ? "Illustrative result for evaluating the interface. No fraud analysis was performed." : noPatterns ? "Within the configured checks. This is not a guarantee that fraud is absent." : "A review signal, not a determination of fraud."}</p>
      </div>
      {/* Grid of Key Forensic Indicators */}
      <dl className="grid gap-4 border-y border-surface-border py-5 sm:grid-cols-3">
        {/* Fraud Type & Volume */}
        <div><dt className="text-xs text-muted">Flagged volume (MXN)</dt><dd className="mt-2 break-words text-lg font-medium text-foreground">{formatCurrencyMXN(verdict.total_amount_mxn)}</dd></div>
        {/* Entities Involved */}
        <div><dt className="text-xs text-muted">Flagged accounts</dt><dd className="mt-2 text-lg font-medium text-foreground">{verdict.entities_involved.length.toLocaleString("en-US")}</dd></div>
        {/* Pruned Leads (Deterministic Graph Reduction) */}
        <div><dt className="text-xs text-muted">Links outside flagged set</dt><dd className="mt-2 text-lg font-medium text-foreground">{verdict.pruned_leads_count.toLocaleString("en-US")}</dd></div>
      </dl>
      {/* Audit Summary Narrative */}
      <div><h3 className="mb-2 text-sm font-medium text-foreground">What the evidence tells us</h3><p className="text-sm leading-7 text-muted">{verdict.audit_summary_text}</p>
        <button type="button" onClick={() => onEvidence({ kind: "overview", id: "risk", label: "Evidence overview" })} className="mt-3 flex min-h-11 items-center gap-2 text-xs text-brand-300 hover:text-brand-50">Inspect supporting evidence <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </div>
      {/* Legal & Regulatory Recommendation */}
      <div className="rounded-lg border border-surface-border bg-surface-deep p-4"><h3 className="mb-2 flex items-center gap-2 text-xs font-medium text-foreground"><Scale className="h-4 w-4 text-muted" aria-hidden="true" /> Recommended next step</h3><p className="text-sm leading-6 text-muted">{verdict.legal_recommendation}</p></div>
      <details className="text-xs text-muted"><summary className="min-h-11 cursor-pointer py-3 font-medium text-foreground">Scope and limitations</summary><ul className="list-disc space-y-2 pl-4 leading-6">{(verdict.limitations || ["The backend assessment must be checked against the dataset and supporting records. Its confidence score is not treated as a calibrated fraud probability."]).map(item => <li key={item}>{item}</li>)}</ul></details>
      {/* Collapsible Entities Breakdown */}
      <div className="border-t border-surface-border pt-2">
        <button type="button" onClick={() => setShowEntities(value => !value)} aria-expanded={showEntities} className="flex min-h-11 w-full items-center justify-between gap-3 text-left text-xs text-muted hover:text-foreground"><span>Flagged account identifiers ({verdict.entities_involved.length})</span><ChevronDown className={`h-4 w-4 transition-transform ${showEntities ? "rotate-180" : ""}`} aria-hidden="true" /></button>
        {showEntities && <div className="mt-2 max-h-40 overflow-y-auto rounded-lg bg-surface-deep p-3"><p className="break-all font-mono text-xs leading-7 text-muted">{verdict.entities_involved.length ? verdict.entities_involved.join(", ") : "No account identifiers were flagged."}</p></div>}
      </div>
      {/* Audio Dictation Player */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-border pt-5">{!simulated && <AudioPlayer textToSynthesize={verdict.audit_summary_text} label="Listen to summary" />}<time dateTime={verdict.completed_at} className="text-xs text-muted">Completed {new Date(verdict.completed_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</time></div>
    </div>
  </section>;
};
