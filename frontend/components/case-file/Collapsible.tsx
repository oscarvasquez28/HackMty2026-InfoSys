"use client";

// A print/export-safe collapsible section. The body is ALWAYS rendered -- collapsed just means
// `hidden`, never unmounted -- so a filtered/collapsed section still shows up in Print, the HTML
// export, and the Markdown export, which force it open again (see globals.css and toHtml.ts).

import React from "react";
import { ChevronDown } from "lucide-react";
import { useCaseFileUi } from "@/components/case-file/CaseFileUiContext";

interface CollapsibleProps {
  id: string;
  defaultOpen: boolean;
  summary: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  summaryClassName?: string;
}

export const Collapsible: React.FC<CollapsibleProps> = ({ id, defaultOpen, summary, children, className, summaryClassName }) => {
  const { isOpen, setOpen } = useCaseFileUi();
  const open = isOpen(id, defaultOpen);

  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-body`}
        onClick={() => setOpen(id, !open)}
        className={summaryClassName ?? "flex w-full items-center justify-between gap-3 text-left"}
      >
        {summary}
        <ChevronDown
          data-print="hide"
          data-export="exclude"
          className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>
      <div id={`${id}-body`} data-collapsible-body hidden={!open}>
        {children}
      </div>
    </div>
  );
};
