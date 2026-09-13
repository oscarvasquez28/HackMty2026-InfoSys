"use client";

// Navigation state for the guided case file tour. The reader always advances by their own action --
// nothing here moves on a timer except clearing the outgoing chapter after its exit animation. The
// active chapter is tracked by identity (not index) so a findings-layout switch keeps the position.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { resolveChapterIndex, type TourChapter } from "@/lib/caseFile/tour";

export type TourDirection = "forward" | "back";

export interface TourLeaving {
  chapter: TourChapter;
  direction: TourDirection;
}

export interface UseTourNavigationReturn {
  activeIndex: number;
  activeChapter: TourChapter;
  direction: TourDirection;
  leaving: TourLeaving | null;
  visited: Set<string>;
  returnToConclusion: boolean;
  concluded: boolean;
  goTo: (index: number, options?: { fromConclusion?: boolean }) => void;
  next: () => void;
  back: () => void;
  returnToReviewRoute: () => void;
  conclude: () => void;
  reopen: () => void;
  restart: () => void;
}

const EXIT_MS = 220;

export function useTourNavigation(chapters: TourChapter[]): UseTourNavigationReturn {
  const [activeChapterState, setActiveChapter] = useState<TourChapter | null>(chapters[0] ?? null);
  const [direction, setDirection] = useState<TourDirection>("forward");
  const [leaving, setLeaving] = useState<TourLeaving | null>(null);
  const [visited, setVisited] = useState<Set<string>>(() => new Set(chapters[0] ? [chapters[0].baseKey] : []));
  const [returnToConclusion, setReturnToConclusion] = useState(false);
  const [concluded, setConcluded] = useState(false);
  const exitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeIndex = useMemo(() => resolveChapterIndex(chapters, activeChapterState), [chapters, activeChapterState]);
  const activeChapter = chapters[activeIndex];

  // A layout switch replaces the chapter objects: adopt the remapped chapter and drop any exit.
  useEffect(() => {
    if (activeChapter && activeChapterState && activeChapter.id !== activeChapterState.id) {
      setActiveChapter(activeChapter);
      setLeaving(null);
    }
  }, [activeChapter, activeChapterState]);

  useEffect(
    () => () => {
      if (exitTimerRef.current) clearTimeout(exitTimerRef.current);
    },
    []
  );

  const goTo = useCallback(
    (index: number, options?: { fromConclusion?: boolean }) => {
      const target = chapters[index];
      if (!target || index === activeIndex) return;
      const nextDirection: TourDirection = index > activeIndex ? "forward" : "back";

      if (exitTimerRef.current) clearTimeout(exitTimerRef.current);
      setLeaving({ chapter: activeChapter, direction: nextDirection });
      exitTimerRef.current = setTimeout(() => {
        setLeaving(null);
        exitTimerRef.current = null;
      }, EXIT_MS);

      setDirection(nextDirection);
      setActiveChapter(target);
      setVisited((prev) => (prev.has(target.baseKey) ? prev : new Set(prev).add(target.baseKey)));
      if (target.kind === "conclusion") setReturnToConclusion(false);
      else if (options?.fromConclusion) setReturnToConclusion(true);
    },
    [chapters, activeIndex, activeChapter]
  );

  const next = useCallback(() => goTo(activeIndex + 1), [goTo, activeIndex]);
  const back = useCallback(() => goTo(activeIndex - 1), [goTo, activeIndex]);
  const returnToReviewRoute = useCallback(() => goTo(chapters.length - 1), [goTo, chapters.length]);

  const conclude = useCallback(() => setConcluded(true), []);
  const reopen = useCallback(() => {
    setConcluded(false);
    setDirection("back");
  }, []);
  const restart = useCallback(() => {
    if (exitTimerRef.current) clearTimeout(exitTimerRef.current);
    setLeaving(null);
    setConcluded(false);
    setDirection("back");
    setReturnToConclusion(false);
    setActiveChapter(chapters[0] ?? null);
    setVisited(new Set(chapters[0] ? [chapters[0].baseKey] : []));
  }, [chapters]);

  return {
    activeIndex,
    activeChapter,
    direction,
    leaving,
    visited,
    returnToConclusion,
    concluded,
    goTo,
    next,
    back,
    returnToReviewRoute,
    conclude,
    reopen,
    restart,
  };
}
