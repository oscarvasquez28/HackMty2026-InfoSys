"use client";

// Multi-file dropzone for the data estate: SQLite .db, per-table CSV, CFDI/estate XML, or JSON.
// Everything is processed locally in this browser tab -- see DataEstateWorkspace's reload notice.

import React, { useCallback, useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { MAX_FILES_PER_BATCH, MAX_ESTATE_FILE_BYTES } from "@/lib/estate/schema";

interface EstateUploadZoneProps {
  isProcessing: boolean;
  onFiles: (files: File[]) => void;
  onLoadSample: () => void;
  onClear: () => void;
  hasFiles: boolean;
}

export const EstateUploadZone: React.FC<EstateUploadZoneProps> = ({ isProcessing, onFiles, onLoadSample, onClear, hasFiles }) => {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const openPicker = useCallback(() => inputRef.current?.click(), []);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (fileList && fileList.length > 0) onFiles(Array.from(fileList));
    },
    [onFiles]
  );

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openPicker();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          isDragging ? "border-brand-500 bg-surface-blue" : "border-surface-border bg-surface-raised"
        }`}
      >
        <Upload className="h-5 w-5 text-brand-300" aria-hidden="true" />
        <p className="text-sm text-foreground">Drop estate files here or browse</p>
        <p className="text-xs text-muted">
          Up to {MAX_FILES_PER_BATCH} files per batch · {Math.round(MAX_ESTATE_FILE_BYTES / (1024 * 1024))} MB per file
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".db,.sqlite,.sqlite3,.csv,.json,.xml"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={onLoadSample} disabled={isProcessing} className="app-button flex items-center gap-1.5 text-xs">
          <FileText className="h-3.5 w-3.5" aria-hidden="true" />
          Load sample estate (illustrative)
        </button>
        {hasFiles && (
          <button type="button" onClick={onClear} className="app-button text-xs">
            Clear estate
          </button>
        )}
      </div>
    </div>
  );
};
