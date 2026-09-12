"use client";

import React, { useMemo } from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  CornerUpLeft,
  Cpu,
  Layers,
  Play,
  RotateCcw,
  Search,
  Wrench,
} from "lucide-react";
import { AgentId, AgentStatuses, ThoughtEvent } from "@/types/investigation";
import { REVIEW_TEAM, getAgentName } from "@/components/AgentTeam";

interface AgentSwimlanesProps {
  statuses: AgentStatuses;
  thoughts: ThoughtEvent[];
  selectedStepId: string | null;
  onSelectStep: (stepId: string) => void;
  selectedAgent: AgentId | null;
  onSelectAgent: (agent: AgentId) => void;
  isRunning: boolean;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  hasCase: boolean;
  verdictReady: boolean;
}

export const AgentSwimlanes: React.FC<AgentSwimlanesProps> = ({
  statuses,
  thoughts,
  selectedStepId,
  onSelectStep,
  selectedAgent,
  onSelectAgent,
  isRunning,
  isCollapsed,
  onToggleCollapse,
  hasCase,
  verdictReady,
}) => {
  // Group thoughts by agent
  const agentTracks = useMemo(() => {
    const map: Record<AgentId, ThoughtEvent[]> = {
      DATA_VALIDATION: [],
      CIRCULAR_FLOWS: [],
      PASSTHROUGH: [],
      RISK_REVIEW: [],
      ORCHESTRATOR: [],
    };
    thoughts.forEach((thought) => {
      if (thought.agent_id && map[thought.agent_id]) {
        map[thought.agent_id].push(thought);
      }
    });
    return map;
  }, [thoughts]);

  const returnedCount = REVIEW_TEAM.filter(
    (agent) => statuses[agent.id] === "returned"
  ).length;

  // Render collapsed summary bar if collapsed (typically after verdict is ready)
  if (isCollapsed && hasCase) {
    return (
      <div className="rounded-xl border border-surface-border bg-surface/70 p-4 transition-all">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-brand-500/40 bg-surface-blue text-brand-300">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">
                  Orchestrator Execution Schedule
                </span>
                <span className="rounded-md border border-status-success/30 bg-status-success/10 px-2 py-0.5 text-[10px] font-medium text-status-success">
                  {returnedCount}/4 Reviews Complete
                </span>
              </div>
              <p className="text-xs text-muted">
                Lanes collapsed to emphasize the final assessment. Total {thoughts.length} timeline milestones recorded.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="app-button flex items-center gap-1.5 text-xs text-brand-300 hover:text-foreground"
          >
            <span>Expand schedule</span>
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <section
      className="overflow-hidden rounded-xl border border-surface-border bg-surface/80 shadow-sm"
      aria-label="Investigation execution swimlanes"
    >
      {/* Board Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border bg-surface-deep/80 px-4 py-3.5 sm:px-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md border border-brand-500/30 bg-surface-blue text-brand-300">
            <Layers className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Investigation Schedule & Activity Tracks
            </h2>
            <p className="text-[11px] text-muted">
              Shared time axis • Concurrent execution with dependency scheduling
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted">
            {isRunning && (
              <span className="review-pulse h-2 w-2 rounded-full bg-brand-500" aria-hidden="true" />
            )}
            {returnedCount === 4
              ? "All 4 reviews returned"
              : isRunning
              ? `${returnedCount}/4 specialists returned`
              : hasCase
              ? "Schedule initialized"
              : "Awaiting dataset"}
          </span>

          {verdictReady && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="flex items-center gap-1 text-xs text-muted hover:text-foreground"
              aria-label="Collapse execution schedule"
            >
              <span>Collapse</span>
              <ChevronUp className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Time Axis Bar */}
      <div className="grid grid-cols-[140px_minmax(0,1fr)] sm:grid-cols-[180px_minmax(0,1fr)] md:grid-cols-[210px_minmax(0,1fr)] border-b border-surface-border/60 bg-surface-deep/40 text-[10px] text-muted">
        <div className="border-r border-surface-border/60 px-3 py-1.5 font-mono uppercase tracking-wider">
          Specialist Track
        </div>
        <div className="flex items-center justify-between px-4 py-1.5 font-mono">
          <span>T=0.0s (Start)</span>
          <span className="hidden sm:inline">T=1.5s (Parallel Execution)</span>
          <span className="hidden md:inline">T=3.0s (Dependency Resolution)</span>
          <span>T=5.0s (Return)</span>
        </div>
      </div>

      {/* Horizontal Lanes for the 4 Specialists */}
      <div className="divide-y divide-surface-border/60">
        {REVIEW_TEAM.map((agent) => {
          const Icon = agent.icon;
          const status = statuses[agent.id];
          const isReviewing = status === "reviewing";
          const isReturned = status === "returned";
          const trackSteps = agentTracks[agent.id] || [];
          const isAgentSelected = selectedAgent === agent.id;

          return (
            <div
              key={agent.id}
              className={`grid grid-cols-[140px_minmax(0,1fr)] sm:grid-cols-[180px_minmax(0,1fr)] md:grid-cols-[210px_minmax(0,1fr)] transition-colors ${
                isAgentSelected ? "bg-surface-blue/50" : "hover:bg-surface-raised/40"
              }`}
            >
              {/* Left Lane Header (Agent Identity) */}
              <div
                onClick={() => onSelectAgent(agent.id)}
                className="flex cursor-pointer flex-col justify-between border-r border-surface-border/60 p-3 select-none"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <Icon
                      className={`h-4 w-4 shrink-0 ${
                        isReviewing ? "text-brand-300" : isReturned ? "text-status-success" : "text-muted"
                      }`}
                      strokeWidth={1.75}
                    />
                    <span className="truncate text-xs font-medium text-foreground">
                      {agent.name}
                    </span>
                  </div>
                  <span className="mt-0.5 hidden text-[10px] leading-tight text-muted sm:block">
                    {agent.brief}
                  </span>
                </div>

                <div className="mt-2 flex items-center gap-1.5 text-[10px]">
                  {isReturned ? (
                    <span className="flex items-center gap-1 text-status-success">
                      <Check className="h-3 w-3" /> Returned
                    </span>
                  ) : isReviewing ? (
                    <span className="flex items-center gap-1 text-brand-300">
                      <span className="review-pulse h-1.5 w-1.5 rounded-full bg-brand-500" />
                      Running
                    </span>
                  ) : status === "available" ? (
                    <span className="text-muted">Available</span>
                  ) : (
                    <span className="text-muted/60">Waiting</span>
                  )}
                </div>
              </div>

              {/* Right Track (Timeline Chips along Time Axis) */}
              <div
                tabIndex={0}
                aria-label={`${agent.name} track steps`}
                className="flex min-h-[72px] items-center gap-2 overflow-x-auto p-3 overscroll-x-contain"
              >
                {trackSteps.length === 0 ? (
                  <div className="flex h-full items-center text-xs text-muted/60 italic font-mono pl-1">
                    {status === "waiting"
                      ? agent.id === "RISK_REVIEW"
                        ? "Awaiting earlier pattern findings (dependency scheduled)..."
                        : "Awaiting dispatch..."
                      : "No activity recorded."}
                  </div>
                ) : (
                  trackSteps.map((step, idx) => {
                    const isSelected = selectedStepId === step.event_id;
                    const isLastStep = idx === trackSteps.length - 1 && isReviewing;
                    const isTool = step.action === "tool" || !!step.tool_call;
                    const isFinding = step.action === "finding";
                    const isReturn = step.action === "returned";

                    let chipStyle =
                      "border-surface-border bg-surface-deep text-muted hover:border-brand-500/40";
                    if (isSelected) {
                      chipStyle =
                        "border-brand-500 bg-surface-blue text-brand-50 ring-1 ring-brand-500 shadow-sm";
                    } else if (isTool) {
                      chipStyle =
                        "border-brand-500/30 bg-surface/90 text-brand-300 hover:border-brand-500/60";
                    } else if (isFinding) {
                      chipStyle =
                        "border-status-warning/40 bg-status-warning/5 text-status-warning hover:border-status-warning/70";
                    } else if (isReturn) {
                      chipStyle =
                        "border-status-success/40 bg-status-success/5 text-status-success hover:border-status-success/70";
                    }

                    return (
                      <button
                        key={step.event_id || idx}
                        type="button"
                        onClick={() => onSelectStep(step.event_id || "")}
                        className={`group relative flex shrink-0 items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition-all ${chipStyle} ${
                          isLastStep ? "animate-pulse" : ""
                        }`}
                      >
                        {/* Chip Icon */}
                        {isReturn ? (
                          <CornerUpLeft className="h-3.5 w-3.5 shrink-0 text-status-success" />
                        ) : isFinding ? (
                          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-status-warning" />
                        ) : isTool ? (
                          <Cpu className="h-3.5 w-3.5 shrink-0 text-brand-500" />
                        ) : (
                          <Play className="h-3 w-3 shrink-0 text-muted" />
                        )}

                        {/* Chip Label & Metric */}
                        <div className="flex flex-col">
                          <span className="font-medium truncate max-w-[130px] sm:max-w-[160px]">
                            {step.headline || step.phase}
                          </span>
                          {step.metric && (
                            <span className="text-[10px] font-mono opacity-80 truncate max-w-[130px] sm:max-w-[160px]">
                              {step.metric}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Orchestrator Hand-off / Synthesis Footer Bar */}
      {agentTracks.ORCHESTRATOR.length > 0 && (
        <div className="flex items-center justify-between border-t border-surface-border bg-surface-deep/60 px-4 py-2 text-xs text-muted">
          <div className="flex items-center gap-2 truncate">
            <span className="font-mono text-[10px] uppercase text-brand-300">Orchestrator:</span>
            <span className="truncate text-foreground/80">
              {agentTracks.ORCHESTRATOR[agentTracks.ORCHESTRATOR.length - 1].message}
            </span>
          </div>
          <button
            type="button"
            onClick={() =>
              onSelectStep(
                agentTracks.ORCHESTRATOR[agentTracks.ORCHESTRATOR.length - 1].event_id || ""
              )
            }
            className="shrink-0 text-brand-300 hover:text-brand-50 ml-2"
          >
            Inspect
          </button>
        </div>
      )}
    </section>
  );
};
