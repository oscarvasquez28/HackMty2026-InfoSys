"use client";

// Export actions for a loaded case file (Print/PDF, standalone HTML, Markdown, raw JSON), shared by
// the top ExportToolbar and the guided tour's closing screen. Print and HTML read the full printable
// document (#case-file-document), which stays mounted but hidden on screen.

import { useCallback, useMemo } from "react";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";
import { buildCaseFileMarkdown } from "@/lib/caseFile/toMarkdown";
import { buildStandaloneHtml } from "@/lib/caseFile/toHtml";
import { downloadTextFile } from "@/lib/caseFile/download";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { LoadedCaseFile } from "@/hooks/useCaseFileSource";

export interface UseCaseFileExportsReturn {
  ready: boolean;
  buildMarkdown: () => string;
  buildHtml: () => string;
  printDocument: () => void;
  downloadHtml: () => void;
  downloadMarkdown: () => void;
  downloadJson: () => void;
}

export function useCaseFileExports(loaded: LoadedCaseFile, view: CaseFileView, estateChecked: boolean): UseCaseFileExportsReturn {
  const { diagrams, diagramsSettled } = useCaseFileUi();
  const seedLabel = loaded.document.seed ?? "unknown";
  const isSample = loaded.source.kind === "sample";

  const renderedSources = useMemo(() => {
    const map: Record<string, string | null> = {};
    for (const [id, state] of Object.entries(diagrams)) {
      map[id] = state.renderedSource;
    }
    return map;
  }, [diagrams]);

  const buildMarkdown = useCallback(
    () => buildCaseFileMarkdown(view, { isSample, renderedSources, estateChecked }),
    [view, isSample, renderedSources, estateChecked]
  );

  const buildHtml = useCallback(() => {
    const el = document.getElementById("case-file-document");
    if (!el) throw new Error("case-file-document not mounted");
    return buildStandaloneHtml({ documentElement: el, title: `Case file · seed ${seedLabel}`, raw: loaded.raw });
  }, [seedLabel, loaded.raw]);

  const printDocument = useCallback(() => window.print(), []);
  const downloadHtml = useCallback(
    () => downloadTextFile(`case-file-seed-${seedLabel}.html`, buildHtml(), "text/html;charset=utf-8"),
    [seedLabel, buildHtml]
  );
  const downloadMarkdown = useCallback(
    () => downloadTextFile(`case-file-seed-${seedLabel}.md`, buildMarkdown(), "text/markdown;charset=utf-8"),
    [seedLabel, buildMarkdown]
  );
  const downloadJson = useCallback(
    () => downloadTextFile(`submission-seed-${seedLabel}.json`, `${JSON.stringify(loaded.raw, null, 2)}\n`, "application/json"),
    [seedLabel, loaded.raw]
  );

  return { ready: diagramsSettled, buildMarkdown, buildHtml, printDocument, downloadHtml, downloadMarkdown, downloadJson };
}
