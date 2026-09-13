"use client";

// Sticky bottom bar with the one clear way forward. Never advances on its own: the reader decides
// when to continue. On the final chapter the primary action becomes "Conclude report".

import React from "react";
import { ArrowLeft, ArrowRight, CheckCheck, Undo2 } from "lucide-react";

interface TourActionBarProps {
  positionLabel: string;
  canGoBack: boolean;
  nextLabel: string | null;
  isFinalChapter: boolean;
  showReturnToReviewRoute: boolean;
  onBack: () => void;
  onNext: () => void;
  onConclude: () => void;
  onReturnToReviewRoute: () => void;
}

export const TourActionBar: React.FC<TourActionBarProps> = ({
  positionLabel,
  canGoBack,
  nextLabel,
  isFinalChapter,
  showReturnToReviewRoute,
  onBack,
  onNext,
  onConclude,
  onReturnToReviewRoute,
}) => {
  return (
    <div data-print="hide" className="sticky bottom-0 z-30 border-t border-surface-border bg-surface-deep/90 backdrop-blur" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <div className="mx-auto flex max-w-[1200px] items-center gap-3 px-4 py-3 sm:px-6">
        <button type="button" onClick={onBack} disabled={!canGoBack} className="app-button flex items-center gap-2 text-sm active:translate-y-px">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Back</span>
        </button>

        <p className="hidden min-w-0 flex-1 truncate text-xs text-muted md:block">{positionLabel}</p>
        <span className="flex-1 md:hidden" />

        {showReturnToReviewRoute && !isFinalChapter && (
          <button type="button" onClick={onReturnToReviewRoute} className="app-button flex items-center gap-2 text-sm active:translate-y-px">
            <Undo2 className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">Back to review route</span>
          </button>
        )}

        {isFinalChapter ? (
          <button type="button" onClick={onConclude} className="app-primary flex min-h-12 items-center gap-2 px-5 text-sm active:translate-y-px">
            <CheckCheck className="h-4 w-4" aria-hidden="true" />
            Conclude report
          </button>
        ) : (
          <button
            key={nextLabel ?? "next"}
            type="button"
            onClick={onNext}
            className="app-primary group flex min-h-12 max-w-[70vw] items-center gap-3 px-5 text-sm active:translate-y-px"
          >
            <span className="flex min-w-0 flex-col items-start leading-tight">
              <span>Continue</span>
              {nextLabel && <span className="max-w-[46vw] truncate text-[11px] font-medium text-brand-ink/70 sm:max-w-[28ch]">{nextLabel}</span>}
            </span>
            <ArrowRight className="tour-nudge h-4 w-4 shrink-0 transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
};
