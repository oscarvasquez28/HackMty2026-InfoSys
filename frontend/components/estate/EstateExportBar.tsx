"use client";

// Export actions for the assembled estate: a real SQLite file (importable back into this page, or
// judged offline with validate_format.py --estate) and a plain JSON dump.

import React, { useState } from "react";
import Link from "next/link";
import { downloadTextFile } from "@/lib/caseFile/download";

interface EstateExportBarProps {
  exportSqlite: () => Promise<Uint8Array>;
  exportJson: () => string;
  hasEstate: boolean;
}

const UPLOAD_API_ENABLED = process.env.NEXT_PUBLIC_ESTATE_UPLOAD_API === "enabled";

export const EstateExportBar: React.FC<EstateExportBarProps> = ({ exportSqlite, exportJson, hasEstate }) => {
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleSqlite = async () => {
    const bytes = await exportSqlite();
    downloadTextFile("estate.db", bytes, "application/vnd.sqlite3");
  };

  const handleJson = () => downloadTextFile("estate.json", exportJson(), "application/json");

  const handleUpload = async () => {
    setUploadStatus("Uploading…");
    try {
      const bytes = await exportSqlite();
      const form = new FormData();
      form.append("file", new Blob([bytes as BlobPart], { type: "application/vnd.sqlite3" }), "estate.db");
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${base}/api/v1/estates/upload`, { method: "POST", body: form });
      if (response.status === 404) {
        setUploadStatus("The backend does not accept estate uploads yet (HTTP 404).");
      } else if (!response.ok) {
        setUploadStatus(`Upload failed (HTTP ${response.status}).`);
      } else {
        setUploadStatus("Uploaded.");
      }
    } catch {
      setUploadStatus("Backend unreachable.");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={handleSqlite} disabled={!hasEstate} className="app-button text-xs disabled:cursor-not-allowed disabled:opacity-50">
        Download estate.db
      </button>
      <button type="button" onClick={handleJson} disabled={!hasEstate} className="app-button text-xs disabled:cursor-not-allowed disabled:opacity-50">
        Download estate.json
      </button>
      <Link href="/investigate" className="text-xs text-brand-300 hover:text-brand-50">
        Open case file viewer
      </Link>
      {UPLOAD_API_ENABLED && (
        <>
          <button type="button" onClick={handleUpload} disabled={!hasEstate} className="app-button text-xs disabled:cursor-not-allowed disabled:opacity-50">
            Send estate.db to backend
          </button>
          {uploadStatus && <span className="text-xs text-muted">{uploadStatus}</span>}
        </>
      )}
    </div>
  );
};
