"use client";

// Top-level shell for /investigate/data: upload, per-file status, per-table summary/preview,
// estate-wide issues, and export. Shares its estate state with the case file viewer via
// InvestigateSessionProvider so exhibits can be checked against it without leaving the tab.

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useInvestigateSession } from "@/components/investigate/InvestigateSessionProvider";
import { InvestigateAppBar } from "@/components/investigate/InvestigateAppBar";
import { EstateUploadZone } from "@/components/estate/EstateUploadZone";
import { EstateFileList } from "@/components/estate/EstateFileList";
import { EstateTableSummary } from "@/components/estate/EstateTableSummary";
import { EstateTablePreview } from "@/components/estate/EstateTablePreview";
import { EstateIssuesPanel } from "@/components/estate/EstateIssuesPanel";
import { EstateExportBar } from "@/components/estate/EstateExportBar";
import { ESTATE_TABLE_ORDER } from "@/lib/estate/schema";
import { parseSqliteFile } from "@/lib/estate/sqlite";
import type { SourceTable } from "@/types/caseFile";

const SAMPLE_FILES = ["vendors.csv", "estate.partial.json", "cfdi-INV-00101.xml", "cfdi-INV-00102.xml"];

declare global {
  interface Window {
    __estateDebug?: {
      ingestText: (fileName: string, content: string) => Promise<void>;
      exportSqliteBase64: () => Promise<string>;
      roundTripSqlite: () => Promise<{ equal: boolean; counts: Record<string, number> }>;
      summary: () => { rows: Record<string, number>; errors: number; warnings: number };
    };
  }
}

export const DataEstateWorkspace: React.FC = () => {
  const { caseFile, estate } = useInvestigateSession();
  const [selectedTable, setSelectedTable] = useState<SourceTable>("vendors");
  const [loadedCaseFileNotice, setLoadedCaseFileNotice] = useState<string | null>(null);

  const handleLoadSample = async () => {
    const files = await Promise.all(
      SAMPLE_FILES.map(async (name) => {
        const response = await fetch(`/samples/estate/${name}`);
        const blob = await response.blob();
        return new File([blob], name, { type: blob.type });
      })
    );
    const { caseFiles } = await estate.addFiles(files);
    if (caseFiles.length > 0) {
      caseFile.loadRaw(caseFiles[0].raw, { kind: "estate-page", label: `From Data estate page: ${caseFiles[0].fileName}` });
      setLoadedCaseFileNotice(caseFiles[0].fileName);
    }
  };

  const handleFiles = async (files: File[]) => {
    const { caseFiles } = await estate.addFiles(files);
    if (caseFiles.length > 0) {
      caseFile.loadRaw(caseFiles[0].raw, { kind: "estate-page", label: `From Data estate page: ${caseFiles[0].fileName}` });
      setLoadedCaseFileNotice(caseFiles[0].fileName);
    }
  };

  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    window.__estateDebug = {
      ingestText: async (fileName, content) => {
        const file = new File([content], fileName);
        await estate.addFiles([file]);
      },
      exportSqliteBase64: async () => {
        const bytes = await estate.exportSqlite();
        let binary = "";
        bytes.forEach((b) => {
          binary += String.fromCharCode(b);
        });
        return btoa(binary);
      },
      roundTripSqlite: async () => {
        const bytes = await estate.exportSqlite();
        const parsed = await parseSqliteFile(bytes, "roundtrip.db");
        const counts: Record<string, number> = {};
        let equal = true;
        for (const table of ESTATE_TABLE_ORDER) {
          counts[table] = estate.tables[table].length;
          const roundTripRows = parsed.contributions[table] ?? [];
          if (JSON.stringify(roundTripRows) !== JSON.stringify(estate.tables[table])) equal = false;
        }
        return { equal, counts };
      },
      summary: () => {
        const rows: Record<string, number> = {};
        for (const table of ESTATE_TABLE_ORDER) rows[table] = estate.tables[table].length;
        return {
          rows,
          errors: estate.issues.filter((i) => i.severity === "error").length,
          warnings: estate.issues.filter((i) => i.severity === "warning").length,
        };
      },
    };
    return () => {
      delete window.__estateDebug;
    };
  }, [estate]);

  return (
    <div className="case-workspace min-h-[100dvh] bg-background text-foreground">
      <InvestigateAppBar />
      <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6">
        <h1 className="text-2xl font-medium tracking-tight text-foreground">Data estate</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Load the company&apos;s data estate — SQLite .db, CSV per table, CFDI 4.0 XML invoices, or JSON — and check it
          against estate_schema.sql. Everything is processed locally in this browser tab and is cleared when the page
          reloads.
        </p>

        {loadedCaseFileNotice && (
          <p className="mt-3 rounded-md border border-brand-500/30 bg-surface-blue px-3 py-2 text-xs text-brand-300">
            Case file loaded from {loadedCaseFileNotice} —{" "}
            <Link href="/investigate" className="underline">
              open the viewer
            </Link>
            .
          </p>
        )}

        {estate.hasEstate && (
          <p className="mt-3 text-xs text-muted">
            Data estate loaded ({estate.totalRows.toLocaleString("en-US")} rows). Exhibits will be checked against it in
            the case file viewer.
          </p>
        )}

        <section className="mt-6">
          <EstateUploadZone
            isProcessing={estate.status === "processing"}
            onFiles={handleFiles}
            onLoadSample={handleLoadSample}
            onClear={estate.clear}
            hasFiles={estate.files.length > 0}
          />
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-medium text-foreground">Files</h2>
          <div className="mt-3">
            <EstateFileList files={estate.files} onAssignTable={estate.assignTable} onRemove={estate.removeFile} />
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-medium text-foreground">Tables</h2>
          <div className="mt-3">
            <EstateTableSummary tables={estate.tables} issues={estate.issues} selected={selectedTable} onSelect={setSelectedTable} />
          </div>
          <div className="mt-4">
            <EstateTablePreview table={selectedTable} tables={estate.tables} issues={estate.issues} />
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-medium text-foreground">Issues</h2>
          <div className="mt-3">
            <EstateIssuesPanel issues={estate.issues} />
          </div>
        </section>

        <section className="mt-8 border-t border-surface-border pt-6">
          <EstateExportBar exportSqlite={estate.exportSqlite} exportJson={estate.exportJson} hasEstate={estate.hasEstate} />
        </section>
      </div>
    </div>
  );
};
