"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Play, Download, ExternalLink } from "lucide-react";
import { downloadTextFile } from "@/lib/caseFile/download";
import { useInvestigateSession } from "@/components/investigate/InvestigateSessionProvider";
import { useEstateAuditStream } from "@/hooks/useEstateAuditStream";
import { EstateAuditStreamModal } from "@/components/estate/EstateAuditStreamModal";

interface EstateExportBarProps {
  exportSqlite: () => Promise<Uint8Array>;
  exportJson: () => string;
  hasEstate: boolean;
}

export const EstateExportBar: React.FC<EstateExportBarProps> = ({
  exportSqlite,
  exportJson,
  hasEstate,
}) => {
  const router = useRouter();
  const { caseFile, auditMode } = useInvestigateSession();
  const stream = useEstateAuditStream();
  const [modalOpen, setModalOpen] = useState(false);

  const handleSqlite = async () => {
    const bytes = await exportSqlite();
    downloadTextFile("estate.db", bytes, "application/vnd.sqlite3");
  };

  const handleJson = () => downloadTextFile("estate.json", exportJson(), "application/json");

  const handleLiveAudit = async () => {
    setModalOpen(true);
    try {
      const bytes = await exportSqlite();
      const blob = new Blob([bytes as BlobPart], { type: "application/vnd.sqlite3" });
      await stream.startAuditWithBlob(blob, undefined, undefined, auditMode);
    } catch (e) {
      console.error("Error launching audit stream:", e);
    }
  };

  const handleOpenCaseFile = (auditData: any) => {
    setModalOpen(false);
    caseFile.loadRaw(auditData, {
      kind: "api",
      label: `Live Audit (Seed ${auditData?.seed ?? 1})`,
    });
    router.push("/investigate");
  };

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleLiveAudit}
            disabled={!hasEstate || stream.isStreaming}
            className="app-primary flex items-center gap-2 text-xs font-semibold py-2 px-3.5 shadow-md shadow-brand-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Run Forensic Audit (Live Stream)
          </button>

          <button
            type="button"
            onClick={handleSqlite}
            disabled={!hasEstate}
            className="app-button flex items-center gap-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5 text-muted" />
            Download estate.db
          </button>

          <button
            type="button"
            onClick={handleJson}
            disabled={!hasEstate}
            className="app-button flex items-center gap-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5 text-muted" />
            Download estate.json
          </button>
        </div>

        <Link
          href="/investigate"
          className="flex items-center gap-1.5 text-xs text-brand-300 hover:text-brand-100 transition-colors"
        >
          Open case file viewer
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      </div>

      <EstateAuditStreamModal
        isOpen={modalOpen}
        isStreaming={stream.isStreaming}
        currentPhase={stream.currentPhase}
        thoughts={stream.thoughts}
        findingsReviewed={stream.findingsReviewed}
        leadsReviewed={stream.leadsReviewed}
        verdict={stream.verdict}
        completedAudit={stream.completedAudit}
        error={stream.error}
        agentStatuses={stream.agentStatuses}
        onClose={() => setModalOpen(false)}
        onOpenCaseFile={handleOpenCaseFile}
      />
    </>
  );
};
