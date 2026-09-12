"use client";

import { useState, useRef, useCallback, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseAudioStreamReturn {
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;
  notice: string | null;
  playAudio: (text: string) => Promise<void>;
  stopAudio: () => void;
}

export function useAudioStream(): UseAudioStreamReturn {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const releaseAudio = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    if (audioRef.current) {
      audioRef.current.onplay = null;
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
  }, []);

  const stopAudio = useCallback(() => {
    releaseAudio();
    setIsPlaying(false);
    setIsLoading(false);
  }, [releaseAudio]);

  useEffect(() => releaseAudio, [releaseAudio]);

  const playAudio = useCallback(async (text: string) => {
    stopAudio();
    setIsLoading(true);
    setError(null);
    setNotice(null);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const response = await fetch(`${API_BASE}/api/v1/tts/synthesize`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }), signal: controller.signal,
      });
      if (abortControllerRef.current !== controller) return;
      if (!response.ok) throw new Error("Audio synthesis is unavailable. The written assessment is still available.");
      if (response.headers.get("X-Audio-Source") === "synthetic-fallback-mode") {
        setNotice("Voice synthesis is not configured. Please use the written summary.");
        stopAudio();
        return;
      }
      const blob = await response.blob();
      if (abortControllerRef.current !== controller) return;
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onplay = () => {
        if (audioRef.current !== audio) return;
        setIsLoading(false);
        setIsPlaying(true);
      };
      audio.onended = stopAudio;
      audio.onerror = () => {
        if (audioRef.current !== audio) return;
        setError("Audio could not be played. Try again or read the summary.");
        stopAudio();
      };
      await audio.play();
    } catch {
      if (controller.signal.aborted || abortControllerRef.current !== controller) return;
      setError("Audio could not be played. Try again or read the summary.");
      stopAudio();
    }
  }, [stopAudio]);

  return { isPlaying, isLoading, error, notice, playAudio, stopAudio };
}
