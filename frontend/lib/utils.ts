import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrencyMXN(amount: number): string {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatPesos(amount: number): string {
  return `${formatCurrencyMXN(amount)} MXN`;
}

export function formatSeconds(seconds: number): string {
  return `${seconds.toFixed(1)}s`;
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function buildVerdictNarration(verdict: {
  risk_level: string;
  total_amount_mxn: number;
}): string {
  const total = verdict.total_amount_mxn;
  const spoken =
    total >= 1_000_000
      ? `${(total / 1_000_000).toFixed(1)} million`
      : total >= 1_000
        ? `${formatInteger(Math.round(total / 1_000))} thousand`
        : formatInteger(total);
  return `Forensic audit complete. Risk level: ${verdict.risk_level.toLowerCase()}. Flagged total: ${spoken} pesos.`;
}
