"use client";

// On-screen presentation of a loaded case file as a guided, chapter-by-chapter tour: progress rail,
// animated chapter stage, and an action bar the reader uses to move on at their own pace. The full
// printable document is rendered separately (hidden) by CaseFileWorkspace for Print and exports.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CaseFileView } from "@/lib/caseFile/derive";
import type { LoadedCaseFile } from "@/hooks/useCaseFileSource";
import type { ValidationIssue } from "@/types/caseFile";
import {
  FINDING_LAYOUT_STORAGE_KEY,
  buildTourChapters,
  type FindingLayout,
  type FindingPart,
  type TourChapter,
} from "@/lib/caseFile/tour";
import { useTourNavigation } from "@/hooks/useTourNavigation";
import { useCaseFileExports } from "@/hooks/useCaseFileExports";
import { prefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { TourProgressRail } from "@/components/case-file/tour/TourProgressRail";
import { TourActionBar } from "@/components/case-file/tour/TourActionBar";
import { TourOpening } from "@/components/case-file/tour/TourOpening";
import { TourSummary } from "@/components/case-file/tour/TourSummary";
import { TourFinding } from "@/components/case-file/tour/TourFinding";
import { TourLeads } from "@/components/case-file/tour/TourLeads";
import { TourMethod } from "@/components/case-file/tour/TourMethod";
import { TourConclusion } from "@/components/case-file/tour/TourConclusion";
import { TourConcluded } from "@/components/case-file/tour/TourConcluded";

interface CaseFileTourProps {
  loaded: LoadedCaseFile;
  view: CaseFileView;
  issues: ValidationIssue[];
  estateChecked: boolean;
  onReset?: () => void;
}

const FLASH_DELAY_MS = 650;

export const CaseFileTour: React.FC<CaseFileTourProps> = ({ loaded, view, issues, estateChecked, onReset }) => {
  const [layout, setLayout] = useState<FindingLayout>("single");
  const chapters = useMemo(() => buildTourChapters(view, layout), [view, layout]);
  const nav = useTourNavigation(chapters);
  const exports = useCaseFileExports(loaded, view, estateChecked);
  const rootRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const pendingFlashRef = useRef<string | null>(null);
  const firstRenderRef = useRef(true);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(FINDING_LAYOUT_STORAGE_KEY);
      if (stored === "single" || stored === "steps") setLayout(stored);
    } catch {
      // Storage unavailable (private mode, blocked site data): keep the default.
    }
  }, []);

  const changeLayout = useCallback((next: FindingLayout) => {
    setLayout(next);
    try {
      window.localStorage.setItem(FINDING_LAYOUT_STORAGE_KEY, next);
    } catch {
      // Non-essential preference.
    }
  }, []);

  const flashAnchor = useCallback((anchor: string) => {
    const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
    const row = rootRef.current?.querySelector<HTMLElement>(`#${CSS.escape(anchor)}`);
    if (!row) return;
    row.scrollIntoView({ behavior, block: "center" });
    row.classList.remove("tour-flash");
    void row.offsetWidth;
    row.classList.add("tour-flash");
    window.setTimeout(() => row.classList.remove("tour-flash"), 1900);
  }, []);

  // After each chapter change: bring the stage top into view, move focus to the new heading, and
  // finish any exhibit jump that required switching chapters.
  const stageKey = nav.concluded ? "concluded" : nav.activeChapter.id;
  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    const stage = stageRef.current;
    if (stage) {
      const top = stage.getBoundingClientRect().top + window.scrollY - 96;
      if (window.scrollY > top) window.scrollTo({ top, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      stage.querySelector<HTMLElement>('[data-chapter-active="true"] [data-chapter-heading]')?.focus({ preventScroll: true });
    }
    const pending = pendingFlashRef.current;
    if (pending) {
      pendingFlashRef.current = null;
      const timer = window.setTimeout(() => flashAnchor(pending), FLASH_DELAY_MS);
      return () => window.clearTimeout(timer);
    }
  }, [stageKey, flashAnchor]);

  const indexOfPart = useCallback(
    (findingIndex: number, part: FindingPart) => chapters.findIndex((c) => c.findingIndex === findingIndex && c.part === part),
    [chapters]
  );

  // Money-trail exhibit chips link to exhibit rows; keep those jumps inside the tour.
  const handleClickCapture = (event: React.MouseEvent<HTMLDivElement>) => {
    const link = (event.target as Element).closest?.("a[data-exhibit-ref]");
    if (!link) return;
    const anchor = link.getAttribute("href")?.slice(1);
    if (!anchor) return;
    event.preventDefault();
    const active = nav.activeChapter;
    if (active.kind === "finding" && active.part && active.part !== "evidence" && active.findingIndex !== null) {
      const target = indexOfPart(active.findingIndex, "evidence");
      if (target !== -1) {
        pendingFlashRef.current = anchor;
        nav.goTo(target);
        return;
      }
    }
    flashAnchor(anchor);
  };

  const renderChapter = (chapter: TourChapter) => {
    const index = chapters.findIndex((c) => c.id === chapter.id);
    const number = index + 1;
    const total = chapters.length;
    switch (chapter.kind) {
      case "opening":
        return <TourOpening document={view.document} isSample={loaded.source.kind === "sample"} chapters={chapters} number={number} onGoTo={nav.goTo} />;
      case "summary":
        return <TourSummary summary={view.summary} number={number} total={total} purpose={chapter.purpose} />;
      case "finding": {
        const findingIndex = chapter.findingIndex ?? 0;
        const finding = view.findings[findingIndex];
        return (
          <TourFinding
            finding={finding}
            total={view.findings.length}
            figureNumber={findingIndex + 1}
            issues={issues}
            part={chapter.part}
            number={number}
            chapterCount={total}
            purpose={chapter.purpose}
            onSelectPart={(part) => {
              const target = indexOfPart(findingIndex, part);
              if (target !== -1) nav.goTo(target);
            }}
          />
        );
      }
      case "leads":
        return <TourLeads view={view} issues={issues} number={number} total={total} purpose={chapter.purpose} />;
      case "method":
        return <TourMethod method={view.document.method_and_limits} number={number} total={total} purpose={chapter.purpose} />;
      case "conclusion":
        return (
          <TourConclusion
            view={view}
            chapters={chapters}
            visited={nav.visited}
            number={number}
            onRevisit={(i) => nav.goTo(i, { fromConclusion: true })}
            onRestart={nav.restart}
          />
        );
    }
  };

  const nextChapter = chapters[nav.activeIndex + 1] ?? null;
  const isFinalChapter = nav.activeChapter.kind === "conclusion";
  const enterMotion = `enter-${nav.direction}`;

  const stageItems: Array<{ key: string; motion: string; active: boolean; content: React.ReactNode }> = [];
  if (nav.leaving && !nav.concluded) {
    stageItems.push({ key: nav.leaving.chapter.id, motion: `exit-${nav.leaving.direction}`, active: false, content: renderChapter(nav.leaving.chapter) });
  }
  stageItems.push(
    nav.concluded
      ? {
          key: "concluded",
          motion: "enter-forward",
          active: true,
          content: <TourConcluded view={view} exports={exports} onRevisit={() => { nav.reopen(); nav.returnToReviewRoute(); }} onReset={onReset} />,
        }
      : { key: nav.activeChapter.id, motion: enterMotion, active: true, content: renderChapter(nav.activeChapter) }
  );

  return (
    <div ref={rootRef} data-print="hide" className="case-tour tour-shell flex min-h-[calc(100dvh-4rem)] flex-col" onClickCapture={handleClickCapture}>
      <TourProgressRail
        chapters={chapters}
        activeIndex={nav.activeIndex}
        visited={nav.visited}
        concluded={nav.concluded}
        layout={layout}
        hasFindings={view.findings.length > 0}
        onGoTo={(i) => {
          if (nav.concluded) nav.reopen();
          nav.goTo(i);
        }}
        onLayoutChange={changeLayout}
      />

      <p aria-live="polite" className="sr-only">
        {nav.concluded ? "Review concluded" : `Chapter ${nav.activeIndex + 1} of ${chapters.length}: ${nav.activeChapter.label}`}
      </p>

      <div ref={stageRef} className="tour-stage flex-1 overflow-x-clip">
        {stageItems.map((item) => (
          <div
            key={item.key}
            className="tour-chapter"
            data-motion={item.motion}
            data-chapter-active={item.active ? "true" : undefined}
            aria-hidden={item.active ? undefined : true}
            // React 18 does not know `inert`; set it directly so the exiting chapter is non-interactive.
            ref={(el) => {
              if (el) el.toggleAttribute("inert", !item.active);
            }}
          >
            {item.content}
          </div>
        ))}
      </div>

      {!nav.concluded && (
        <TourActionBar
          positionLabel={`Chapter ${nav.activeIndex + 1} of ${chapters.length} · ${nav.activeChapter.label}`}
          canGoBack={nav.activeIndex > 0}
          nextLabel={nextChapter?.label ?? null}
          isFinalChapter={isFinalChapter}
          showReturnToReviewRoute={nav.returnToConclusion}
          onBack={nav.back}
          onNext={nav.next}
          onConclude={nav.conclude}
          onReturnToReviewRoute={nav.returnToReviewRoute}
        />
      )}
    </div>
  );
};
