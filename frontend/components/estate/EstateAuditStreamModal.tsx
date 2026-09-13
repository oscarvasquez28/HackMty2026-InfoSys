"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clock,
  Cpu,
  FileCheck,
  Loader2,
  Play,
  Scale,
  Search,
  ShieldAlert,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import { cn, formatCurrencyMXN } from "@/lib/utils";
import type {
  AgentId,
  AgentStatuses,
  AuditFeedItem,
  AuditProgress,
  FindingReviewedEvent,
  LeadReviewedEvent,
  ThoughtEvent,
  VerdictEvent,
} from "@/types/investigation";

interface EstateAuditStreamModalProps {
  isOpen: boolean;
  isStreaming: boolean;
  currentPhase: string;
  feed: AuditFeedItem[];
  progress: AuditProgress;
  streamStartedAt: number | null;
  lastEventAt: number | null;
  verdict: VerdictEvent | null;
  completedAudit: any | null;
  error: string | null;
  agentStatuses: AgentStatuses;
  onClose: () => void;
  onOpenCaseFile: (auditData: any) => void;
}

const AGENTS: Array<{ id: AgentId; label: string; role: string }> = [
  { id: "DATA_VALIDATION", label: "Validation", role: "Ingestion & Reconciliation 2%" },
  { id: "CIRCULAR_FLOWS", label: "Topology", role: "NetworkX Cycles & Mules" },
  { id: "RISK_REVIEW", label: "Adversarial", role: "Challenger vs Investigator" },
  { id: "ORCHESTRATOR", label: "Verdict", role: "Official Expert Judge" },
];

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  started: Play,
  delegated: Play,
  tool: Wrench,
  finding: Search,
  returned: CheckCircle2,
  synthesizing: Scale,
  fallback: AlertTriangle,
};

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function verdictTone(judgeVerdict: string): "guilty" | "acquitted" | "evaluated" {
  const verdict = judgeVerdict.toUpperCase();
  if (verdict.includes("ACQUIT") || verdict.includes("ABSUEL") || verdict.includes("DISMISS")) {
    return "acquitted";
  }
  if (verdict.includes("GUILT") || verdict.includes("CULPABLE") || verdict.includes("UPHELD")) {
    return "guilty";
  }
  return "evaluated";
}

const TONE_STYLES = {
  guilty: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  acquitted: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  evaluated: "border-amber-500/30 bg-amber-500/10 text-amber-300",
} as const;

const TONE_LABELS = {
  guilty: "Charge upheld",
  acquitted: "Dismissed",
  evaluated: "Evaluated",
} as const;

const SourceChip: React.FC<{ source?: string }> = ({ source }) => {
  if (source === "EXTERNAL") {
    return (
      <span className="rounded border border-brand-500/30 bg-brand-500/10 px-1.5 py-0.5 text-[10px] font-medium text-brand-300">
        n8n · LLM
      </span>
    );
  }
  if (source === "DETERMINISTIC") {
    return (
      <span className="rounded border border-surface-border bg-surface-raised px-1.5 py-0.5 text-[10px] font-medium text-muted">
        engine
      </span>
    );
  }
  return null;
};

const OnlineChip: React.FC<{ online: boolean }> = ({ online }) => (
  <span
    className={cn(
      "rounded border px-1.5 py-0.5 text-[10px] font-medium",
      online
        ? "border-brand-500/30 bg-brand-500/10 text-brand-300"
        : "border-surface-border bg-surface-raised text-muted"
    )}
  >
    {online ? "n8n · LLM" : "deterministic"}
  </span>
);

const ThoughtRow: React.FC<{ item: ThoughtEvent }> = ({ item }) => {
  const Icon = ACTION_ICONS[item.action ?? ""] ?? Activity;
  const agent = AGENTS.find((a) => a.id === item.agent_id);
  return (
    <div className="group rounded-lg border border-surface-border/60 bg-surface/40 p-3 transition-colors hover:border-brand-500/30">
      <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-brand-500/20 text-brand-300">
            <Icon className="h-3 w-3" />
          </span>
          <span className="rounded bg-brand-500/20 px-1.5 py-0.5 font-semibold text-brand-300">
            Step {item.step}
          </span>
          <span className="font-medium text-foreground">{item.phase}</span>
          {agent && <span className="text-[10px] text-muted">{agent.label}</span>}
          <SourceChip source={item.source} />
        </div>
        <span className="text-[10px] text-muted">
          {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : ""}
        </span>
      </div>
      <p className="font-sans text-xs leading-relaxed text-muted group-hover:text-foreground">
        {item.message}
      </p>
    </div>
  );
};

interface DetailCardProps {
  open: boolean;
  onToggle: () => void;
  receivedAt: number;
}

const FindingCard: React.FC<DetailCardProps & { item: FindingReviewedEvent }> = ({
  item,
  open,
  onToggle,
  receivedAt,
}) => {
  const tone = verdictTone(item.judge_verdict || "");
  const scheme = String(item.finding?.scheme_type ?? "scheme").replace(/_/g, " ");
  const amount = Number(item.finding?.peso_amount ?? 0);
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 text-xs">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 p-3 text-left"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-amber-500/20 text-amber-300">
            <ShieldAlert className="h-3 w-3" />
          </span>
          <span className="font-semibold text-amber-200">
            Finding {item.index}/{item.total || "?"}
          </span>
          <span className="font-medium capitalize text-foreground">{scheme}</span>
          {amount > 0 && (
            <span className="font-mono text-[11px] text-amber-200/90">
              {formatCurrencyMXN(amount)}
            </span>
          )}
          <span className={cn("rounded border px-1.5 py-0.5 text-[10px] font-semibold", TONE_STYLES[tone])}>
            {TONE_LABELS[tone]}
          </span>
          <OnlineChip online={item.is_online} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted">
            {new Date(receivedAt).toLocaleTimeString()}
          </span>
          <ChevronDown
            className={cn("h-4 w-4 shrink-0 text-muted transition-transform", open && "rotate-180")}
          />
        </div>
      </button>
      <p className="px-3 pb-2 font-sans text-xs text-amber-100/80">{item.message}</p>
      {open && (
        <div className="space-y-2 border-t border-amber-500/20 p-3 font-sans">
          {item.judge_verdict && (
            <div>
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                Judicial verdict
              </p>
              <p className="leading-relaxed text-foreground">{item.judge_verdict}</p>
            </div>
          )}
          {item.adversarial_review && (
            <div>
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                Adversarial defense review
              </p>
              <p className="leading-relaxed text-muted">{item.adversarial_review}</p>
            </div>
          )}
          {item.adversarial_evidences?.length > 0 && (
            <div>
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                Evidence cited ({item.adversarial_evidences.length})
              </p>
              <ul className="space-y-1">
                {item.adversarial_evidences.map((ev, i) => (
                  <li key={i} className="rounded border border-surface-border/60 bg-surface/40 px-2 py-1.5">
                    <span className="font-mono text-[10px] text-brand-300">
                      {ev.exhibit_id ?? `EX-${i + 1}`}
                      {ev.source_table ? ` · ${ev.source_table}` : ""}
                      {ev.record_id ? `.${ev.record_id}` : ""}
                    </span>
                    {ev.sentence && <p className="mt-0.5 text-muted">{ev.sentence}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const LeadCard: React.FC<DetailCardProps & { item: LeadReviewedEvent }> = ({
  item,
  open,
  onToggle,
  receivedAt,
}) => {
  const entity = String(item.lead?.entity ?? "Unknown entity");
  const signal = String(item.lead?.signal ?? "");
  return (
    <div className="rounded-lg border border-surface-border bg-surface/40 text-xs">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 p-3 text-left"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-emerald-500/20 text-emerald-300">
            <CheckCircle2 className="h-3 w-3" />
          </span>
          <span className="font-semibold text-foreground">
            Lead {item.index}/{item.total || "?"}
          </span>
          <span className="font-mono text-[11px] text-muted">{entity}</span>
          {signal && <span className="text-muted">{signal}</span>}
          <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
            Dismissed
          </span>
          <OnlineChip online={item.is_online} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted">
            {new Date(receivedAt).toLocaleTimeString()}
          </span>
          <ChevronDown
            className={cn("h-4 w-4 shrink-0 text-muted transition-transform", open && "rotate-180")}
          />
        </div>
      </button>
      <p className="px-3 pb-2 font-sans text-xs text-muted">{item.message}</p>
      {open && (
        <div className="space-y-2 border-t border-surface-border p-3 font-sans">
          {item.reason && (
            <div>
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                Reason to close
              </p>
              <p className="leading-relaxed text-foreground">{item.reason}</p>
            </div>
          )}
          {item.judge_verdict && (
            <div>
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                Judicial verdict
              </p>
              <p className="leading-relaxed text-muted">{item.judge_verdict}</p>
            </div>
          )}
          {item.closed_by && (
            <p className="text-[11px] text-muted">
              Closed by: <span className="text-foreground">{item.closed_by}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export const EstateAuditStreamModal: React.FC<EstateAuditStreamModalProps> = ({
  isOpen,
  isStreaming,
  currentPhase,
  feed,
  progress,
  streamStartedAt,
  lastEventAt,
  verdict,
  completedAudit,
  error,
  agentStatuses,
  onClose,
  onOpenCaseFile,
}) => {
  const streamEndRef = useRef<HTMLDivElement>(null);
  const [openCards, setOpenCards] = useState<Record<number, boolean>>({});
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (isOpen) {
      streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [feed, isOpen]);

  useEffect(() => {
    if (!isStreaming) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [isStreaming]);

  // The most recent finding/lead card stays expanded; earlier ones auto-collapse
  // unless the investigator explicitly toggled them.
  const latestDetailIdx = useMemo(() => {
    for (let i = feed.length - 1; i >= 0; i--) {
      if (feed[i].kind !== "thought") return i;
    }
    return -1;
  }, [feed]);

  const usesLLM = useMemo(
    () =>
      verdict?.source === "EXTERNAL" ||
      feed.some(
        (item) =>
          (item.kind === "thought" && item.data.source === "EXTERNAL") ||
          (item.kind !== "thought" && item.data.is_online)
      ),
    [feed, verdict]
  );

  const pendingLabel = useMemo(() => {
    if (!isStreaming) return null;
    const { findingsDone, findingsTotal, leadsDone, leadsTotal } = progress;
    if (findingsTotal > 0 && findingsDone < findingsTotal) {
      return `Awaiting adversarial review — finding ${findingsDone + 1}/${findingsTotal}`;
    }
    if (leadsTotal > 0 && leadsDone < leadsTotal) {
      return `Awaiting decoy lead review — lead ${leadsDone + 1}/${leadsTotal}`;
    }
    const lastThought = [...feed].reverse().find((f) => f.kind === "thought");
    const phase = String(
      lastThought && lastThought.kind === "thought" ? lastThought.data.phase : currentPhase
    ).toLowerCase();
    if (phase.includes("verdict")) return "Compiling judicial case file…";
    if (findingsTotal + leadsTotal > 0) return "Synthesizing expert verdict…";
    if (phase.includes("adversarial") || phase.includes("review")) {
      return "Awaiting adversarial review — finding 1";
    }
    return "Running deterministic detection engine…";
  }, [isStreaming, progress, feed, currentPhase]);

  const reviewedTotal = progress.findingsDone + progress.leadsDone;
  const expectedTotal = progress.findingsTotal + progress.leadsTotal;
  const progressPct = expectedTotal > 0 ? Math.round((reviewedTotal / expectedTotal) * 100) : 0;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-surface-border bg-surface-deep shadow-2xl shadow-black/60">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-border bg-surface/60 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-brand-500/30 bg-brand-500/10 text-brand-300">
              {isStreaming ? (
                <Loader2 className="h-5 w-5 animate-spin text-brand-400" />
              ) : completedAudit ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              ) : (
                <Activity className="h-5 w-5 text-brand-300" />
              )}
            </div>
            <div>
              <h3 className="text-base font-semibold tracking-tight text-foreground">
                Real-Time Forensic Audit
              </h3>
              <p className="flex items-center gap-2 font-mono text-xs text-muted">
                <span className="inline-block h-2 w-2 rounded-full bg-brand-400 animate-pulse" />
                {currentPhase}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {streamStartedAt !== null && (
              <span className="flex items-center gap-1.5 rounded border border-surface-border bg-surface-raised px-2 py-1 font-mono text-[11px] text-muted">
                <Clock className="h-3 w-3" />
                {formatElapsed(now - streamStartedAt)}
              </span>
            )}
            {(feed.length > 0 || verdict) && (
              <span
                className={cn(
                  "rounded border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider",
                  usesLLM
                    ? "border-brand-500/30 bg-brand-500/10 text-brand-300"
                    : "border-surface-border bg-surface-raised text-muted"
                )}
              >
                {usesLLM ? "n8n · LLM" : "Deterministic"}
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted hover:bg-surface-raised hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Agent Roster Bar */}
        <div className="grid grid-cols-2 gap-2 border-b border-surface-border bg-surface/30 p-3 sm:grid-cols-4">
          {AGENTS.map((agent) => {
            const status = agentStatuses[agent.id] || "waiting";
            const isReviewing = status === "reviewing";
            const isDone = status === "complete" || status === "returned";

            return (
              <div
                key={agent.id}
                className={`flex flex-col justify-center rounded-lg border px-3 py-2 text-xs transition-colors ${
                  isReviewing
                    ? "border-brand-500/40 bg-brand-500/10 text-brand-200"
                    : isDone
                    ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
                    : "border-surface-border bg-surface-raised/40 text-muted"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground">{agent.label}</span>
                  {isReviewing ? (
                    <span className="h-2 w-2 rounded-full bg-brand-400 animate-ping" />
                  ) : isDone ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-muted/40" />
                  )}
                </div>
                <span className="truncate text-[10px] text-muted">{agent.role}</span>
              </div>
            );
          })}
        </div>

        {/* Review progress */}
        {(expectedTotal > 0 || isStreaming) && (
          <div className="border-b border-surface-border bg-surface/30 px-6 py-2.5">
            <div className="flex items-center justify-between text-[11px] text-muted">
              <span>
                Findings reviewed:{" "}
                <span className="font-mono text-foreground">
                  {progress.findingsDone}/{progress.findingsTotal || "?"}
                </span>
                {" · "}Leads dismissed:{" "}
                <span className="font-mono text-foreground">
                  {progress.leadsDone}/{progress.leadsTotal || "?"}
                </span>
              </span>
              <span className="font-mono">{expectedTotal > 0 ? `${progressPct}%` : "…"}</span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-raised">
              <div
                className={cn(
                  "h-full rounded-full bg-brand-500 transition-all duration-500",
                  expectedTotal === 0 && "animate-pulse"
                )}
                style={{ width: expectedTotal > 0 ? `${progressPct}%` : "100%" }}
              />
            </div>
          </div>
        )}

        {/* Chain-of-thought feed */}
        <div className="flex-1 space-y-3 overflow-y-auto p-4 font-mono text-xs">
          {feed.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted">
              <Loader2 className="mb-3 h-8 w-8 animate-spin text-brand-400" />
              <p>Starting agents and loading transaction topology...</p>
            </div>
          )}

          {feed.map((item, idx) => {
            if (item.kind === "thought") {
              return <ThoughtRow key={idx} item={item.data} />;
            }
            const open = openCards[idx] ?? idx === latestDetailIdx;
            const toggle = () =>
              setOpenCards((prev) => ({
                ...prev,
                [idx]: !(prev[idx] ?? idx === latestDetailIdx),
              }));
            return item.kind === "finding" ? (
              <FindingCard
                key={idx}
                item={item.data}
                open={open}
                onToggle={toggle}
                receivedAt={item.receivedAt}
              />
            ) : (
              <LeadCard
                key={idx}
                item={item.data}
                open={open}
                onToggle={toggle}
                receivedAt={item.receivedAt}
              />
            );
          })}

          {/* In-flight activity indicator while the stream is open */}
          {isStreaming && pendingLabel && (
            <div className="flex items-center gap-3 rounded-lg border border-brand-500/30 bg-brand-500/5 p-3">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-400" />
              <div className="flex-1">
                <p className="font-sans text-xs text-brand-200">{pendingLabel}</p>
                {lastEventAt !== null && now - lastEventAt > 15000 && (
                  <p className="mt-0.5 text-[10px] text-muted">
                    No updates for {formatElapsed(now - lastEventAt)} — the n8n agent can take a
                    while per review.
                  </p>
                )}
              </div>
              <Cpu className="h-4 w-4 shrink-0 animate-pulse text-brand-400/60" />
            </div>
          )}

          {/* Error notice if any */}
          {error && (
            <div className="flex items-start gap-3 rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
              <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
              <div>
                <p className="font-semibold">Error during the audit</p>
                <p className="mt-1 font-sans text-rose-200/80">{error}</p>
              </div>
            </div>
          )}

          {/* Final Verdict Banner */}
          {verdict && (
            <div className="mt-4 rounded-xl border border-brand-500/40 bg-brand-500/10 p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  <span className="text-sm font-semibold text-foreground">
                    Expert Verdict Concluded
                  </span>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    verdict.risk_level === "CRITICAL"
                      ? "border border-rose-500/30 bg-rose-500/20 text-rose-300"
                      : "border border-emerald-500/30 bg-emerald-500/20 text-emerald-300"
                  }`}
                >
                  Risk Level: {verdict.risk_level}
                </span>
              </div>

              {verdict.fraud_type && (
                <p className="mt-2 font-sans text-xs font-medium text-brand-200">
                  {verdict.fraud_type}
                </p>
              )}

              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-surface-border/50 pt-3 text-xs">
                <div>
                  <span className="block text-muted">Flagged Volume:</span>
                  <span className="text-sm font-semibold text-foreground">
                    {formatCurrencyMXN(verdict.total_amount_mxn)}
                  </span>
                </div>
                <div>
                  <span className="block text-muted">Discarded Leads:</span>
                  <span className="text-sm font-semibold text-foreground">
                    {verdict.pruned_leads_count} leads
                  </span>
                </div>
              </div>

              <p className="mt-3 font-sans text-xs leading-relaxed text-muted">
                {verdict.audit_summary_text}
              </p>
            </div>
          )}

          <div ref={streamEndRef} />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-surface-border bg-surface/60 px-6 py-4">
          <div className="text-xs text-muted">
            {isStreaming ? (
              <span className="flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 animate-pulse text-brand-400" />
                Deterministic execution in progress...
              </span>
            ) : completedAudit ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                Judicial case file ready for inspection
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="app-button text-xs"
            >
              Close
            </button>

            {completedAudit && (
              <button
                type="button"
                onClick={() => onOpenCaseFile(completedAudit)}
                className="app-primary flex items-center gap-2 py-2 px-4 text-xs font-semibold shadow-lg shadow-brand-500/20"
              >
                <FileCheck className="h-4 w-4" />
                View Full Case File
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
