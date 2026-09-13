"use client";

import React, { useEffect, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { PolarLogo } from "@/components/PolarLogo";

const navigationItems = [
  { label: "Platform", href: "#platform" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "How it works", href: "#workflow" },
];

export const LandingNavigation: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-surface-border/70 bg-background/85 backdrop-blur-xl">
      <nav
        aria-label="Primary navigation"
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8"
      >
        <a
          href="#top"
          className="flex min-h-11 items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-4 focus-visible:ring-offset-background"
          aria-label="Polar home"
        >
          <PolarLogo className="h-7 w-auto" />
        </a>

        <div className="hidden items-center gap-8 md:flex">
          {navigationItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="flex min-h-11 items-center text-sm text-muted transition-colors duration-200 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              {item.label}
            </a>
          ))}
        </div>

        <a
          href="/investigate"
          className="hidden min-h-11 items-center gap-2 rounded-md border border-surface-border bg-surface-raised px-4 text-sm font-medium text-foreground transition-colors duration-200 hover:border-brand-500/60 hover:bg-surface md:flex focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Explore Polar
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </a>

        <button
          type="button"
          className="inline-flex h-11 w-11 cursor-pointer items-center justify-center rounded-md border border-surface-border bg-surface text-foreground transition-colors hover:border-brand-500/60 md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          aria-controls="mobile-navigation"
          aria-expanded={isOpen}
          aria-label={isOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setIsOpen((value) => !value)}
        >
          {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {isOpen && (
        <div id="mobile-navigation" className="border-t border-surface-border bg-background px-5 pb-5 pt-3 md:hidden">
          <div className="mx-auto flex max-w-7xl flex-col">
            {navigationItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                className="flex min-h-12 items-center border-b border-surface-border/70 text-base text-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                {item.label}
              </a>
            ))}
            <a
              href="/investigate"
              onClick={() => setIsOpen(false)}
              className="mt-4 flex min-h-12 items-center justify-center gap-2 rounded-md bg-brand-500 px-4 text-sm font-semibold text-brand-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              Explore Polar
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
        </div>
      )}
    </header>
  );
};
