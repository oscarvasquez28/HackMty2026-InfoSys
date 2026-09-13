"use client";

import React, { useEffect, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileCheck,
  Loader2,
  ShieldAlert,
  X,
  Zap,
} from "lucide-react";
import { formatCurrencyMXN } from "@/lib/utils";
import type { ThoughtEvent, VerdictEvent, AgentStatuses, AgentId } from "@/types/investigation";

interface EstateAuditStreamModalProps {
  isOpen: boolean;
  isStreaming: boolean;
  currentPhase: string;
  thoughts: ThoughtEvent[];
  findingsReviewed: any[];
  leadsReviewed: any[];
  verdict: VerdictEvent | null;
  completedAudit: any | null;
  error: string | null;
  agentStatuses: AgentStatuses;
  onClose: () => void;
  onOpenCaseFile: (auditData: any) => void;
}

const AGENTS: Array<{ id: AgentId; label: string; role: string }> = [
  { id: "DATA_VALIDATION", label: "Validación", role: "Ingesta & Conciliación 2%" },
  { id: "CIRCULAR_FLOWS", label: "Topología", role: "Ciclos NetworkX & Mulas" },
  { id: "RISK_REVIEW", label: "Adversarial", role: "Challenger vs Investigator" },
  { id: "ORCHESTRATOR", label: "Dictamen", role: "Juez Pericial Oficial" },
];

export const EstateAuditStreamModal: React.FC<EstateAuditStreamModalProps> = ({
  isOpen,
  isStreaming,
  currentPhase,
  thoughts,
  findingsReviewed,
  leadsReviewed,
  verdict,
  completedAudit,
  error,
  agentStatuses,
  onClose,
  onOpenCaseFile,
}) => {
  const streamEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [thoughts, isOpen]);

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
                Auditoría Forense en Tiempo Real
              </h3>
              <p className="flex items-center gap-2 font-mono text-xs text-muted">
                <span className="inline-block h-2 w-2 rounded-full bg-brand-400 animate-pulse" />
                {currentPhase}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted hover:bg-surface-raised hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
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

        {/* Live Thoughts Log */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs">
          {thoughts.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted">
              <Loader2 className="h-8 w-8 animate-spin text-brand-400 mb-3" />
              <p>Iniciando agentes y cargando topología de transacciones...</p>
            </div>
          )}

          {thoughts.map((t, idx) => (
            <div
              key={t.event_id || idx}
              className="group rounded-lg border border-surface-border/60 bg-surface/40 p-3 hover:border-brand-500/30 transition-colors"
            >
              <div className="flex items-center justify-between gap-2 mb-1.5 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-brand-300 font-semibold">
                    Paso {t.step}
                  </span>
                  <span className="text-foreground font-medium">{t.phase}</span>
                </div>
                <span className="text-muted text-[10px]">
                  {t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : ""}
                </span>
              </div>
              <p className="text-muted leading-relaxed font-sans text-xs group-hover:text-foreground">
                {t.message}
              </p>
            </div>
          ))}

          {/* Finding Cards if any reviewed */}
          {findingsReviewed.map((f, i) => (
            <div
              key={i}
              className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs"
            >
              <div className="flex items-center gap-2 text-amber-300 font-semibold mb-1">
                <ShieldAlert className="h-4 w-4" />
                <span>Hallazgo Detectado & Validado</span>
              </div>
              <p className="text-amber-100/90 font-sans">{f.message}</p>
            </div>
          ))}

          {/* Error notice if any */}
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
              <div>
                <p className="font-semibold">Error en la auditoría</p>
                <p className="mt-1 text-rose-200/80 font-sans">{error}</p>
              </div>
            </div>
          )}

          {/* Final Verdict Banner */}
          {verdict && (
            <div className="mt-4 rounded-xl border border-brand-500/40 bg-brand-500/10 p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  <span className="font-semibold text-foreground text-sm">
                    Dictamen Pericial Concluido
                  </span>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    verdict.risk_level === "CRÍTICO"
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                      : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  }`}
                >
                  Nivel de Riesgo: {verdict.risk_level}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-surface-border/50 pt-3 text-xs">
                <div>
                  <span className="text-muted block">Volumen Flagelado:</span>
                  <span className="text-foreground font-semibold text-sm">
                    {formatCurrencyMXN(verdict.total_amount_mxn)}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Líneas Descartadas:</span>
                  <span className="text-foreground font-semibold text-sm">
                    {verdict.pruned_leads_count} líneas
                  </span>
                </div>
              </div>

              <p className="mt-3 text-xs font-sans text-muted leading-relaxed">
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
                <Zap className="h-3.5 w-3.5 text-brand-400 animate-pulse" />
                Ejecución determinista en curso...
              </span>
            ) : completedAudit ? (
              <span className="text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4" />
                Expediente judicial listo para inspección
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="app-button text-xs"
            >
              Cerrar
            </button>

            {completedAudit && (
              <button
                type="button"
                onClick={() => onOpenCaseFile(completedAudit)}
                className="app-primary flex items-center gap-2 text-xs font-semibold py-2 px-4 shadow-lg shadow-brand-500/20"
              >
                <FileCheck className="h-4 w-4" />
                Ver Expediente Completo
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
