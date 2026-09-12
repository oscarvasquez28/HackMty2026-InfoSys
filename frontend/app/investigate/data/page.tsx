import type { Metadata } from "next";
import { DataEstateWorkspace } from "@/components/estate/DataEstateWorkspace";

export const metadata: Metadata = {
  title: "Data estate | Polar",
  description: "Load and validate the company's data estate (SQLite, CSV, CFDI XML, or JSON) against estate_schema.sql.",
};

export default function InvestigateDataPage() {
  return <DataEstateWorkspace />;
}
