"use client";

// UI-only state for one loaded case file: which sections are expanded/collapsed, and whether every
// money-trail diagram has finished attempting to render. Export buttons wait on diagramsSettled so a
// Markdown/HTML export never fires before a diagram's final source (primary or fallback) is known.

import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

export type DiagramStatus = "pending" | "ready" | "failed";
export interface DiagramState {
  status: DiagramStatus;
  renderedSource: string | null;
  usedFallback: boolean;
}

interface CaseFileUiContextValue {
  isOpen: (id: string, defaultOpen: boolean) => boolean;
  setOpen: (id: string, open: boolean) => void;
  expandAll: () => void;
  collapseAll: () => void;
  reportDiagram: (id: string, state: DiagramState) => void;
  diagrams: Record<string, DiagramState>;
  diagramsSettled: boolean;
}

const CaseFileUiContext = createContext<CaseFileUiContextValue | null>(null);

export const CaseFileUiProvider: React.FC<{ expectedDiagramIds: string[]; children: React.ReactNode }> = ({
  expectedDiagramIds,
  children,
}) => {
  const [openMap, setOpenMap] = useState<Record<string, boolean>>({});
  const [override, setOverride] = useState<boolean | null>(null);
  const [diagrams, setDiagrams] = useState<Record<string, DiagramState>>({});

  const isOpen = useCallback(
    (id: string, defaultOpen: boolean) => openMap[id] ?? override ?? defaultOpen,
    [openMap, override]
  );

  const setOpen = useCallback((id: string, open: boolean) => {
    setOpenMap((prev) => ({ ...prev, [id]: open }));
  }, []);

  const expandAll = useCallback(() => {
    setOverride(true);
    setOpenMap({});
  }, []);

  const collapseAll = useCallback(() => {
    setOverride(false);
    setOpenMap({});
  }, []);

  const reportDiagram = useCallback((id: string, state: DiagramState) => {
    setDiagrams((prev) => {
      const existing = prev[id];
      if (existing && existing.status === state.status && existing.renderedSource === state.renderedSource && existing.usedFallback === state.usedFallback) {
        return prev;
      }
      return { ...prev, [id]: state };
    });
  }, []);

  const diagramsSettled = useMemo(
    () => expectedDiagramIds.every((id) => diagrams[id] && diagrams[id].status !== "pending"),
    [expectedDiagramIds, diagrams]
  );

  const value = useMemo<CaseFileUiContextValue>(
    () => ({ isOpen, setOpen, expandAll, collapseAll, reportDiagram, diagrams, diagramsSettled }),
    [isOpen, setOpen, expandAll, collapseAll, reportDiagram, diagrams, diagramsSettled]
  );

  return <CaseFileUiContext.Provider value={value}>{children}</CaseFileUiContext.Provider>;
};

export function useCaseFileUi(): CaseFileUiContextValue {
  const value = useContext(CaseFileUiContext);
  if (!value) {
    throw new Error("useCaseFileUi must be used within a CaseFileUiProvider");
  }
  return value;
}
