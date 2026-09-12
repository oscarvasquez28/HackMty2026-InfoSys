"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { ThoughtEvent, VerdictEvent } from "@/types/investigation";

interface UseInvestigationStreamReturn {
  thoughts: ThoughtEvent[];
  verdict: VerdictEvent | null;
  isStreaming: boolean;
  error: string | null;
  startStream: (caseId: string) => void;
  resetStream: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useInvestigationStream(): UseInvestigationStreamReturn {
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [verdict, setVerdict] = useState<VerdictEvent | null>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const resetStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setThoughts([]);
    setVerdict(null);
    setIsStreaming(false);
    setError(null);
  }, []);

  const startStream = useCallback(
    (caseId: string) => {
      resetStream();
      setIsStreaming(true);

      const url = `${API_BASE}/api/v1/investigations/${caseId}/stream`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener("thought", (e: MessageEvent) => {
        try {
          const data: ThoughtEvent = JSON.parse(e.data);
          setThoughts((prev) => [...prev, data]);
        } catch (err) {
          console.error("Failed to parse thought event data", err);
        }
      });

      es.addEventListener("verdict", (e: MessageEvent) => {
        try {
          const data: VerdictEvent = JSON.parse(e.data);
          setVerdict(data);
          setIsStreaming(false);
          es.close();
        } catch (err) {
          console.error("Failed to parse verdict event data", err);
        }
      });

      es.onerror = (err) => {
        console.error("SSE connection error", err);
        setError("Error en la conexión del flujo de razonamiento pericial.");
        setIsStreaming(false);
        es.close();
      };
    },
    [resetStream]
  );

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    thoughts,
    verdict,
    isStreaming,
    error,
    startStream,
    resetStream,
  };
}
