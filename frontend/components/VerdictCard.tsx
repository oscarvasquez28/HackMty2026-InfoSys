"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  DollarSign,
  Users,
  FilterX,
  FileText,
  Scale,
  ChevronDown,
  ChevronUp,
  CheckCircle,
} from "lucide-react";
import { VerdictEvent } from "@/types/investigation";
import { formatCurrencyMXN } from "@/lib/utils";
import { AudioPlayer } from "@/components/AudioPlayer";

interface VerdictCardProps {
  verdict: VerdictEvent;
}

export const VerdictCard: React.FC<VerdictCardProps> = ({ verdict }) => {
  const [showEntities, setShowEntities] = useState<boolean>(false);

  const getRiskBadgeColor = (risk: string) => {
    switch (risk) {
      case "CRÍTICO":
        return "bg-red-950/80 text-red-400 border-red-700/60";
      case "ALTO":
        return "bg-amber-950/80 text-amber-400 border-amber-700/60";
      default:
        return "bg-blue-950/80 text-blue-400 border-blue-700/60";
    }
  };

  return (
    <div className="w-full bg-surface border border-surface-border rounded-xl p-6 shadow-2xl space-y-6 animate-fade-in">
      {/* Header with Risk Level & Case ID */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-red-400" />
            <h3 className="text-xl font-bold text-white tracking-wide">
              Dictamen Pericial Forense
            </h3>
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${getRiskBadgeColor(
                verdict.risk_level
              )}`}
            >
              Nivel {verdict.risk_level}
            </span>
          </div>
          <p className="text-xs text-gray-400 font-mono">
            ID de Caso: <span className="text-gray-300">{verdict.case_id}</span> • Finalizado:{" "}
            {new Date(verdict.completed_at).toLocaleString("es-MX")}
          </p>
        </div>

        {/* Audio Dictation Player */}
        <div className="shrink-0">
          <AudioPlayer
            textToSynthesize={verdict.audit_summary_text}
            label="Escuchar Dictamen (ElevenLabs)"
          />
        </div>
      </div>

      {/* Grid of Key Forensic Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Fraud Type & Volume */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-xs font-medium mb-1">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Monto Comprometido (MXN)</span>
          </div>
          <p className="text-2xl font-extrabold text-white tracking-tight">
            {formatCurrencyMXN(verdict.total_amount_mxn)}
          </p>
          <p className="text-xs text-emerald-400/90 mt-1 font-medium">
            {verdict.fraud_type}
          </p>
        </div>

        {/* Entities Involved */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-xs font-medium mb-1">
            <Users className="w-4 h-4 text-sky-400" />
            <span>Entidades Involucradas</span>
          </div>
          <p className="text-2xl font-extrabold text-white tracking-tight">
            {verdict.entities_involved.length} cuentas
          </p>
          <p className="text-xs text-sky-400/90 mt-1 font-medium">
            {verdict.patterns_summary.closed_cycles} ciclos detectados • {verdict.patterns_summary.passthrough_accounts} cuentas puente
          </p>
        </div>

        {/* Pruned Leads (Deterministic Graph Reduction) */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-xs font-medium mb-1">
            <FilterX className="w-4 h-4 text-purple-400" />
            <span>Pistas Descartadas (Poda)</span>
          </div>
          <p className="text-2xl font-extrabold text-white tracking-tight">
            {verdict.pruned_leads_count.toLocaleString()} operaciones
          </p>
          <p className="text-xs text-purple-400/90 mt-1 font-medium">
            {verdict.patterns_summary.pruning_efficiency_pct}% de reducción de falso positivo
          </p>
        </div>
      </div>

      {/* Audit Summary Narrative */}
      <div className="bg-gray-900/40 border border-gray-800/80 rounded-lg p-4 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <FileText className="w-4 h-4 text-emerald-400" />
          <span>Resumen Ejecutivo del Peritaje</span>
        </div>
        <p className="text-sm text-gray-200 leading-relaxed font-sans">
          {verdict.audit_summary_text}
        </p>
      </div>

      {/* Legal & Regulatory Recommendation */}
      <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-4 space-y-1.5">
        <div className="flex items-center gap-2 text-xs font-semibold text-amber-300 uppercase tracking-wider">
          <Scale className="w-4 h-4 text-amber-400" />
          <span>Recomendación Jurídica y Regulatoria (UIF / GAFI)</span>
        </div>
        <p className="text-xs text-amber-200/90 leading-relaxed">
          {verdict.legal_recommendation}
        </p>
      </div>

      {/* Collapsible Entities Breakdown */}
      <div className="border-t border-gray-800 pt-3">
        <button
          type="button"
          onClick={() => setShowEntities(!showEntities)}
          className="w-full flex items-center justify-between text-xs text-gray-400 hover:text-white py-1.5 transition-colors"
        >
          <span className="font-mono">
            {showEntities ? "Ocultar cuentas bajo sospecha" : "Ver listado de cuentas bajo sospecha pericial"} ({verdict.entities_involved.length})
          </span>
          {showEntities ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showEntities && (
          <div className="mt-3 flex flex-wrap gap-2 max-h-40 overflow-y-auto p-2 bg-gray-900/80 rounded border border-gray-800">
            {verdict.entities_involved.map((entityId) => (
              <span
                key={entityId}
                className="px-2.5 py-1 rounded bg-gray-800 border border-gray-700 font-mono text-xs text-gray-300 hover:border-red-500/50 transition-colors"
              >
                {entityId}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
