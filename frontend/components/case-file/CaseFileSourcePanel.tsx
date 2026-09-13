"use client";

import React, { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Database, FileText, Play, Sparkles, Upload } from "lucide-react";
import { useInvestigateSession } from "@/components/investigate/InvestigateSessionProvider";
import { AnalysisModeSwitch } from "@/components/AnalysisModeSwitch";
import { useEstateAuditStream } from "@/hooks/useEstateAuditStream";
import { EstateAuditStreamModal } from "@/components/estate/EstateAuditStreamModal";
import type { FixtureId } from "@/hooks/useCaseFileSource";

interface CaseFileSourcePanelProps {
  error: string | null;
  isLoading: boolean;
  onLoadFixture: (id: FixtureId) => void;
  onLoadFile: (file: File) => void;
  onLoadFromApi?: (caseId: string) => void;
  apiEnabled: boolean;
  estateNote?: string | null;
}

const DEV_FIXTURES: Array<{ id: FixtureId; label: string }> = [
  { id: "sample", label: "Sample case (illustrative)" },
  { id: "no-findings", label: "Sample: no findings (illustrative)" },
  { id: "edge-cases", label: "Sample: edge cases (invalid on purpose)" },
  { id: "dense-trail", label: "Sample: dense money trails (diagram regression)" },
];

export const CaseFileSourcePanel: React.FC<CaseFileSourcePanelProps> = ({
  error,
  isLoading,
  onLoadFixture,
  onLoadFile,
  onLoadFromApi,
  apiEnabled,
  estateNote,
}) => {
  const { caseFile, estate, auditMode, setAuditMode } = useInvestigateSession();
  const stream = useEstateAuditStream();

  const [isDragging, setIsDragging] = useState(false);
  const [caseId, setCaseId] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const openPicker = useCallback(() => inputRef.current?.click(), []);

  const handleAuditBlob = useCallback(
    async (blob: Blob, seed: number = 1, companyName: string = "Audited Company S.A. de C.V.") => {
      setModalOpen(true);
      await stream.startAuditWithBlob(blob, seed, companyName, auditMode);
    },
    [stream, auditMode]
  );

  const handleLiveAuditFromEstate = useCallback(async () => {
    try {
      const bytes = await estate.exportSqlite();
      const blob = new Blob([bytes as BlobPart], { type: "application/vnd.sqlite3" });
      await handleAuditBlob(blob);
    } catch (e) {
      console.error("Error running audit from estate:", e);
    }
  }, [estate, handleAuditBlob]);

  const handleAuditSampleEstate = useCallback(async () => {
    try {
      setModalOpen(true);
      const res = await fetch("/samples/estate/estate.db");
      if (!res.ok) {
        throw new Error("Could not find /samples/estate/estate.db");
      }
      const blob = await res.blob();
      await stream.startAuditWithBlob(blob, 1, "Audited Company S.A. de C.V.", auditMode);
    } catch (e) {
      console.error("Error loading sample estate for audit:", e);
      // Fallback to sample fixture
      onLoadFixture("sample");
      setModalOpen(false);
    }
  }, [stream, onLoadFixture, auditMode]);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const fileArray = Array.from(files);

      // If a SQLite database was provided
      const sqliteFile = fileArray.find((f) => {
        const n = f.name.toLowerCase();
        return n.endsWith(".db") || n.endsWith(".sqlite") || n.endsWith(".sqlite3");
      });
      if (sqliteFile) {
        await handleAuditBlob(sqliteFile);
        return;
      }

      // If CSV file(s) were provided
      const hasCsv = fileArray.some((f) => f.name.toLowerCase().endsWith(".csv"));
      if (hasCsv) {
        const result = await estate.addFiles(fileArray);
        if (result.caseFiles.length > 0) {
          caseFile.loadRaw(result.caseFiles[0].raw, {
            kind: "estate-page",
            label: `From dropped CSV: ${result.caseFiles[0].fileName}`,
          });
          return;
        }
        const bytes = await result.exportSqlite();
        const blob = new Blob([bytes as BlobPart], { type: "application/vnd.sqlite3" });
        await handleAuditBlob(blob);
        return;
      }

      // Otherwise treat as submission.json
      onLoadFile(fileArray[0]);
    },
    [handleAuditBlob, estate, caseFile, onLoadFile]
  );

  const handleOpenCaseFile = useCallback(
    (auditData: any) => {
      setModalOpen(false);
      caseFile.loadRaw(auditData, {
        kind: "api",
        label: `Live Forensic Audit (Seed ${auditData?.seed ?? 1})`,
      });
    },
    [caseFile]
  );

  return (
    <>
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-medium tracking-tight text-foreground">
          Forensic Auditor Workspace
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          Run the deterministic forensic audit in real time connected to the backend via SSE, or load
          a previous verdict file (<code className="font-mono text-xs">submission.json</code>).
        </p>

        {/* Analysis mode: online (n8n enrichment) vs offline (deterministic only) */}
        <div className="mt-6">
          <AnalysisModeSwitch
            mode={auditMode}
            onChange={setAuditMode}
            disabled={stream.isStreaming}
          />
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleAuditSampleEstate}
            disabled={isLoading || stream.isStreaming}
            className="app-primary flex items-center gap-2 text-sm font-semibold py-2 px-4 shadow-lg shadow-brand-500/20"
          >
            <Sparkles className="h-4 w-4" />
            Audit Sample Live (Live SSE)
          </button>

          <button
            type="button"
            onClick={() => onLoadFixture("sample")}
            disabled={isLoading}
            className="app-button flex items-center gap-2 text-sm"
          >
            <FileText className="h-4 w-4" />
            Open sample case
          </button>
        </div>

        {/* State Banner if Estate is already loaded in browser */}
        {estate.hasEstate && (
          <div className="mt-6 rounded-xl border border-brand-500/40 bg-brand-500/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-foreground text-sm flex items-center gap-2">
                  <Database className="h-4 w-4 text-brand-300" />
                  Accounting Database Ready ({estate.totalRows.toLocaleString()} records)
                </h3>
                <p className="text-xs text-muted mt-0.5">
                  The accounting records are in memory. Run deterministic detection with SSE streaming.
                </p>
              </div>
              <button
                type="button"
                onClick={handleLiveAuditFromEstate}
                disabled={stream.isStreaming}
                className="app-primary flex items-center gap-1.5 text-xs font-semibold py-2 px-3.5"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Audit Loaded Data
              </button>
            </div>
          </div>
        )}

        {/* Drop Zone: accepts JSON, SQLite .db, and CSVs */}
        <div
          role="button"
          tabIndex={0}
          onClick={openPicker}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openPicker();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            handleFiles(e.dataTransfer.files);
          }}
          className={`mt-6 flex min-h-36 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
            isDragging ? "border-brand-500 bg-surface-blue" : "border-surface-border bg-surface-raised"
          }`}
        >
          <Upload className="h-6 w-6 text-brand-300" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">
            Drag data here (.db, .csv or submission.json) or click to browse
          </p>
          <p className="text-xs text-muted">
            .db or .csv files run the deterministic forensic audit live. JSON opens the viewer directly.
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".json,.db,.sqlite,.sqlite3,.csv"
            className="sr-only"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        <p className="mt-4 text-xs text-muted">
          Want to inspect or assemble tables individually?{" "}
          <Link href="/investigate/data" className="text-brand-300 hover:text-brand-100 underline">
            Open Data Estate page
          </Link>{" "}
          · Revisit a past verdict in{" "}
          <Link href="/investigate/history" className="text-brand-300 hover:text-brand-100 underline">
            Audit history
          </Link>
        </p>

        {estateNote && <p className="mt-2 text-xs text-status-success">{estateNote}</p>}

        {apiEnabled && onLoadFromApi && (
          <div className="mt-6 flex flex-wrap items-end gap-2 border-t border-surface-border pt-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="backend-case-id" className="text-xs text-muted">
                Backend case ID
              </label>
              <input
                id="backend-case-id"
                type="text"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                className="min-h-11 rounded-md border border-surface-border bg-surface-deep px-3 text-sm text-foreground"
              />
            </div>
            <button
              type="button"
              onClick={() => caseId.trim() && onLoadFromApi(caseId.trim())}
              disabled={!caseId.trim() || isLoading}
              className="app-button text-xs"
            >
              Load from backend
            </button>
          </div>
        )}

        {process.env.NODE_ENV !== "production" && (
          <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-surface-border pt-4">
            <label htmlFor="dev-fixtures" className="text-xs text-muted">
              Developer fixtures
            </label>
            <select
              id="dev-fixtures"
              defaultValue=""
              onChange={(e) => {
                const value = e.target.value as FixtureId | "";
                if (value) onLoadFixture(value);
                e.target.value = "";
              }}
              className="min-h-9 rounded-md border border-surface-border bg-surface-deep px-2 text-xs text-foreground"
            >
              <option value="" disabled>
                Choose a fixture…
              </option>
              {DEV_FIXTURES.map((fixture) => (
                <option key={fixture.id} value={fixture.id}>
                  {fixture.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm text-status-danger">
            {error}
          </p>
        )}
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
