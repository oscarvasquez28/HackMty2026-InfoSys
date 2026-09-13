"use client";

import React from "react";
import { Globe, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AuditMode } from "@/types/investigation";

interface AnalysisModeSwitchProps {
  mode: AuditMode;
  onChange: (mode: AuditMode) => void;
  disabled?: boolean;
}

const OPTIONS: Array<{
  value: AuditMode;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  hint: string;
}> = [
  {
    value: "offline",
    label: "Offline",
    icon: WifiOff,
    hint: "Deterministic engine only — no external n8n calls.",
  },
  {
    value: "online",
    label: "Online",
    icon: Globe,
    hint: "Connects to n8n for LLM enrichment; deterministic fallback if unreachable.",
  },
];

export const AnalysisModeSwitch: React.FC<AnalysisModeSwitchProps> = ({
  mode,
  onChange,
  disabled = false,
}) => {
  const active = OPTIONS.find((option) => option.value === mode) ?? OPTIONS[1];

  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
        Analysis mode
      </span>
      <div
        role="radiogroup"
        aria-label="Analysis mode"
        className="inline-flex w-fit items-center gap-1 rounded-md border border-surface-border bg-surface-deep p-1"
      >
        {OPTIONS.map((option) => {
          const Icon = option.icon;
          const selected = option.value === mode;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(option.value)}
              className={cn(
                "flex min-h-8 items-center gap-1.5 rounded px-3 text-xs font-medium transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                "disabled:cursor-not-allowed disabled:opacity-50",
                selected
                  ? "bg-brand-500 text-brand-ink shadow-sm"
                  : "text-muted hover:text-foreground"
              )}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted">{active.hint}</p>
    </div>
  );
};
