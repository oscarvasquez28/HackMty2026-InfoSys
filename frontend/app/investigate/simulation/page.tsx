import type { Metadata } from "next";
import Link from "next/link";
import { InvestigationDashboard } from "@/components/InvestigationDashboard";

export const metadata: Metadata = {
  title: "Legacy simulation (deprecated) | Polar",
  description: "The pre-contract frontend-only multi-agent simulation, kept for reference only.",
};

export default function InvestigateSimulationPage() {
  return (
    <>
      <div className="border-b border-status-warning/40 bg-surface-deep px-4 py-2 text-center text-xs text-status-warning">
        Deprecated: this multi-agent simulation predates the case file contract and is kept for reference only.{" "}
        <Link href="/investigate" className="underline">
          Open the case file viewer
        </Link>
      </div>
      <InvestigationDashboard />
    </>
  );
}
