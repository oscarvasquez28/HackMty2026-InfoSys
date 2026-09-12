"use client";

import React, { useState } from "react";
import { ArrowRight, Check, CircleDot, Network } from "lucide-react";

type ViewMode = "all" | "signals";

const nodes = [
  { id: "A-1042", label: "Origin", x: 12, y: 48, flagged: true },
  { id: "B-2281", label: "Bridge", x: 37, y: 22, flagged: true },
  { id: "C-9013", label: "Bridge", x: 64, y: 38, flagged: true },
  { id: "D-6720", label: "Return", x: 39, y: 72, flagged: true },
  { id: "E-3328", label: "Account", x: 82, y: 16, flagged: false },
  { id: "F-1844", label: "Account", x: 84, y: 72, flagged: false },
];

export const InvestigationPreview: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const showContext = viewMode === "all";

  return (
    <div className="overflow-hidden rounded-xl border border-surface-border bg-surface shadow-panel">
      <div className="flex flex-col gap-4 border-b border-surface-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-brand-500/25 bg-brand-500/10 text-brand-300">
            <Network className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">Investigation overview</p>
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">Illustrative data · Case PLR-082</p>
          </div>
        </div>
        <div className="inline-flex w-fit rounded-md border border-surface-border bg-background p-1" aria-label="Transaction view">
          <button
            type="button"
            aria-pressed={showContext}
            onClick={() => setViewMode("all")}
            className={`min-h-11 cursor-pointer rounded px-3 text-xs font-medium transition-colors ${
              showContext ? "bg-surface-raised text-foreground" : "text-muted hover:text-foreground"
            } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
          >
            All activity
          </button>
          <button
            type="button"
            aria-pressed={!showContext}
            onClick={() => setViewMode("signals")}
            className={`min-h-11 cursor-pointer rounded px-3 text-xs font-medium transition-colors ${
              !showContext ? "bg-brand-500 text-brand-ink" : "text-muted hover:text-foreground"
            } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
          >
            Signals only
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_310px]">
        <div className="relative min-h-[410px] overflow-hidden border-b border-surface-border bg-grid-pattern lg:border-b-0 lg:border-r">
          <div className="absolute left-5 top-5 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <CircleDot className="h-3.5 w-3.5 text-brand-500" aria-hidden="true" />
            Transaction topology
          </div>
          <svg aria-hidden="true" className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <g className={`transition-opacity duration-300 ${showContext ? "opacity-100" : "opacity-10"}`} stroke="currentColor" strokeWidth="0.3" strokeDasharray="1 1.5">
              <path d="M12 48 82 16" className="text-surface-border" />
              <path d="M64 38 84 72" className="text-surface-border" />
              <path d="M37 22 84 72" className="text-surface-border" />
              <path d="M12 48 84 72" className="text-surface-border" />
            </g>
            <g className="preview-signal-path text-brand-500" fill="none" stroke="currentColor" strokeWidth="0.7">
              <path d="M12 48 37 22 64 38 39 72 12 48" />
            </g>
          </svg>

          {nodes.map((node) => (
            <div
              key={node.id}
              className={`absolute -translate-x-1/2 -translate-y-1/2 transition-all duration-300 ${
                !node.flagged && !showContext ? "scale-75 opacity-20" : "opacity-100"
              }`}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <div
                className={`relative min-w-[78px] rounded-md border px-2.5 py-2 text-center shadow-lg sm:min-w-[92px] ${
                  node.flagged
                    ? "border-brand-500/55 bg-surface-blue"
                    : "border-surface-border bg-surface-raised"
                }`}
              >
                {node.flagged && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-brand-500" />}
                <p className={`font-mono text-[10px] ${node.flagged ? "text-brand-300" : "text-muted"}`}>{node.id}</p>
                <p className="mt-0.5 text-[10px] text-muted">{node.label}</p>
              </div>
            </div>
          ))}

          <div className="absolute bottom-4 left-5 right-5 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
            <span>6 accounts</span>
            <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-brand-500" />Pattern traced</span>
          </div>
        </div>

        <aside className="flex flex-col p-5 sm:p-6" aria-label="Illustrative findings">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-brand-300">Signal detected</p>
          <h3 className="mt-3 text-xl font-semibold tracking-[-0.025em] text-foreground">Circular flow pattern</h3>
          <p className="mt-3 text-sm leading-6 text-muted">
            Funds return to the origin through three intermediary accounts, concentrating review on the connected trail.
          </p>

          <dl className="mt-7 space-y-4 border-y border-surface-border py-5">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-xs text-muted">Connected accounts</dt>
              <dd className="font-mono text-sm text-foreground">04</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-xs text-muted">Pattern type</dt>
              <dd className="font-mono text-sm text-foreground">CYCLE</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-xs text-muted">Review status</dt>
              <dd className="flex items-center gap-1.5 text-xs text-brand-300"><Check className="h-3.5 w-3.5" />Ready</dd>
            </div>
          </dl>

          <div className="mt-auto pt-6">
            <p className="flex items-center gap-2 text-xs font-medium text-foreground">
              Evidence path isolated
              <ArrowRight className="h-3.5 w-3.5 text-brand-500" aria-hidden="true" />
            </p>
            <p className="mt-2 text-xs leading-5 text-muted">Context remains visible while the relevant transactions stay in focus.</p>
          </div>
        </aside>
      </div>
    </div>
  );
};
