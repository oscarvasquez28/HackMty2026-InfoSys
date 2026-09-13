import type { Metadata } from "next";
import { ReportHistoryScreen } from "@/components/investigate/ReportHistoryScreen";

export const metadata: Metadata = {
  title: "Audit history | Polar",
  description: "Browse persisted forensic audit runs and reopen their generated reports.",
};

export default function InvestigateHistoryPage() {
  return <ReportHistoryScreen />;
}
