"use client";

import React, { useState, useRef, useEffect } from "react";
import { Terminal, ChevronDown, ChevronUp, Cpu, CheckCircle2, Clock } from "lucide-react";
import { ThoughtEvent } from "@/types/investigation";

interface ThoughtStreamProps {
  thoughts: ThoughtEvent[];
  isStreaming: boolean;
  error?: string | null;
}

export const ThoughtStream: React.FC<ThoughtStreamProps> = ({
  thoughts,
  isStreaming,
  error,
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const consoleBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isCollapsed && consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [thoughts, isCollapsed]);

  return (
    <div className="w-full bg-[#0d131f] border border-gray-800 rounded-xl shadow-2xl overflow-hidden font-mono text-sm">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#111928] border-b border-gray-800 select-none">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block"></span>
            <span className="w-3 h-3 rounded-full bg-yellow-500/80 inline-block"></span>
            <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block"></span>
          </div>
          <div className="h-4 w-px bg-gray-700 mx-1"></div>
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            Consola Pericial de Razonamiento (SSE Stream)
          </span>
          {isStreaming && (
            <span className="flex items-center gap-1.5 ml-2 px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-[10px] text-emerald-400 animate-pulse">
              <Cpu className="w-3 h-3 animate-spin" /> EN VIVO
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">
            {thoughts.length} {thoughts.length === 1 ? "paso" : "pasos"}
          </span>
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 text-gray-400 hover:text-white transition-colors"
            title={isCollapsed ? "Expandir consola" : "Minimizar consola"}
          >
            {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      {!isCollapsed && (
        <div className="p-4 max-h-80 min-h-[160px] overflow-y-auto space-y-3 bg-[#080c14] text-xs">
          {thoughts.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center py-10 text-gray-500">
              <Terminal className="w-8 h-8 mb-2 opacity-30" />
              <p>Esperando carga de dataset o inicio de la investigación forense...</p>
            </div>
          )}

          {thoughts.map((thought, index) => {
            const timeStr = new Date(thought.timestamp).toLocaleTimeString("es-MX", {
              hour12: false,
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });

            return (
              <div
                key={`${thought.step}-${index}`}
                className="flex items-start gap-3 p-2 rounded bg-gray-900/50 border border-gray-800/80 hover:border-gray-700/80 transition-colors"
              >
                <span className="text-emerald-500 font-bold shrink-0">
                  [{thought.step.toString().padStart(2, "0")}]
                </span>

                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-600/30 text-[10px] text-emerald-300 uppercase tracking-wider font-semibold">
                      {thought.phase}
                    </span>
                    <span className="text-[10px] text-gray-500 flex items-center gap-1 ml-auto">
                      <Clock className="w-3 h-3" />
                      {timeStr}
                    </span>
                  </div>
                  <p className="text-gray-300 font-sans leading-relaxed text-xs">
                    {thought.message}
                  </p>
                </div>
              </div>
            );
          })}

          {isStreaming && (
            <div className="flex items-center gap-2 text-emerald-400/80 text-xs py-1 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>Ejecutando inferencia pericial y verificando tipologías contra grafo podado...</span>
            </div>
          )}

          {error && (
            <div className="p-2 rounded bg-red-950/40 border border-red-800/50 text-red-300 text-xs">
              {error}
            </div>
          )}

          <div ref={consoleBottomRef} />
        </div>
      )}
    </div>
  );
};
