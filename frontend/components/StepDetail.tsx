"use client";

import React from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CornerUpLeft,
  Cpu,
  Layers,
  Search,
  Wrench,
} from "lucide-react";
import { EvidenceRef, ThoughtEvent } from "@/types/investigation";
import { REVIEW_TEAM, getAgentName } from "@/components/AgentTeam";

interface StepDetailProps {
  step: ThoughtEvent | null;
  allSteps: ThoughtEvent[];
  onSelectStep: (stepId: string) => void;
  onEvidence: (ref: EvidenceRef) => void;
  isStreaming?: boolean;
}

export const StepDetail: React.FC<StepDetailProps> = ({
  step,
  allSteps,
  onSelectStep,
  onEvidence,
  isStreaming = false,
}) => {
  if (!step) {
    return (
      <div className="rounded-xl border border-surface-border bg-surface/50 p-5 text-center text-xs text-muted">
        <p>Select any step on the investigation timeline above to inspect its execution narrative and evidence links.</p>
      </div>
    );
  }

  const agentMeta = REVIEW_TEAM.find((m) => m.id === step.agent_id);
  const AgentIcon = agentMeta?.icon || Layers;
  const currentIndex = allSteps.findIndex((s) => s.event_id === step.event_id);
  const canPrev = currentIndex > 0;
  const canNext = currentIndex >= 0 && currentIndex < allSteps.length - 1;

  // Determine badge style and label
  const isTool = step.action === "tool" || !!step.tool_call;
  const isFinding = step.action === "finding";
  const isReturned = step.action === "returned";
  const isStarted = step.action === "started" || step.action === "delegated";
  const isSynth = step.action === "synthesizing";

  let badgeText = "Timeline Step";
  let badgeColor = "border-surface-border text-muted bg-surface-raised";

  if (isTool) {
    badgeText = "Tool Execution";
    badgeColor = "border-brand-500/30 text-brand-300 bg-surface-blue";
  } else if (isFinding) {
    badgeText = "Finding Surfaced";
    badgeColor = "border-status-warning/30 text-status-warning bg-status-warning/5";
  } else if (isReturned) {
    badgeText = "Review Returned";
    badgeColor = "border-status-success/30 text-status-success bg-status-success/5";
  } else if (isStarted) {
    badgeText = "Specialist Dispatched";
    badgeColor = "border-brand-500/20 text-brand-300 bg-surface/80";
  } else if (isSynth) {
    badgeText = "Orchestrator Synthesis";
    badgeColor = "border-brand-500/40 text-brand-50 bg-brand-500/20";
  }

  const timeStr = new Date(step.timestamp).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return (
    <article
      className="review-enter rounded-xl border border-surface-border bg-surface/80 p-4 sm:p-5 transition-all shadow-sm"
      aria-label="Investigation step detail"
    >
      {/* Top Meta Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-surface-border bg-surface-raised text-brand-300">
            <AgentIcon className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-foreground">
                {getAgentName(step.agent_id)}
              </span>
              <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${badgeColor}`}>
                {badgeText}
              </span>
            </div>
            <p className="text-[11px] text-muted">{step.phase}</p>
          </div>
        </div>

        {/* Step index & pagination */}
        <div className="flex items-center gap-2">
          {currentIndex >= 0 && (
            <span className="text-[11px] font-mono text-muted">
              Step {currentIndex + 1} of {allSteps.length}
            </span>
          )}
          <div className="flex items-center gap-1 rounded-lg border border-surface-border bg-surface-deep p-0.5">
            <button
              type="button"
              disabled={!canPrev}
              onClick={() => canPrev && onSelectStep(allSteps[currentIndex - 1].event_id || "")}
              className="flex h-7 w-7 items-center justify-center rounded text-muted hover:text-foreground disabled:opacity-30"
              aria-label="Previous step"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={!canNext}
              onClick={() => canNext && onSelectStep(allSteps[currentIndex + 1].event_id || "")}
              className="flex h-7 w-7 items-center justify-center rounded text-muted hover:text-foreground disabled:opacity-30"
              aria-label="Next step"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Narrative Area */}
      <div className="mt-4 space-y-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-base font-medium text-foreground tracking-tight">
            {step.headline || step.phase}
          </h3>
          {step.metric && (
            <span className="rounded-md border border-brand-500/25 bg-surface-blue px-2.5 py-1 font-mono text-xs font-medium text-brand-300">
              {step.metric}
            </span>
          )}
        </div>

        <p className="text-sm leading-relaxed text-muted">{step.message}</p>

        {/* Tool Call Specific Capability + Outcome Card */}
        {step.tool_call && (
          <div className="rounded-lg border border-surface-border bg-surface-deep/90 p-3.5 text-xs">
            <div className="flex items-center justify-between gap-2 border-b border-surface-border/50 pb-2">
              <div className="flex items-center gap-2 font-mono text-brand-300">
                <Cpu className="h-3.5 w-3.5 text-brand-500" />
                <span>Tool: {step.tool_call.name}</span>
              </div>
              {step.tool_call.duration_ms !== undefined && (
                <span className="text-[10px] text-muted">
                  ~{step.tool_call.duration_ms}ms simulated
                </span>
              )}
            </div>
            <div className="mt-2 text-foreground/90">
              <span className="text-muted">Outcome: </span>
              <span className="font-medium text-foreground">{step.tool_call.outcome}</span>
            </div>
          </div>
        )}

        {/* Interactive Evidence Links */}
        {!!step.evidence_refs?.length && (
          <div className="pt-2">
            <span className="mb-2 block text-[11px] font-medium text-muted">
              Connected Evidence Available:
            </span>
            <div className="flex flex-wrap gap-2">
              {step.evidence_refs.map((ref) => (
                <button
                  key={`${ref.kind}:${ref.id}`}
                  type="button"
                  onClick={() => onEvidence(ref)}
                  className="inline-flex items-center gap-2 rounded-lg border border-brand-500/35 bg-surface-blue px-3 py-2 text-xs font-medium text-brand-300 transition-colors hover:border-brand-500/60 hover:bg-surface-raised"
                >
                  <Search className="h-3.5 w-3.5" />
                  <span>Inspect: {ref.label}</span>
                  <ArrowUpRight className="h-3.5 w-3.5 opacity-70" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer Timestamp */}
      <div className="mt-4 flex items-center justify-between border-t border-surface-border/60 pt-3 text-[11px] text-muted">
        <span>Attribution: {getAgentName(step.agent_id)}</span>
        <time dateTime={step.timestamp} className="font-mono">
          {timeStr}
        </time>
      </div>
    </article>
  );
};
