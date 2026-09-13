"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import type {
  ThoughtEvent,
  VerdictEvent,
  AgentStatuses,
  AgentId,
  AuditMode,
  AuditFeedItem,
  AuditProgress,
  FindingReviewedEvent,
  LeadReviewedEvent,
} from "@/types/investigation";

export interface EstateAuditStreamState {
  isStreaming: boolean;
  thoughts: ThoughtEvent[];
  findingsReviewed: FindingReviewedEvent[];
  leadsReviewed: LeadReviewedEvent[];
  feed: AuditFeedItem[];
  progress: AuditProgress;
  streamStartedAt: number | null;
  lastEventAt: number | null;
  verdict: VerdictEvent | null;
  completedAudit: any | null;
  error: string | null;
  currentPhase: string;
  agentStatuses: AgentStatuses;
  startAuditWithBlob: (blob: Blob, seed?: number, companyName?: string, mode?: AuditMode) => Promise<void>;
  startAuditWithPath: (estatePath: string, seed?: number, companyName?: string, mode?: AuditMode) => void;
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
  const [findingsReviewed, setFindingsReviewed] = useState<FindingReviewedEvent[]>([]);
  const [leadsReviewed, setLeadsReviewed] = useState<LeadReviewedEvent[]>([]);
  const [feed, setFeed] = useState<AuditFeedItem[]>([]);
  const [verdict, setVerdict] = useState<VerdictEvent | null>(null);
  const [completedAudit, setCompletedAudit] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentPhase, setCurrentPhase] = useState<string>("Starting...");
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);

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
    setFeed([]);
    setVerdict(null);
    setCompletedAudit(null);
    setError(null);
    setCurrentPhase("Starting...");
    setStreamStartedAt(null);
    setLastEventAt(null);
  }, []);

  const startAuditWithPath = useCallback(
    (estatePath: string, seed: number = 1, companyName: string = "Audited Company S.A. de C.V.", mode: AuditMode = "online") => {
      resetAudit();
      setIsStreaming(true);
      setCurrentPhase(mode === "offline" ? "Connecting to deterministic engine (offline mode)..." : "Connecting to audit engine...");

      let url = `${API_BASE}/api/v1/estates/stream?estate_path=${encodeURIComponent(
        estatePath
      )}&seed=${seed}&company_name=${encodeURIComponent(companyName)}`;
      if (mode === "offline") {
        url += "&n8n_url=offline";
      }

      setStreamStartedAt(Date.now());
      setLastEventAt(null);

      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener("thought", (event: MessageEvent) => {
        try {
          const data: ThoughtEvent = JSON.parse(event.data);
          setThoughts((prev) => [...prev, data]);
          setFeed((prev) => [...prev, { kind: "thought", receivedAt: Date.now(), data }]);
          setLastEventAt(Date.now());
          if (data.phase) {
            setCurrentPhase(data.phase);
          }
        } catch (e) {
          console.error("Error parsing thought event:", e);
        }
      });

      es.addEventListener("finding_reviewed", (event: MessageEvent) => {
        try {
          const data: FindingReviewedEvent = JSON.parse(event.data);
          setFindingsReviewed((prev) => [...prev, data]);
          setFeed((prev) => [...prev, { kind: "finding", receivedAt: Date.now(), data }]);
          setLastEventAt(Date.now());
        } catch (e) {
          console.error("Error parsing finding_reviewed event:", e);
        }
      });

      es.addEventListener("lead_reviewed", (event: MessageEvent) => {
        try {
          const data: LeadReviewedEvent = JSON.parse(event.data);
          setLeadsReviewed((prev) => [...prev, data]);
          setFeed((prev) => [...prev, { kind: "lead", receivedAt: Date.now(), data }]);
          setLastEventAt(Date.now());
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
          setCurrentPhase("Audit Completed Successfully");
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
          setError(data.error || "Error in the audit pipeline");
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
            setError("Connection to the server was interrupted or terminated.");
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
    async (blob: Blob, seed: number = 1, companyName: string = "Audited Company S.A. de C.V.", mode: AuditMode = "online") => {
      resetAudit();
      setIsStreaming(true);
      setCurrentPhase("Preparing and uploading database...");

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
          throw new Error(`Upload error (HTTP ${uploadRes.status})`);
        }

        const uploadData = await uploadRes.json();
        const path = uploadData.estate_path;
        if (!path) {
          throw new Error("The backend did not return the database path.");
        }

        startAuditWithPath(path, seed, companyName, mode);
      } catch (err: any) {
        setIsStreaming(false);
        setError(err?.message || "Could not connect to the server.");
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

  const progress = useMemo<AuditProgress>(() => {
    const lastFinding = findingsReviewed[findingsReviewed.length - 1];
    const lastLead = leadsReviewed[leadsReviewed.length - 1];
    return {
      findingsDone: findingsReviewed.length,
      findingsTotal: lastFinding?.total ?? 0,
      leadsDone: leadsReviewed.length,
      leadsTotal: lastLead?.total ?? 0,
    };
  }, [findingsReviewed, leadsReviewed]);

  return {
    isStreaming,
    thoughts,
    findingsReviewed,
    leadsReviewed,
    feed,
    progress,
    streamStartedAt,
    lastEventAt,
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
