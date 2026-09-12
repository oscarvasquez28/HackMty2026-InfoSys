"use client";

import React, { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CornerUpLeft,
  Cpu,
  FileSearch,
  Layers,
  Search,
  ShieldAlert,
  Users,
} from "lucide-react";
import {
  AgentDecision,
  AgentId,
  AgentStatuses,
  EvidenceRef,
  UploadResponse,
} from "@/types/investigation";
import { REVIEW_TEAM, getAgentName } from "@/components/AgentTeam";
import { EvidenceInspector } from "@/components/EvidenceInspector";

interface TeamDecisionRosterProps {
  statuses: AgentStatuses;
  agentDecisions: Record<AgentId, AgentDecision>;
  selectedAgent: AgentId | null;
  onSelectAgent: (agent: AgentId) => void;
  currentCase: UploadResponse | null;
  selectedEvidence: EvidenceRef | null;
  onEvidence: (ref: EvidenceRef) => void;
  hasCase: boolean;
}

export const TeamDecisionRoster: React.FC<TeamDecisionRosterProps> = ({
  statuses,
  agentDecisions,
  selectedAgent,
  onSelectAgent,
  currentCase,
  selectedEvidence,
  onEvidence,
  hasCase,
}) => {
  const [activeTab, setActiveTab] = useState<"decisions" | "evidence">("decisions");

  const handleInspectDecisionEvidence = (ref: EvidenceRef) => {
    onEvidence(ref);
    setActiveTab("evidence");
  };

  return (
    <aside
      className="overflow-hidden rounded-xl border border-surface-border bg-surface/80 shadow-sm"
      aria-label="Specialist team decisions and dataset evidence"
    >
      {/* Top Tab Bar: Toggle between Decisions and Evidence */}
      <div className="flex border-b border-surface-border bg-surface-deep/80 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab("decisions")}
          className={`flex min-h-11 flex-1 items-center justify-center gap-2 border-b-2 px-3 font-medium transition-colors ${
            activeTab === "decisions"
              ? "border-brand-500 text-brand-300 bg-surface/40"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <Users className="h-3.5 w-3.5" />
          <span>Team Decisions</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("evidence")}
          className={`flex min-h-11 flex-1 items-center justify-center gap-2 border-b-2 px-3 font-medium transition-colors ${
            activeTab === "evidence"
              ? "border-brand-500 text-brand-300 bg-surface/40"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <FileSearch className="h-3.5 w-3.5" />
          <span>Dataset Evidence</span>
        </button>
      </div>

      {/* TAB 1: Specialist Team & Active Decisions */}
      {activeTab === "decisions" && (
        <div className="p-4 space-y-3.5">
          <div className="flex items-center justify-between border-b border-surface-border/60 pb-2.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Specialist Roster
            </span>
            <span className="text-[11px] font-mono text-muted">
              {REVIEW_TEAM.filter((a) => statuses[a.id] === "returned").length}/4 returned
            </span>
          </div>

          <div className="space-y-3">
            {REVIEW_TEAM.map((agent) => {
              const Icon = agent.icon;
              const status = statuses[agent.id];
              const decision = agentDecisions[agent.id];
              const isReviewing = status === "reviewing";
              const isReturned = status === "returned";
              const isSelected = selectedAgent === agent.id;

              return (
                <div
                  key={agent.id}
                  onClick={() => onSelectAgent(agent.id)}
                  className={`cursor-pointer rounded-lg border p-3 transition-all ${
                    isSelected
                      ? "border-brand-500/70 bg-surface-blue"
                      : "border-surface-border bg-surface-deep/50 hover:border-brand-500/40 hover:bg-surface-raised"
                  }`}
                >
                  {/* Agent Header */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded border border-surface-border bg-surface text-brand-300">
                        <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </div>
                      <span className="text-xs font-semibold text-foreground">
                        {agent.name}
                      </span>
                    </div>

                    {/* Status badge */}
                    {isReturned ? (
                      <span className="flex items-center gap-1 rounded bg-status-success/10 px-1.5 py-0.5 text-[10px] font-medium text-status-success">
                        <Check className="h-2.5 w-2.5 stroke-[2.5]" />
                        Returned
                      </span>
                    ) : isReviewing ? (
                      <span className="flex items-center gap-1 rounded bg-brand-500/15 px-1.5 py-0.5 text-[10px] font-medium text-brand-300">
                        <span className="review-pulse h-1.5 w-1.5 rounded-full bg-brand-500" />
                        Active
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono text-muted/60">Waiting</span>
                    )}
                  </div>

                  {/* Current Task */}
                  <div className="mt-2 text-[11px] text-muted">
                    <span className="font-mono text-[10px] uppercase text-muted/70 mr-1.5">
                      Task:
                    </span>
                    <span>{decision?.task || "Awaiting dispatch"}</span>
                  </div>

                  {/* Current Decision / Finding Callout */}
                  {decision?.decision && (
                    <div className="mt-2 rounded border border-surface-border/70 bg-surface/90 p-2 text-[11px]">
                      <div className="flex items-start justify-between gap-1">
                        <span className="font-mono text-[10px] uppercase text-brand-300">
                          Decision / Output:
                        </span>
                        {decision.metric && (
                          <span className="rounded bg-surface-raised px-1 font-mono text-[9px] text-muted">
                            {decision.metric}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-foreground/90 leading-relaxed">
                        {decision.decision}
                      </p>

                      {/* Quick Inspect Button */}
                      {decision.evidence_ref && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (decision.evidence_ref) {
                              handleInspectDecisionEvidence(decision.evidence_ref);
                            }
                          }}
                          className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-medium text-brand-300 hover:text-brand-50"
                        >
                          <span>Inspect finding</span>
                          <ArrowRight className="h-2.5 w-2.5" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: Embedded Dataset Evidence Inspector */}
      {activeTab === "evidence" && (
        <div>
          <EvidenceInspector
            key={currentCase?.case_id || "empty"}
            currentCase={currentCase}
            selected={selectedEvidence}
            onSelect={onEvidence}
          />
        </div>
      )}
    </aside>
  );
};
