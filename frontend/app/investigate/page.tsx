import type { Metadata } from "next";
import { CaseFileWorkspace } from "@/components/case-file/CaseFileWorkspace";

export const metadata: Metadata = {
  title: "Case File | Polar",
  description: "Forensic case file viewer: findings, money trails, exhibits, reconciliation and declined leads.",
};

export default function InvestigatePage() {
  return <CaseFileWorkspace />;
}
