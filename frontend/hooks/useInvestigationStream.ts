"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { ThoughtEvent, VerdictEvent, AgentStatuses, ReviewSource, isThoughtEvent, isVerdictEvent } from "@/types/investigation";

interface UseInvestigationStreamReturn {
  thoughts: ThoughtEvent[];
  verdict: VerdictEvent | null;
  isStreaming: boolean;
  error: string | null;
  source: ReviewSource | null;
  agentStatuses: AgentStatuses;
  startStream: (caseId: string) => void;
  resetStream: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useInvestigationStream(): UseInvestigationStreamReturn {
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [verdict, setVerdict] = useState<VerdictEvent | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const resetStream = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setThoughts([]);
    setVerdict(null);
    setIsStreaming(false);
    setError(null);
  }, []);

  const startStream = useCallback((caseId: string) => {
    resetStream();
    setIsStreaming(true);
    const es = new EventSource(`${API_BASE}/api/v1/investigations/${encodeURIComponent(caseId)}/stream`);
    eventSourceRef.current = es;
    const seen = new Set<string>();
    const fail = (message: string) => {
      if (eventSourceRef.current !== es) return;
      es.close();
      eventSourceRef.current = null;
      setError(message);
      setIsStreaming(false);
    };

    es.addEventListener("thought", (event: MessageEvent) => {
      if (eventSourceRef.current !== es) return;
      try {
        const data: unknown = JSON.parse(event.data);
        if (!isThoughtEvent(data)) throw new Error("Invalid review event");
        if (data.event_id && seen.has(data.event_id)) return;
        if (data.event_id) seen.add(data.event_id);
        setThoughts(previous => [...previous, data]);
      } catch {
        fail("An update could not be read. The review is incomplete. Retry to restart it.");
      }
    });

    es.addEventListener("verdict", (event: MessageEvent) => {
      if (eventSourceRef.current !== es) return;
      try {
        const data: unknown = JSON.parse(event.data);
        if (!isVerdictEvent(data) || data.case_id !== caseId) throw new Error("Invalid assessment");
        setVerdict(data);
        setIsStreaming(false);
        es.close();
        eventSourceRef.current = null;
      } catch {
        fail("The final assessment could not be verified. Retry the review; no outcome has been assumed.");
      }
    });

    es.onerror = () => fail("The connection was interrupted. Retry the review, or upload again if the backend has restarted.");
  }, [resetStream]);

  useEffect(() => () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }, []);

  const agentStatuses = useMemo<AgentStatuses>(() => {
    const statuses: AgentStatuses = {
      ORCHESTRATOR: "waiting", DATA_VALIDATION: "waiting", CIRCULAR_FLOWS: "waiting", PASSTHROUGH: "waiting", RISK_REVIEW: "waiting",
    };
    const fallbackIndex = thoughts.map(thought => thought.action).lastIndexOf("fallback");
    for (const thought of thoughts.slice(Math.max(0, fallbackIndex))) {
      const agent = thought.agent_id || "ORCHESTRATOR";
      if (thought.action === "returned") statuses[agent] = "returned";
      else if (thought.action === "started" || thought.action === "finding" || thought.action === "synthesizing") statuses[agent] = "reviewing";
    }
    if (verdict) statuses.ORCHESTRATOR = "complete";
    if (error) {
      for (const agent of Object.keys(statuses) as Array<keyof AgentStatuses>) {
        if (statuses[agent] === "reviewing") statuses[agent] = "interrupted";
      }
    }
    return statuses;
  }, [thoughts, verdict, error]);

  return {
    thoughts, verdict, isStreaming, error, agentStatuses,
    source: verdict?.source || thoughts[thoughts.length - 1]?.source || null,
    startStream, resetStream,
  };
}
