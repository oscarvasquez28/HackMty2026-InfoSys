"use client";

import React, { useCallback, useRef, useState, ChangeEvent, DragEvent } from "react";
import { UploadCloud, FileSpreadsheet, ArrowRight, AlertCircle, X, FlaskConical } from "lucide-react";

interface FileUploadProps {
  onStartSimulation: (files: File[]) => Promise<void>;
  disabled?: boolean;
  isPreparing?: boolean;
  simulationError?: string | null;
}

const MAX_FILES = 5;
const MAX_TOTAL_BYTES = 20 * 1024 * 1024;

export const FileUpload: React.FC<FileUploadProps> = ({ onStartSimulation, disabled, isPreparing, simulationError }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = disabled || isPreparing;

  const validateAndSetFiles = useCallback((files: File[]) => {
    if (busy) return;
    const csvFiles = files.filter(file => file.name.toLowerCase().endsWith(".csv") && file.size > 0);
    if (csvFiles.length !== files.length) {
      setErrorMessage("Choose non-empty CSV files. Other file types are not supported in the demo.");
      return;
    }
    if (!csvFiles.length || csvFiles.length > MAX_FILES) {
      setErrorMessage(`Choose between 1 and ${MAX_FILES} CSV files.`);
      return;
    }
    if (csvFiles.reduce((sum, file) => sum + file.size, 0) > MAX_TOTAL_BYTES) {
      setErrorMessage("The selected files exceed the 20 MB demo limit.");
      return;
    }
    setErrorMessage(null);
    setSelectedFiles(csvFiles);
  }, [busy]);

  const handleDrag = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (!busy) setDragActive(event.type === "dragenter" || event.type === "dragover");
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    if (!busy) validateAndSetFiles(Array.from(event.dataTransfer.files));
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) validateAndSetFiles(Array.from(event.target.files));
  };

  const removeFile = (name: string) => {
    setSelectedFiles(files => files.filter(file => file.name !== name));
    if (inputRef.current) inputRef.current.value = "";
  };

  return <div className="w-full" aria-busy={isPreparing}>
    <div className="mb-4 flex items-start gap-3 rounded-lg border border-brand-500/30 bg-surface-blue p-4">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
      <div><p className="text-sm font-medium text-foreground">Visual simulation</p><p className="mt-1 text-xs leading-5 text-muted">Files provide names and sample values. Agent findings and the outcome are illustrative and remain in your browser.</p></div>
    </div>
    <div onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
      className={`rounded-xl border border-dashed p-6 transition-colors duration-200 sm:p-8 ${dragActive ? "border-brand-500 bg-surface-blue" : "border-surface-border bg-surface/60"}`}>
      <input ref={inputRef} id="investigation-csv" aria-label="Transaction CSV files" tabIndex={-1} type="file" multiple accept=".csv,text/csv" onChange={handleChange} disabled={busy} className="sr-only" aria-describedby="upload-help" />
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-surface-border bg-surface-raised text-brand-300">{selectedFiles.length ? <FileSpreadsheet className="h-5 w-5" aria-hidden="true" /> : <UploadCloud className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />}</div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">{selectedFiles.length ? `${selectedFiles.length} CSV file${selectedFiles.length === 1 ? "" : "s"} ready` : "Give the simulated team a dataset"}</p>
          <p id="upload-help" className="mt-2 text-sm leading-6 text-muted">{selectedFiles.length ? `${(selectedFiles.reduce((sum, file) => sum + file.size, 0) / 1024).toFixed(1)} KB selected` : `Drop up to ${MAX_FILES} transaction CSVs here, or choose files to begin.`}</p>
        </div>
      </div>
      {!!selectedFiles.length && <ul className="mt-5 grid gap-2 sm:grid-cols-2">{selectedFiles.map(file => <li key={file.name} className="flex min-w-0 items-center gap-2 rounded-lg border border-surface-border bg-surface-deep px-3 py-2">
        <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" /><span className="min-w-0 flex-1 truncate text-xs text-foreground" title={file.name}>{file.name}</span>
        {!busy && <button type="button" onClick={() => removeFile(file.name)} aria-label={`Remove ${file.name}`} className="flex h-11 w-11 shrink-0 items-center justify-center text-muted hover:text-foreground"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>}
      </li>)}</ul>}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="app-button text-xs">{selectedFiles.length ? "Change files" : "Choose CSV files"}</button>
        {!!selectedFiles.length && <button type="button" onClick={() => onStartSimulation(selectedFiles)} disabled={busy} className="app-primary inline-flex items-center gap-2 text-xs">{isPreparing ? "Preparing simulation…" : "Run simulation"}{!isPreparing && <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />}</button>}
        {!selectedFiles.length && <span className="text-xs text-muted">1-5 files, 20 MB total</span>}
      </div>
      {isPreparing && <div className="mt-5" role="status"><div className="review-pulse h-1 w-full rounded bg-brand-500/30" /><p className="mt-3 text-xs leading-5 text-muted">Reading sample records and preparing the visual workflow.</p></div>}
    </div>
    {(errorMessage || simulationError) && <div role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-status-danger/30 bg-status-danger/5 p-4 text-sm leading-6 text-foreground"><AlertCircle className="mt-1 h-4 w-4 shrink-0 text-status-danger" aria-hidden="true" />{errorMessage || simulationError}</div>}
    <p className="mt-4 text-xs leading-6 text-muted">Expected columns: origin, destination, amount, and optionally timestamp. Common AMLSim aliases are supported for the visual preview.</p>
  </div>;
};
