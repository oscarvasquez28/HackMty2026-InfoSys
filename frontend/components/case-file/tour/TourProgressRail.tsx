"use client";

// Sticky segmented progress rail. One group per part of the case file (a finding split into steps
// gets one slim segment per step); every segment is a button, so the reader can jump anywhere.

import React from "react";
import { groupTourChapters, type FindingLayout, type TourChapter } from "@/lib/caseFile/tour";
import { TourFindingLayoutToggle } from "@/components/case-file/tour/TourFindingLayoutToggle";

interface TourProgressRailProps {
  chapters: TourChapter[];
  activeIndex: number;
  visited: Set<string>;
  concluded: boolean;
  layout: FindingLayout;
  hasFindings: boolean;
  onGoTo: (index: number) => void;
  onLayoutChange: (layout: FindingLayout) => void;
}

export const TourProgressRail: React.FC<TourProgressRailProps> = ({
  chapters,
  activeIndex,
  visited,
  concluded,
  layout,
  hasFindings,
  onGoTo,
  onLayoutChange,
}) => {
  const groups = React.useMemo(() => groupTourChapters(chapters), [chapters]);
  const active = chapters[activeIndex];

  return (
    <div data-print="hide" className="sticky top-0 z-30 border-b border-surface-border bg-surface-deep/85 backdrop-blur">
      <div className="mx-auto max-w-[1200px] px-4 pt-3 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 truncate text-sm">
            <span className="font-mono text-xs tabular-nums text-brand-500">
              {concluded ? "Done" : `${String(activeIndex + 1).padStart(2, "0")} / ${String(chapters.length).padStart(2, "0")}`}
            </span>
            <span key={concluded ? "concluded" : active.id} className="tour-rise ml-3 inline-block font-medium text-foreground" style={{ "--i": 0 } as React.CSSProperties}>
              {concluded ? "Review concluded" : active.label}
            </span>
          </p>
          {hasFindings && <TourFindingLayoutToggle value={layout} onChange={onLayoutChange} />}
        </div>

        <nav aria-label="Case file chapters" className="mt-1 flex gap-1.5 sm:gap-2">
          {groups.map((group) => {
            const groupActive = group.indices.includes(activeIndex);
            return (
              <div key={group.baseKey} className="min-w-0" style={{ flex: `${group.indices.length === 1 ? 1 : 1.6} 1 0%` }}>
                <div className="flex gap-0.5">
                  {group.indices.map((index) => {
                    const chapter = chapters[index];
                    const isActive = index === activeIndex && !concluded;
                    const isVisited = visited.has(chapter.baseKey);
                    const isPast = concluded || index < activeIndex;
                    return (
                      <button
                        key={chapter.id}
                        type="button"
                        onClick={() => onGoTo(index)}
                        aria-current={isActive ? "step" : undefined}
                        aria-label={`Go to ${chapter.label}${isVisited ? " (visited)" : ""}`}
                        title={chapter.label}
                        className="group flex h-11 min-w-0 flex-1 items-center"
                      >
                        <span
                          className={`relative block w-full overflow-hidden rounded-full bg-surface-border transition-[height] duration-300 ${
                            isActive ? "h-2" : "h-1 group-hover:h-1.5"
                          }`}
                        >
                          <span
                            className={`absolute inset-0 origin-left rounded-full transition-transform duration-700 [transition-timing-function:cubic-bezier(0.22,1,0.36,1)] ${
                              isActive ? "bg-brand-500" : "bg-brand-500/45"
                            }`}
                            style={{ transform: `scaleX(${isActive || isPast || isVisited ? 1 : 0})` }}
                          />
                        </span>
                      </button>
                    );
                  })}
                </div>
                <p
                  className={`-mt-2 hidden truncate pb-2 text-[11px] transition-colors duration-300 lg:block ${
                    groupActive && !concluded ? "text-foreground" : "text-muted"
                  }`}
                >
                  {group.label}
                </p>
              </div>
            );
          })}
        </nav>
      </div>
    </div>
  );
};
