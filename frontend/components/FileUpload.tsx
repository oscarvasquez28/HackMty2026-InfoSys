"use client";

import React, { useState, useRef, ChangeEvent, DragEvent } from "react";
import { UploadCloud, FileSpreadsheet, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { UploadResponse } from "@/types/investigation";

interface FileUploadProps {
  onUploadSuccess: (data: UploadResponse) => void;
  disabled?: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess, disabled }) => {
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (file: File) => {
    if (!file.name.endsWith(".csv")) {
      setErrorMessage("Solo se permiten archivos en formato CSV (IBM AMLSim).");
      setSelectedFile(null);
      return;
    }
    setErrorMessage(null);
    setSelectedFile(file);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${API_BASE}/api/v1/investigations/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Error en el servidor." }));
        throw new Error(errorData.detail || "Fallo en la carga del dataset.");
      }

      const data: UploadResponse = await response.json();
      onUploadSuccess(data);
    } catch (err: any) {
      console.error("Upload error:", err);
      setErrorMessage(err.message || "Error al comunicarse con el backend.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="w-full bg-surface border border-surface-border rounded-xl p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
            Ingesta de Dataset IBM AMLSim
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Carga el registro de transacciones para iniciar la poda determinista con Polars y NetworkX.
          </p>
        </div>
      </div>

      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !disabled && !uploading && inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors duration-200 ${
          dragActive
            ? "border-emerald-500 bg-emerald-950/20"
            : "border-gray-700 hover:border-gray-500 bg-gray-900/40"
        } ${disabled || uploading ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={handleChange}
          disabled={disabled || uploading}
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center gap-3">
          <div className="p-3 bg-gray-800 rounded-full text-emerald-400">
            <UploadCloud className="w-8 h-8" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-200">
              {selectedFile ? (
                <span className="text-emerald-400 font-semibold">{selectedFile.name}</span>
              ) : (
                "Arrastra y suelta tu dataset CSV aquí o haz clic para explorar"
              )}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {selectedFile
                ? `${(selectedFile.size / 1024).toFixed(1)} KB listos para procesar`
                : "Compatible con esquemas estándar [origin, destination, amount, timestamp]"}
            </p>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-3 p-3 bg-red-950/50 border border-red-800/60 rounded-lg flex items-center gap-2 text-xs text-red-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {selectedFile && (
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-emerald-400 flex items-center gap-1.5 font-mono">
            <CheckCircle2 className="w-4 h-4" /> Archivo seleccionado
          </span>
          <button
            type="button"
            onClick={handleUpload}
            disabled={uploading || disabled}
            className="px-5 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 rounded-lg transition-all shadow-md flex items-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Procesando con Polars...</span>
              </>
            ) : (
              <span>Ejecutar Poda y Análisis</span>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
