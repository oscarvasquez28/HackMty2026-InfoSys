"use client";

import { useState, useRef, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseAudioStreamReturn {
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;
  playAudio: (text: string) => Promise<void>;
  stopAudio: () => void;
}

export function useAudioStream(): UseAudioStreamReturn {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopAudio = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsPlaying(false);
    setIsLoading(false);
  }, []);

  const playAudio = useCallback(
    async (text: string) => {
      stopAudio();
      setIsLoading(true);
      setError(null);

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(`${API_BASE}/api/v1/tts/synthesize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ text }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`Error en síntesis de voz: ${response.statusText}`);
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audioRef.current = audio;

        audio.onplay = () => {
          setIsLoading(false);
          setIsPlaying(true);
        };

        audio.onended = () => {
          setIsPlaying(false);
          URL.revokeObjectURL(audioUrl);
        };

        audio.onerror = () => {
          setError("Error durante la reproducción del audio.");
          setIsPlaying(false);
          setIsLoading(false);
          URL.revokeObjectURL(audioUrl);
        };

        await audio.play();
      } catch (err: any) {
        if (err.name === "AbortError") return;
        console.error("Audio playback error:", err);
        setError(err.message || "Error al reproducir dictamen de voz.");
        setIsLoading(false);
        setIsPlaying(false);
      }
    },
    [stopAudio]
  );

  return {
    isPlaying,
    isLoading,
    error,
    playAudio,
    stopAudio,
  };
}
