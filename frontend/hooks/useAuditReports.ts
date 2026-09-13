"use client";

// Fetches the persisted audit report history from the backend's /api/v1/reports
// endpoints. The list endpoint reports `database_enabled` so the UI can tell
// "no history stored" apart from "history storage is not configured".

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AuditReportDetail,
  AuditReportListResponse,
  AuditReportSummary,
} from "@/types/reports";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PAGE_SIZE = 20;

export interface UseAuditReportsReturn {
  reports: AuditReportSummary[];
  total: number;
  totalPages: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  error: string | null;
  databaseEnabled: boolean | null;
  fetchPage: (page: number) => Promise<void>;
  refresh: () => Promise<void>;
  loadReportDetail: (runId: string) => Promise<AuditReportDetail | null>;
}

export function useAuditReports(): UseAuditReportsReturn {
  const [reports, setReports] = useState<AuditReportSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [databaseEnabled, setDatabaseEnabled] = useState<boolean | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchPage = useCallback(async (targetPage: number) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsLoading(true);
    setError(null);

    try {
      const url = `${API_BASE}/api/v1/reports?page=${targetPage}&page_size=${PAGE_SIZE}`;
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`Backend request failed (HTTP ${response.status}).`);
      }
      const data: AuditReportListResponse = await response.json();
      setReports(data.items ?? []);
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
      setPage(data.page ?? targetPage);
      setDatabaseEnabled(data.database_enabled ?? false);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the backend reports service."
      );
      setDatabaseEnabled(null);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  const refresh = useCallback(async () => {
    await fetchPage(page);
  }, [fetchPage, page]);

  const loadReportDetail = useCallback(
    async (runId: string): Promise<AuditReportDetail | null> => {
      try {
        const url = `${API_BASE}/api/v1/reports/${encodeURIComponent(runId)}`;
        const response = await fetch(url);
        if (!response.ok) {
          setError(
            response.status === 404
              ? `Report '${runId}' was not found in the audit history.`
              : `Backend request failed (HTTP ${response.status}).`
          );
          return null;
        }
        return (await response.json()) as AuditReportDetail;
      } catch {
        setError("Backend unreachable. Could not load the stored report.");
        return null;
      }
    },
    []
  );

  useEffect(() => {
    void fetchPage(1);
    return () => abortRef.current?.abort();
  }, [fetchPage]);

  return {
    reports,
    total,
    totalPages,
    page,
    pageSize: PAGE_SIZE,
    isLoading,
    error,
    databaseEnabled,
    fetchPage,
    refresh,
    loadReportDetail,
  };
}
