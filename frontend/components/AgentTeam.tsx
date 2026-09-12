"use client";

import React from "react";
import { ScanLine, GitCompareArrows, Route, ShieldCheck, Check, CornerUpLeft } from "lucide-react";
import { AgentId, AgentStatuses } from "@/types/investigation";

export const REVIEW_TEAM = [
  { id: "DATA_VALIDATION", name: "Data validation", brief: "Input & assumptions", icon: ScanLine },
  { id: "CIRCULAR_FLOWS", name: "Circular flows", brief: "Connected account paths", icon: GitCompareArrows },
  { id: "PASSTHROUGH", name: "Pass-through", brief: "Flow matching & timing", icon: Route },
  { id: "RISK_REVIEW", name: "Risk review", brief: "Evidence & limitations", icon: ShieldCheck },
] as const;

export function getAgentName(id?: AgentId): string {
  return REVIEW_TEAM.find(agent => agent.id === id)?.name || "Orchestrator";
}

interface AgentTeamProps {
  statuses: AgentStatuses;
  selectedAgent: AgentId | null;
  onSelect: (agent: AgentId) => void;
  hasCase: boolean;
}

export const AgentTeam: React.FC<AgentTeamProps> = ({ statuses, selectedAgent, onSelect, hasCase }) => (
  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Specialist review team">
    {REVIEW_TEAM.map(agent => {
      const Icon = agent.icon;
      const status = statuses[agent.id];
      const active = status === "reviewing";
      const returned = status === "returned";
      return (
        <button key={agent.id} type="button" onClick={() => onSelect(agent.id)} aria-pressed={selectedAgent === agent.id}
          className={`group min-w-0 rounded-lg border p-3 text-left transition-colors duration-200 ${selectedAgent === agent.id ? "border-brand-500/70 bg-surface-blue" : "border-surface-border bg-surface/50 hover:border-brand-500/40 hover:bg-surface-raised"}`}>
          <div className="mb-4 flex items-center justify-between">
            <Icon className={`h-5 w-5 ${active ? "text-brand-300" : "text-muted"}`} strokeWidth={1.5} aria-hidden="true" />
            {returned && <CornerUpLeft className="h-3.5 w-3.5 text-status-success" aria-hidden="true" />}
            {active && <span className="review-pulse h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden="true" />}
          </div>
          <span className="block text-xs font-medium text-foreground">{agent.name}</span>
          <span className="mt-1 block text-xs leading-5 text-muted">{agent.brief}</span>
          <span className={`mt-3 flex items-center gap-1.5 text-xs ${returned ? "text-status-success" : active ? "text-brand-300" : "text-muted"}`}>
            {returned && <Check className="h-3 w-3" aria-hidden="true" />}
            {returned ? "Findings returned" : active ? "Reviewing findings" : status === "available" ? "Evidence available" : status === "interrupted" ? "Interrupted" : hasCase ? "Awaiting update" : "Ready for a dataset"}
          </span>
        </button>
      );
    })}
  </div>
);
