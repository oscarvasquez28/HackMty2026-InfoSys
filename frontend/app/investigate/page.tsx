import type { Metadata } from "next";
import { InvestigationDashboard } from "@/components/InvestigationDashboard";

export const metadata: Metadata = {
  title: "Investigate | Polar",
  description: "Follow a guided financial investigation from transaction records to connected findings and an evidence-based assessment.",
};

export default function InvestigatePage() {
  return <InvestigationDashboard />;
}
