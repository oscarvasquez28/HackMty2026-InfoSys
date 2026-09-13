"use client";

// Shared chapter layout for the guided tour: an oversized chapter number, eyebrow, masked title and
// one-line purpose, then the chapter's content. "split" pins the identity column beside the content
// (asymmetric 5/7); "wide" stacks it above full-width content for table- and diagram-heavy chapters.

import React from "react";

interface TourChapterFrameProps {
  number: number;
  total: number;
  eyebrow: string;
  title: React.ReactNode;
  purpose: string;
  layout?: "split" | "wide";
  aside?: React.ReactNode;
  children: React.ReactNode;
}

export function riseStyle(i: number): React.CSSProperties {
  return { "--i": i } as React.CSSProperties;
}

export const TourChapterFrame: React.FC<TourChapterFrameProps> = ({ number, total, eyebrow, title, purpose, layout = "split", aside, children }) => {
  const identity = (
    <div>
      <p className="tour-mask font-mono text-[clamp(3.5rem,9vw,6.5rem)] font-semibold leading-none tracking-tight text-brand-500/20" aria-hidden="true">
        <span>{String(number).padStart(2, "0")}</span>
      </p>
      <p className="section-label tour-rise mt-4" style={riseStyle(0)}>
        {eyebrow} · Chapter {number} of {total}
      </p>
      <h2 data-chapter-heading tabIndex={-1} className="tour-mask mt-3 text-[clamp(1.75rem,3.6vw,2.75rem)] font-semibold leading-[1.1] tracking-tight text-foreground outline-none">
        <span style={{ "--mask-delay": "200ms" } as React.CSSProperties}>{title}</span>
      </h2>
      <p className="tour-rise mt-4 max-w-[46ch] text-base leading-7 text-muted" style={riseStyle(1)}>
        {purpose}
      </p>
      {aside && (
        <div className="tour-rise mt-8" style={riseStyle(2)}>
          {aside}
        </div>
      )}
    </div>
  );

  if (layout === "wide") {
    return (
      <div className="mx-auto w-full max-w-[1200px] px-4 py-10 sm:px-6 lg:py-14">
        {identity}
        <div className="mt-10">{children}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-[1200px] gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-14">
      <div className="self-start lg:sticky lg:top-32">{identity}</div>
      <div className="min-w-0">{children}</div>
    </div>
  );
};
