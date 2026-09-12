"use client";

import React from "react";
import { Volume2, Square, AlertTriangle } from "lucide-react";
import { useAudioStream } from "@/hooks/useAudioStream";

interface AudioPlayerProps {
  textToSynthesize: string;
  label?: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ textToSynthesize, label = "Listen to summary" }) => {
  const { isPlaying, isLoading, error, notice, playAudio, stopAudio } = useAudioStream();
  const tooLong = textToSynthesize.length > 5000;
  return <div className="max-w-full space-y-2">
    <button type="button" onClick={() => isPlaying || isLoading ? stopAudio() : playAudio(textToSynthesize)} disabled={!textToSynthesize || tooLong} className="app-button inline-flex items-center gap-2 text-xs">
      {isPlaying || isLoading ? <Square className="h-3.5 w-3.5" aria-hidden="true" /> : <Volume2 className="h-4 w-4 text-brand-300" aria-hidden="true" />}
      {isLoading ? "Cancel audio request" : isPlaying ? "Stop audio" : label}
    </button>
    {isLoading && <p role="status" className="text-xs text-muted">Preparing spoken summary…</p>}
    {isPlaying && <p role="status" className="text-xs text-brand-300">Playing summary</p>}
    {(notice || tooLong) && <p role="status" className="max-w-sm text-xs leading-5 text-muted">{notice || "Audio is unavailable for summaries longer than 5,000 characters."}</p>}
    {error && <p role="alert" className="flex max-w-sm items-start gap-2 text-xs leading-5 text-status-warning"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{error}</p>}
  </div>;
};
