"use client";

// Loads a case file JSON from a bundled fixture, a local file, an in-memory raw object (e.g. handed
// off from the Data estate page), or the backend's proposed case-file endpoint. Normalizes and
// structurally validates every load so CaseFileWorkspace always receives a renderable document plus
// its format-check issues, regardless of source.

import { useCallback, useRef, useState } from "react";
import { normalizeCaseFile } from "@/lib/caseFile/normalize";
import { validateStructure } from "@/lib/caseFile/validate";
import { MAX_JSON_BYTES } from "@/lib/caseFile/constants";
import type { CaseFileDocument, ValidationIssue } from "@/types/caseFile";

import sampleFixture from "@/fixtures/case-file.sample.json";
import noFindingsFixture from "@/fixtures/case-file.no-findings.json";
import edgeCasesFixture from "@/fixtures/case-file.edge-cases.json";

export type CaseFileSourceKind = "sample" | "file" | "estate-page" | "api";
export type FixtureId = "sample" | "no-findings" | "edge-cases";

export interface CaseFileSource {
  kind: CaseFileSourceKind;
  label: string;
}

export interface LoadedCaseFile {
  raw: unknown;
  document: CaseFileDocument;
  structureIssues: ValidationIssue[];
  source: CaseFileSource;
  loadId: number;
}

export interface UseCaseFileSourceReturn {
  status: "idle" | "loading" | "ready" | "error";
  loaded: LoadedCaseFile | null;
  error: string | null;
  loadFixture: (id: FixtureId) => void;
  loadFile: (file: File) => Promise<void>;
  loadRaw: (raw: unknown, source: CaseFileSource) => void;
  loadFromApi: (caseId: string) => Promise<void>;
  reset: () => void;
}

const FIXTURES: Record<FixtureId, { data: unknown; label: string }> = {
  sample: { data: sampleFixture, label: "Sample case (illustrative)" },
  "no-findings": { data: noFindingsFixture, label: "Sample: no findings (illustrative)" },
  "edge-cases": { data: edgeCasesFixture, label: "Sample: edge cases (invalid on purpose)" },
};

const ESTATE_EXTENSION_RE = /\.(db|sqlite|sqlite3|csv|xml)$/i;

export function useCaseFileSource(): UseCaseFileSourceReturn {
  const [status, setStatus] = useState<UseCaseFileSourceReturn["status"]>("idle");
  const [loaded, setLoaded] = useState<LoadedCaseFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadCounter = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const applyRaw = useCallback((raw: unknown, source: CaseFileSource) => {
    const result = normalizeCaseFile(raw);
    if (!result.ok) {
      setStatus("error");
      setError(result.error);
      return;
    }
    loadCounter.current += 1;
    setLoaded({
      raw,
      document: result.document,
      structureIssues: validateStructure(raw),
      source,
      loadId: loadCounter.current,
    });
    setStatus("ready");
    setError(null);
  }, []);

  const loadFixture = useCallback(
    (id: FixtureId) => {
      const fixture = FIXTURES[id];
      applyRaw(fixture.data, { kind: "sample", label: fixture.label });
    },
    [applyRaw]
  );

  const loadRaw = useCallback(
    (raw: unknown, source: CaseFileSource) => {
      applyRaw(raw, source);
    },
    [applyRaw]
  );

  const loadFile = useCallback(
    async (file: File) => {
      setStatus("loading");
      setError(null);

      if (ESTATE_EXTENSION_RE.test(file.name)) {
        setStatus("error");
        setError("This is data estate input. Open it from the Data estate page.");
        return;
      }
      if (!file.name.toLowerCase().endsWith(".json")) {
        setStatus("error");
        setError("Select a .json file produced by the auditor (submission.json).");
        return;
      }
      if (file.size > MAX_JSON_BYTES) {
        setStatus("error");
        setError("File exceeds 5 MB.");
        return;
      }

      let text: string;
      try {
        text = await file.text();
      } catch {
        setStatus("error");
        setError("Could not read the file.");
        return;
      }

      let raw: unknown;
      try {
        raw = JSON.parse(text);
      } catch (e) {
        setStatus("error");
        setError(`Invalid JSON: ${e instanceof Error ? e.message : String(e)}`);
        return;
      }

      applyRaw(raw, { kind: "file", label: `Local file: ${file.name}` });
    },
    [applyRaw]
  );

  const loadFromApi = useCallback(
    async (caseId: string) => {
      setStatus("loading");
      setError(null);
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeout = setTimeout(() => controller.abort(), 15000);

      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const url = `${base}/api/v1/investigations/${encodeURIComponent(caseId)}/case-file`;

      try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          if (response.status === 404) {
            setStatus("error");
            setError("The backend does not expose a case file for this case yet (HTTP 404).");
          } else {
            setStatus("error");
            setError(`Backend request failed (HTTP ${response.status}).`);
          }
          return;
        }
        const raw = await response.json();
        applyRaw(raw, { kind: "api", label: `Backend case ${caseId}` });
      } catch {
        setStatus("error");
        setError("Backend unreachable. Load a local JSON file instead.");
      } finally {
        clearTimeout(timeout);
      }
    },
    [applyRaw]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
    setLoaded(null);
    setError(null);
  }, []);

  return { status, loaded, error, loadFixture, loadFile, loadRaw, loadFromApi, reset };
}
