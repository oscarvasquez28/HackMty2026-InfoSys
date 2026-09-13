"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import type { ThoughtEvent, VerdictEvent, AgentStatuses, AgentId } from "@/types/investigation";

export interface EstateAuditStreamState {
  isStreaming: boolean;
  thoughts: ThoughtEvent[];
  findingsReviewed: any[];
  leadsReviewed: any[];
  verdict: VerdictEvent | null;
  completedAudit: any | null;
  error: string | null;
  currentPhase: string;
  agentStatuses: AgentStatuses;
  startAuditWithBlob: (blob: Blob, seed?: number, companyName?: string) => Promise<void>;
  startAuditWithPath: (estatePath: string, seed?: number, companyName?: string) => void;
  resetAudit: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const INITIAL_AGENT_STATUSES: AgentStatuses = {
  ORCHESTRATOR: "waiting",
  DATA_VALIDATION: "waiting",
  CIRCULAR_FLOWS: "waiting",
  PASSTHROUGH: "waiting",
  RISK_REVIEW: "waiting",
};

export function useEstateAuditStream(): EstateAuditStreamState {
  const [isStreaming, setIsStreaming] = useState(false);
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [findingsReviewed, setFindingsReviewed] = useState<any[]>([]);
  const [leadsReviewed, setLeadsReviewed] = useState<any[]>([]);
  const [verdict, setVerdict] = useState<VerdictEvent | null>(null);
  const [completedAudit, setCompletedAudit] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentPhase, setCurrentPhase] = useState<string>("Iniciando...");

  const eventSourceRef = useRef<EventSource | null>(null);

  const resetAudit = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
    setThoughts([]);
    setFindingsReviewed([]);
    setLeadsReviewed([]);
    setVerdict(null);
    setCompletedAudit(null);
    setError(null);
    setCurrentPhase("Iniciando...");
  }, []);

  const startAuditWithPath = useCallback(
    (estatePath: string, seed: number = 1, companyName: string = "Empresa Auditada S.A. de C.V.") => {
      resetAudit();
      setIsStreaming(true);
      setCurrentPhase("Conectando al motor determinista...");

      const url = `${API_BASE}/api/v1/estates/stream?estate_path=${encodeURIComponent(
        estatePath
      )}&seed=${seed}&company_name=${encodeURIComponent(companyName)}`;

      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener("thought", (event: MessageEvent) => {
        try {
          const data: ThoughtEvent = JSON.parse(event.data);
          setThoughts((prev) => [...prev, data]);
          if (data.phase) {
            setCurrentPhase(data.phase);
          }
        } catch (e) {
          console.error("Error parsing thought event:", e);
        }
      });

      es.addEventListener("finding_reviewed", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setFindingsReviewed((prev) => [...prev, data]);
        } catch (e) {
          console.error("Error parsing finding_reviewed event:", e);
        }
      });

      es.addEventListener("lead_reviewed", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setLeadsReviewed((prev) => [...prev, data]);
        } catch (e) {
          console.error("Error parsing lead_reviewed event:", e);
        }
      });

      es.addEventListener("verdict", (event: MessageEvent) => {
        try {
          const data: VerdictEvent = JSON.parse(event.data);
          setVerdict(data);
        } catch (e) {
          console.error("Error parsing verdict event:", e);
        }
      });

      es.addEventListener("audit_completed", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setCompletedAudit(data);
          setIsStreaming(false);
          setCurrentPhase("Auditoría Finalizada con Éxito");
          es.close();
          eventSourceRef.current = null;
        } catch (e) {
          console.error("Error parsing audit_completed event:", e);
          setIsStreaming(false);
        }
      });

      es.addEventListener("error", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setError(data.error || "Error en el pipeline de auditoría");
        } catch {
          // If connection closed normally or failed
          if (es.readyState === EventSource.CLOSED) {
            setIsStreaming(false);
          }
        }
      });

      es.onerror = () => {
        // Only set error if not completed
        setCompletedAudit((curr: any) => {
          if (!curr) {
            setError("Conexión con el servidor interrumpida o terminada.");
            setIsStreaming(false);
          }
          return curr;
        });
        es.close();
        eventSourceRef.current = null;
      };
    },
    [resetAudit]
  );

  const startAuditWithBlob = useCallback(
    async (blob: Blob, seed: number = 1, companyName: string = "Empresa Auditada S.A. de C.V.") => {
      resetAudit();
      setIsStreaming(true);
      setCurrentPhase("Preparando y subiendo base de datos...");

      try {
        const form = new FormData();
        form.append("file", blob, "estate.db");
        form.append("seed", String(seed));
        form.append("company_name", companyName);
        form.append("audit", "false");

        const uploadRes = await fetch(`${API_BASE}/api/v1/estates/upload`, {
          method: "POST",
          body: form,
        });

        if (!uploadRes.ok) {
          throw new Error(`Error en subida (HTTP ${uploadRes.status})`);
        }

        const uploadData = await uploadRes.json();
        const path = uploadData.estate_path;
        if (!path) {
          throw new Error("El backend no retornó la ruta de la base de datos.");
        }

        startAuditWithPath(path, seed, companyName);
      } catch (err: any) {
        setIsStreaming(false);
        setError(err?.message || "No se pudo conectar con el servidor.");
      }
    },
    [resetAudit, startAuditWithPath]
  );

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const agentStatuses = useMemo<AgentStatuses>(() => {
    const statuses: AgentStatuses = { ...INITIAL_AGENT_STATUSES };
    for (const t of thoughts) {
      const agent = (t.agent_id as AgentId) || "ORCHESTRATOR";
      if (t.action === "started" || t.action === "finding" || t.action === "synthesizing") {
        statuses[agent] = "reviewing";
      } else if (t.action === "returned") {
        statuses[agent] = "returned";
      }
    }
    if (verdict) {
      statuses.ORCHESTRATOR = "complete";
    }
    if (error) {
      for (const agent of Object.keys(statuses) as AgentId[]) {
        if (statuses[agent] === "reviewing") {
          statuses[agent] = "interrupted";
        }
      }
    }
    return statuses;
  }, [thoughts, verdict, error]);

  return {
    isStreaming,
    thoughts,
    findingsReviewed,
    leadsReviewed,
    verdict,
    completedAudit,
    error,
    currentPhase,
    agentStatuses,
    startAuditWithBlob,
    startAuditWithPath,
    resetAudit,
  };
}
