"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus } from "lucide-react";
import { PolarLogo } from "@/components/PolarLogo";

interface InvestigateAppBarProps {
  sourceLabel?: string;
  onReset?: () => void;
}

const TABS: Array<{ href: string; label: string }> = [
  { href: "/investigate", label: "Case file" },
  { href: "/investigate/data", label: "Data estate" },
  { href: "/investigate/history", label: "History" },
];

export const InvestigateAppBar: React.FC<InvestigateAppBarProps> = ({ sourceLabel, onReset }) => {
  const pathname = usePathname();

  return (
    <header data-print="hide" className="border-b border-surface-border bg-surface-deep">
      <div className="mx-auto flex min-h-16 max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-2 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-4 sm:gap-6">
          <Link href="/" className="flex min-h-11 shrink-0 items-center" aria-label="Polar home">
            <PolarLogo className="h-6 w-auto sm:h-7" />
          </Link>
          <span className="h-5 w-px bg-surface-border" aria-hidden="true" />
          <nav aria-label="Investigation views" className="flex items-center gap-1">
            {TABS.map((tab) => {
              const isActive = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex min-h-9 items-center rounded-md px-3 text-xs font-medium ${
                    isActive ? "bg-surface-raised text-foreground" : "text-muted hover:text-foreground"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {sourceLabel && <span className="hidden truncate text-xs text-muted lg:inline">{sourceLabel}</span>}
          {onReset && (
            <button type="button" onClick={onReset} className="app-button flex items-center gap-2 text-xs">
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Open another file</span>
              <span className="sm:hidden">New</span>
            </button>
          )}
          <Link href="/investigate/simulation" className="hidden text-xs text-muted hover:text-foreground md:inline">
            Legacy simulation (deprecated)
          </Link>
        </div>
      </div>
    </header>
  );
};
