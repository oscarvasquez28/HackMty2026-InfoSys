"use client";

// Shared session state for the /investigate route group: the loaded case file (and, once Phase 6
// lands, the loaded data estate) survive navigation between /investigate and /investigate/data
// within the same browser tab, but not a reload -- there is no server-side persistence by design.

import React, { createContext, useContext, useState } from "react";
import { useCaseFileSource, type UseCaseFileSourceReturn } from "@/hooks/useCaseFileSource";
import { useEstate, type UseEstateReturn } from "@/hooks/useEstate";
import type { AuditMode } from "@/types/investigation";

interface InvestigateSessionValue {
  caseFile: UseCaseFileSourceReturn;
  estate: UseEstateReturn;
  auditMode: AuditMode;
  setAuditMode: (mode: AuditMode) => void;
}

const InvestigateSessionContext = createContext<InvestigateSessionValue | null>(null);

export const InvestigateSessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const caseFile = useCaseFileSource();
  const estate = useEstate();
  const [auditMode, setAuditMode] = useState<AuditMode>("online");
  return (
    <InvestigateSessionContext.Provider value={{ caseFile, estate, auditMode, setAuditMode }}>
      {children}
    </InvestigateSessionContext.Provider>
  );
};

export function useInvestigateSession(): InvestigateSessionValue {
  const value = useContext(InvestigateSessionContext);
  if (!value) {
    throw new Error("useInvestigateSession must be used within an InvestigateSessionProvider");
  }
  return value;
}
