"use client";

import React, { useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Plus,
  Layers,
  Check,
  FileText,
  PanelRight,
  Activity,
  Info,
} from "lucide-react";
import { AgentId, EvidenceRef } from "@/types/investigation";
import { useAgentSimulation } from "@/hooks/useAgentSimulation";
import { FileUpload } from "@/components/FileUpload";
import { TeamSituationalBriefing } from "@/components/TeamSituationalBriefing";
import { TeamDecisionRoster } from "@/components/TeamDecisionRoster";
import { VerdictCard } from "@/components/VerdictCard";
import { REVIEW_TEAM, getAgentName } from "@/components/AgentTeam";
import { DatasetContext } from "@/components/DatasetContext";
import { PolarMark } from "@/components/PolarMark";

type WorkspaceView = "activity" | "dataset" | "evidence";

const specialistFocus: Record<string, string> = {
  DATA_VALIDATION: "Checks accepted records, normalized columns and the assumptions behind transaction timestamps.",
  CIRCULAR_FLOWS: "Reviews paths where money moves through connected accounts and returns to its starting point.",
  PASSTHROUGH: "Reviews accounts with closely matching incoming and outgoing funds inside a configured time window.",
  RISK_REVIEW: "Connects the pattern findings to their scope, limitations and recommended human follow-up.",
};

/** @deprecated Legacy frontend-only simulation. Superseded by CaseFileWorkspace at /investigate. */
export const InvestigationDashboard: React.FC = () => {
  const {
    currentCase,
    verdict,
    statuses: agentStatuses,
    situationalState,
    agentDecisions,
    isPreparing,
    isRunning,
    error,
    startSimulation,
    resetSimulation,
  } = useAgentSimulation();

  const [selectedAgent, setSelectedAgent] = useState<AgentId | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceRef | null>(null);
  const [view, setView] = useState<WorkspaceView>("activity");
  const [session, setSession] = useState(0);

  const returned = REVIEW_TEAM.filter((agent) => agentStatuses[agent.id] === "returned").length;
  const statusLabel = isPreparing
    ? "Preparing simulation"
    : error
    ? "Simulation interrupted"
    : verdict
    ? "Demo assessment ready"
    : isRunning
    ? "Simulation in progress"
    : "Ready to simulate";

  const handleReset = useCallback(() => {
    resetSimulation();
    setSelectedAgent(null);
    setSelectedEvidence(null);
    setView("activity");
    setSession((value) => value + 1);
  }, [resetSimulation]);

  const handleEvidence = useCallback((ref: EvidenceRef) => {
    setSelectedEvidence(ref);
    setView("evidence");
  }, []);

  const handleAgent = useCallback((agent: AgentId) => {
    setSelectedAgent((previous) => (previous === agent ? null : agent));
  }, []);

  const handleStartSimulation = useCallback(
    async (files: File[]) => {
      setSelectedAgent(null);
      setSelectedEvidence(null);
      setView("activity");
      await startSimulation(files);
    },
    [startSimulation]
  );

  return (
    <div className="investigation-shell min-h-[100dvh] bg-background text-foreground">
      <a
        href="#investigation-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-brand-500 focus:p-3 focus:text-brand-ink"
      >
        Skip to investigation
      </a>

      {/* Top Header */}
      <header className="border-b border-surface-border bg-surface-deep">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <Link
              href="/"
              className="flex min-h-11 shrink-0 items-center gap-2.5 text-base font-semibold tracking-tight"
              aria-label="Polar home"
            >
              <PolarMark className="h-6 w-6 text-brand-500" />
              polar
            </Link>
            <span className="h-5 w-px bg-surface-border" aria-hidden="true" />
            <span className="truncate text-xs text-muted sm:text-sm">Investigation workspace</span>
          </div>

          {/* System Health Indicators */}
          <div className="flex shrink-0 items-center gap-5">
            <span className="hidden text-xs text-muted lg:block">{statusLabel}</span>
            {currentCase || isPreparing ? (
              <button
                type="button"
                onClick={handleReset}
                className="app-button flex items-center gap-2 text-xs"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">New investigation</span>
                <span className="sm:hidden">New</span>
              </button>
            ) : (
              <Link
                href="/"
                className="flex min-h-11 items-center gap-2 text-xs text-muted hover:text-foreground"
              >
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Back to Polar</span>
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Mobile navigation tab bar */}
      <nav aria-label="Workspace views" className="flex border-b border-surface-border px-4 md:hidden">
        {(
          [
            { id: "activity", label: "Briefing & Progress", icon: Activity },
            { id: "dataset", label: "Dataset", icon: FileText },
            { id: "evidence", label: "Team & Decisions", icon: PanelRight },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={view === item.id ? "page" : undefined}
            onClick={() => setView(item.id)}
            className={`flex min-h-12 flex-1 items-center justify-center gap-2 border-b-2 text-xs ${
              view === item.id
                ? "border-brand-500 text-brand-300"
                : "border-transparent text-muted"
            }`}
          >
            <item.icon className="h-3.5 w-3.5" aria-hidden="true" />
            {item.label}
          </button>
        ))}
      </nav>

      {/* Main 3-column workspace grid */}
      <div className="mx-auto grid max-w-[1600px] gap-6 px-4 py-6 sm:px-6 md:grid-cols-[210px_minmax(0,1fr)] lg:gap-8 lg:px-8 lg:py-8 xl:grid-cols-[220px_minmax(0,1fr)_320px] 2xl:grid-cols-[240px_minmax(0,1fr)_340px]">
        {/* Left Column: Dataset context */}
        <div
          className={`min-w-0 md:border-r md:border-surface-border md:pr-6 ${
            view === "dataset" ? "block" : "hidden md:block"
          }`}
        >
          <DatasetContext
            currentCase={currentCase}
            onOpenDataset={() =>
              handleEvidence({ kind: "dataset", id: "normalized", label: "Normalized records" })
            }
          />
        </div>

        {/* Center Main: Whole-team fraud detection progress, briefing, voice narration & verdict */}
        <main
          id="investigation-main"
          className={`min-w-0 space-y-6 ${view === "activity" ? "block" : "hidden md:block"}`}
        >
          {/* Section Header */}
          <section>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs text-muted">
                <Layers className="h-4 w-4 text-brand-300" aria-hidden="true" />
                {currentCase
                  ? `Case ${currentCase.case_id.slice(0, 8)} • Whole-Team Forensic Progress`
                  : "A clear path from data to findings"}
              </div>
              {verdict && (
                <a
                  href="#final-assessment"
                  className="flex min-h-11 items-center gap-1.5 text-xs text-brand-300"
                >
                  View assessment <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              )}
            </div>
            <h1 className="text-balance text-2xl font-medium leading-tight tracking-[-0.04em] sm:text-3xl">
              {currentCase
                ? "Unified Team Fraud Investigation"
                : "Follow the evidence."}
            </h1>
            <p className="mt-2 max-w-xl text-xs sm:text-sm leading-6 text-muted">
              {currentCase
                ? "Follow the collective forensic breakthroughs as the team advances through ingestion, pattern extraction, and regulatory risk synthesis. Human voice briefings powered by ElevenLabs."
                : "Upload transaction CSVs. Follow the team's progress through four synchronized fraud detection stages with voice narration."}
            </p>
          </section>

          {/* Real-time Simulation Disclaimer Banner */}
          {currentCase && (
            <div className="flex items-start gap-2 rounded-lg border border-brand-500/30 bg-surface-blue px-4 py-3 text-xs leading-5 text-muted">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-300" aria-hidden="true" />
              <p>
                <span className="font-medium text-brand-300">Simulation mode.</span> The sequence,
                narrative briefings, and final risk level are illustrative. No backend or live AI model is
                analyzing these files.
              </p>
            </div>
          )}

          {/* Upload Area (When No Case Active) */}
          {!currentCase && (
            <section className="space-y-5">
              {selectedAgent && (
                <div className="rounded-lg border border-brand-500/25 bg-surface-blue p-4">
                  <h3 className="text-sm font-medium text-brand-300">
                    {getAgentName(selectedAgent)}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {specialistFocus[selectedAgent]}
                  </p>
                </div>
              )}
              <FileUpload
                key={session}
                onStartSimulation={handleStartSimulation}
                isPreparing={isPreparing}
                simulationError={error}
              />
              <div className="flex items-start gap-2 text-xs leading-6 text-muted">
                <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-brand-300" aria-hidden="true" />
                <p>
                  High-level demo explanations only. No raw internal reasoning, backend calls, or
                  real fraud conclusions.
                </p>
              </div>
            </section>
          )}

          {/* Center Column Core: Whole-Team Situational Briefing & Progress Line (When Case Active) */}
          {currentCase && (
            <div className="space-y-6">
              <TeamSituationalBriefing
                situationalState={situationalState}
                hasCase={!!currentCase}
                isRunning={isRunning}
                verdictReady={!!verdict}
              />
            </div>
          )}

          {/* Final Forensic Verdict Card (Prominently shown once ready) */}
          {verdict && (
            <div id="final-assessment" className="scroll-mt-6">
              <VerdictCard
                key={verdict.case_id}
                verdict={verdict}
                onEvidence={handleEvidence}
              />
            </div>
          )}
        </main>

        {/* Right Column: Specialist Team Roster & Active Decisions + Dataset Evidence */}
        <div
          className={`min-w-0 md:col-start-2 xl:col-start-3 xl:row-start-1 ${
            view === "evidence" ? "block" : "hidden md:block"
          }`}
        >
          <div className="xl:sticky xl:top-6">
            <TeamDecisionRoster
              statuses={agentStatuses}
              agentDecisions={agentDecisions}
              selectedAgent={selectedAgent}
              onSelectAgent={handleAgent}
              currentCase={currentCase}
              selectedEvidence={selectedEvidence}
              onEvidence={handleEvidence}
              hasCase={!!currentCase}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
