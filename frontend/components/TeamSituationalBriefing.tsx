"use client";

import React from "react";
import {
  Activity,
  AlertTriangle,
  Check,
  Cpu,
  Layers,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
} from "lucide-react";
import { TeamSituationalState } from "@/types/investigation";
import { useAudioStream } from "@/hooks/useAudioStream";

interface TeamSituationalBriefingProps {
  situationalState: TeamSituationalState;
  hasCase: boolean;
  isRunning: boolean;
  verdictReady: boolean;
}

const STAGES = [
  { id: "ingestion", label: "Ingestion & Schema", short: "Ingest" },
  { id: "discovery", label: "Pattern Discovery", short: "Discovery" },
  { id: "synthesis", label: "Risk Synthesis", short: "Synthesis" },
  { id: "verdict", label: "Adjudication", short: "Verdict" },
] as const;

export const TeamSituationalBriefing: React.FC<TeamSituationalBriefingProps> = ({
  situationalState,
  hasCase,
  isRunning,
  verdictReady,
}) => {
  const { isPlaying, isLoading, error, notice, playAudio, stopAudio } = useAudioStream();

  const handleAudioToggle = () => {
    if (isPlaying || isLoading) {
      stopAudio();
    } else if (situationalState.executiveSummary) {
      playAudio(situationalState.executiveSummary);
    }
  };

  return (
    <section
      className="space-y-5"
      aria-label="Whole-team fraud investigation progress"
    >
      {/* 1. Clear Line of Progress */}
      <div className="rounded-xl border border-surface-border bg-surface-deep/80 p-4 sm:p-5">
        <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-brand-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Investigation Progress
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs text-muted">
            <span>{situationalState.stageTitle}</span>
            <span className="rounded-full border border-surface-border bg-surface-raised px-2 py-0.5 text-[11px] text-brand-300">
              {situationalState.progressPct}%
            </span>
          </div>
        </div>

        {/* Multi-stage Progress Stepper Track */}
        <div className="relative mt-2">
          {/* Background track line */}
          <div className="absolute left-0 top-3.5 h-1 w-full -translate-y-1/2 rounded-full bg-surface-raised" />
          {/* Active progress fill */}
          <div
            className="absolute left-0 top-3.5 h-1 -translate-y-1/2 rounded-full bg-gradient-to-r from-brand-600 via-brand-500 to-brand-300 transition-all duration-500"
            style={{ width: `${situationalState.progressPct}%` }}
          />

          {/* Stepper Nodes */}
          <div className="relative flex justify-between">
            {STAGES.map((s, idx) => {
              const isPast = situationalState.stageIndex > idx;
              const isCurrent = situationalState.stageIndex === idx;
              const isFuture = situationalState.stageIndex < idx;

              let nodeClass = "border-surface-border bg-surface text-muted";
              if (isPast) {
                nodeClass = "border-status-success bg-status-success/15 text-status-success";
              } else if (isCurrent) {
                nodeClass =
                  "border-brand-500 bg-surface-blue text-brand-300 ring-4 ring-brand-500/20 shadow-md";
              }

              return (
                <div key={s.id} className="flex flex-col items-center">
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-semibold transition-all ${nodeClass}`}
                  >
                    {isPast ? (
                      <Check className="h-3.5 w-3.5 stroke-[2.5]" />
                    ) : isCurrent && isRunning ? (
                      <span className="review-pulse h-2 w-2 rounded-full bg-brand-500" />
                    ) : (
                      idx + 1
                    )}
                  </div>
                  <span
                    className={`mt-2 hidden text-center text-[11px] font-medium sm:block ${
                      isCurrent
                        ? "text-brand-300"
                        : isPast
                        ? "text-foreground"
                        : "text-muted/60"
                    }`}
                  >
                    {s.label}
                  </span>
                  <span
                    className={`mt-1 text-center text-[10px] font-medium sm:hidden ${
                      isCurrent
                        ? "text-brand-300"
                        : isPast
                        ? "text-foreground"
                        : "text-muted/60"
                    }`}
                  >
                    {s.short}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. Whole-Team Situational Briefing Card */}
      <div className="rounded-xl border border-surface-border bg-surface p-5 sm:p-6 transition-all shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border/80 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-500/30 bg-surface-blue text-brand-300">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                Whole-Team Situational Briefing
              </h2>
              <p className="text-xs text-muted">
                Collective fraud detection progress & unified operational status
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                verdictReady
                  ? "border-status-success/30 bg-status-success/10 text-status-success"
                  : isRunning
                  ? "border-brand-500/30 bg-surface-blue text-brand-300"
                  : "border-surface-border bg-surface-raised text-muted"
              }`}
            >
              {isRunning && (
                <span className="review-pulse h-2 w-2 rounded-full bg-brand-500" aria-hidden="true" />
              )}
              {verdictReady
                ? "Adjudication Complete"
                : isRunning
                ? "Active Fraud Investigation"
                : "Awaiting Ledger"}
            </span>
          </div>
        </div>

        {/* Narrative Paragraph */}
        <div className="py-4">
          <p className="text-sm sm:text-base leading-relaxed text-foreground/90 font-normal">
            {situationalState.executiveSummary}
          </p>
        </div>

        {/* 3. ElevenLabs Voice Narration Integration */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-500/20 bg-surface-blue/50 px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleAudioToggle}
              disabled={!situationalState.executiveSummary}
              className="app-button inline-flex items-center gap-2 text-xs"
              aria-label={isPlaying ? "Stop audio briefing" : "Listen to spoken briefing"}
            >
              {isPlaying || isLoading ? (
                <Square className="h-3.5 w-3.5 text-brand-300" />
              ) : (
                <Volume2 className="h-4 w-4 text-brand-300" />
              )}
              <span>
                {isLoading
                  ? "Synthesizing voice…"
                  : isPlaying
                  ? "Stop narration"
                  : "Listen to spoken briefing"}
              </span>
            </button>

            {/* Visualizer Sound Waves */}
            {isPlaying && (
              <div className="flex items-center gap-1 text-brand-500">
                <span className="h-3 w-1 animate-pulse bg-brand-500 rounded-full" />
                <span className="h-5 w-1 animate-pulse delay-75 bg-brand-500 rounded-full" />
                <span className="h-2 w-1 animate-pulse delay-150 bg-brand-500 rounded-full" />
                <span className="h-4 w-1 animate-pulse delay-100 bg-brand-500 rounded-full" />
                <span className="text-[11px] font-mono text-brand-300 ml-1">
                  Speaking update (ElevenLabs)
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 text-[11px] text-muted">
            <Sparkles className="h-3 w-3 text-brand-300" />
            <span>Human Voice Narration</span>
          </div>
        </div>

        {notice && (
          <p className="mt-2 text-xs leading-5 text-muted">{notice}</p>
        )}
        {error && (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-status-warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            {error}
          </p>
        )}

        {/* 4. Cumulative Fraud Advances Matrix */}
        <div className="mt-5 border-t border-surface-border/70 pt-4">
          <span className="mb-2.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">
            Current Fraud Detection Indicators
          </span>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {situationalState.advances.map((adv, idx) => (
              <div
                key={idx}
                className={`rounded-lg border p-3 ${
                  adv.isAlert
                    ? "border-status-warning/40 bg-status-warning/5 text-status-warning"
                    : "border-surface-border bg-surface-deep/70 text-foreground"
                }`}
              >
                <span className="block text-[10px] text-muted">{adv.label}</span>
                <span className="mt-1 block font-mono text-sm font-semibold truncate">
                  {adv.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
