"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Activity,
  Layers,
  Sparkles,
  RotateCcw,
  Network,
  Cpu,
  BarChart3,
} from "lucide-react";
import { UploadResponse } from "@/types/investigation";
import { useInvestigationStream } from "@/hooks/useInvestigationStream";
import { FileUpload } from "@/components/FileUpload";
import { ThoughtStream } from "@/components/ThoughtStream";
import { VerdictCard } from "@/components/VerdictCard";
import { formatCurrencyMXN } from "@/lib/utils";

export default function Home() {
  const [currentCase, setCurrentCase] = useState<UploadResponse | null>(null);
  const { thoughts, verdict, isStreaming, error, startStream, resetStream } =
    useInvestigationStream();

  const handleUploadSuccess = (data: UploadResponse) => {
    setCurrentCase(data);
    startStream(data.case_id);
  };

  const handleReset = () => {
    resetStream();
    setCurrentCase(null);
  };

  return (
    <main className="min-h-screen px-4 py-8 md:px-12 max-w-7xl mx-auto space-y-8">
      {/* Top Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-6">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-950/80 border border-emerald-600/40 text-emerald-400 shadow-lg">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2">
                Forensic Auditor
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-mono">
                  v1.0 AML Core
                </span>
              </h1>
              <p className="text-xs md:text-sm text-gray-400">
                Poda determinista de grafos (Polars + NetworkX), orquestación SSE y dictamen por voz con ElevenLabs
              </p>
            </div>
          </div>
        </div>

        {/* System Health Indicators */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-300 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>FastAPI: 8000</span>
          </div>

          {currentCase && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-200 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Nueva Auditoría</span>
            </button>
          )}
        </div>
      </header>

      {/* Hero / Upload Section */}
      {!currentCase && (
        <section className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-2">
            <div className="p-4 rounded-xl bg-surface/80 border border-surface-border space-y-1">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase">
                <Network className="w-4 h-4" /> Poda Topológica
              </div>
              <p className="text-xs text-gray-400">
                NetworkX extrae ciclos cerrados y cuentas puente de alta velocidad eliminando hasta el 95% de falsos positivos.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface/80 border border-surface-border space-y-1">
              <div className="flex items-center gap-2 text-sky-400 text-xs font-semibold uppercase">
                <Cpu className="w-4 h-4" /> Inferencia SSE
              </div>
              <p className="text-xs text-gray-400">
                Streaming en vivo de la cadena de razonamiento pericial conectada con n8n o generador forense en tiempo real.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface/80 border border-surface-border space-y-1">
              <div className="flex items-center gap-2 text-purple-400 text-xs font-semibold uppercase">
                <Sparkles className="w-4 h-4" /> Síntesis ElevenLabs
              </div>
              <p className="text-xs text-gray-400">
                Proxy seguro de audio en streaming directo que dicta el resumen pericial oficial para el oficial de cumplimiento.
              </p>
            </div>
          </div>

          <FileUpload onUploadSuccess={handleUploadSuccess} />
        </section>
      )}

      {/* Investigation Dashboard */}
      {currentCase && (
        <section className="space-y-6 animate-fade-in">
          {/* Real-time Processing Stats Banner */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 font-mono">
                <Layers className="w-3.5 h-3.5 text-emerald-400" /> Operaciones Analizadas
              </span>
              <p className="text-lg font-bold text-white mt-1">
                {currentCase.metrics.total_edges_analyzed.toLocaleString()}
              </p>
            </div>

            <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 font-mono">
                <Activity className="w-3.5 h-3.5 text-purple-400" /> Poda Determinista
              </span>
              <p className="text-lg font-bold text-purple-400 mt-1">
                {currentCase.metrics.pruning_efficiency_pct}% ruido filtrado
              </p>
            </div>

            <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 font-mono">
                <Network className="w-3.5 h-3.5 text-sky-400" /> Nodos en Subgrafo
              </span>
              <p className="text-lg font-bold text-sky-400 mt-1">
                {currentCase.metrics.suspicious_nodes_count} cuentas
              </p>
            </div>

            <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg">
              <span className="text-[11px] text-gray-400 flex items-center gap-1 font-mono">
                <BarChart3 className="w-3.5 h-3.5 text-amber-400" /> Volumen Detectado
              </span>
              <p className="text-lg font-bold text-amber-400 mt-1">
                {formatCurrencyMXN(currentCase.metrics.suspicious_volume_mxn)}
              </p>
            </div>
          </div>

          {/* Thought Stream Terminal */}
          <ThoughtStream
            thoughts={thoughts}
            isStreaming={isStreaming}
            error={error}
          />

          {/* Final Forensic Verdict Card */}
          {verdict && <VerdictCard verdict={verdict} />}
        </section>
      )}
    </main>
  );
}
