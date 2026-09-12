"use client";

// Empty-state loader for the case file viewer: the illustrative sample, a local submission.json
// file (drag-drop or browse), the proposed backend endpoint when enabled, and -- in development
// only -- the three developer fixtures used to exercise the renderer's edge cases.

import React, { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { FileText, Upload } from "lucide-react";
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
  const [isDragging, setIsDragging] = useState(false);
  const [caseId, setCaseId] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const openPicker = useCallback(() => inputRef.current?.click(), []);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (files && files.length > 0) onLoadFile(files[0]);
    },
    [onLoadFile]
  );

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
      <h1 className="text-2xl font-medium tracking-tight text-foreground">Open a forensic case file</h1>
      <p className="mt-2 text-sm leading-6 text-muted">
        Load the JSON your auditor run produced — the same submission.json checked by validate_format.py — to
        render the case file, or open the illustrative sample.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => onLoadFixture("sample")} disabled={isLoading} className="app-primary flex items-center gap-2 text-sm">
          <FileText className="h-4 w-4" aria-hidden="true" />
          Open sample case
        </button>
      </div>

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
        className={`mt-6 flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          isDragging ? "border-brand-500 bg-surface-blue" : "border-surface-border bg-surface-raised"
        }`}
      >
        <Upload className="h-5 w-5 text-brand-300" aria-hidden="true" />
        <p className="text-sm text-foreground">Drop submission JSON here or browse</p>
        <p className="text-xs text-muted">Read locally in your browser. Nothing is uploaded. Max 5 MB.</p>
        <input
          ref={inputRef}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <p className="mt-4 text-xs text-muted">
        Have .db, .csv or .xml estate data?{" "}
        <Link href="/investigate/data" className="text-brand-300 hover:text-brand-50">
          Open the Data estate page
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
  );
};
