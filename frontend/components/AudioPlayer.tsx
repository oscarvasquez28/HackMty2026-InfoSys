"use client";

import React from "react";
import { Volume2, Square, Loader2, VolumeX, AlertTriangle } from "lucide-react";
import { useAudioStream } from "@/hooks/useAudioStream";

interface AudioPlayerProps {
  textToSynthesize: string;
  label?: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  textToSynthesize,
  label = "Reproducir Dictamen de Voz",
}) => {
  const { isPlaying, isLoading, error, playAudio, stopAudio } = useAudioStream();

  const handleToggle = () => {
    if (isPlaying) {
      stopAudio();
    } else {
      playAudio(textToSynthesize);
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleToggle}
          disabled={isLoading || !textToSynthesize}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-xs transition-all shadow-md ${
            isPlaying
              ? "bg-amber-600 hover:bg-amber-500 text-white animate-pulse"
              : "bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white disabled:opacity-50"
          }`}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Sintetizando en ElevenLabs...</span>
            </>
          ) : isPlaying ? (
            <>
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Detener Audio</span>
            </>
          ) : (
            <>
              <Volume2 className="w-4 h-4" />
              <span>{label}</span>
            </>
          )}
        </button>

        {isPlaying && (
          <div className="flex items-center gap-1">
            <span className="w-1 h-3 bg-emerald-400 animate-bounce rounded-full"></span>
            <span className="w-1 h-5 bg-emerald-400 animate-bounce delay-100 rounded-full"></span>
            <span className="w-1 h-4 bg-emerald-400 animate-bounce delay-200 rounded-full"></span>
            <span className="w-1 h-6 bg-emerald-400 animate-bounce delay-300 rounded-full"></span>
            <span className="text-[11px] text-emerald-400 font-mono ml-1.5">Streaming Audio</span>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-1.5 text-xs text-amber-400 mt-1">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
