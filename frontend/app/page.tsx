import React from "react";
import {
  ArrowDown,
  ArrowRight,
  AudioLines,
  Binary,
  Network,
  Radio,
  ScanSearch,
} from "lucide-react";
import { IcebergVisual } from "@/components/IcebergVisual";
import { InvestigationPreview } from "@/components/InvestigationPreview";
import { LandingNavigation } from "@/components/LandingNavigation";
import { PolarLogo } from "@/components/PolarLogo";
import { PolarMark } from "@/components/PolarMark";

const capabilities = [
  {
    icon: Network,
    index: "01",
    title: "Connected pattern detection",
    description: "Trace circular flows and rapid pass-through behavior across accounts instead of evaluating transactions in isolation.",
  },
  {
    icon: Binary,
    index: "02",
    title: "Deterministic signal reduction",
    description: "Separate relevant topology from routine activity with repeatable graph analysis that keeps the evidence path intact.",
  },
  {
    icon: Radio,
    index: "03",
    title: "Live investigation updates",
    description: "Follow each phase of the review as findings move from transaction ingestion to a structured forensic verdict.",
  },
  {
    icon: AudioLines,
    index: "04",
    title: "Accessible case summaries",
    description: "Review a concise written verdict and, when configured, listen to a protected spoken summary through the secure audio proxy.",
  },
];

const workflow = [
  {
    number: "01",
    title: "Import transactions",
    description: "Bring a structured transaction record into a focused investigation workspace.",
  },
  {
    number: "02",
    title: "Surface hidden patterns",
    description: "Polar maps connected flows and isolates the activity that warrants closer review.",
  },
  {
    number: "03",
    title: "Review the evidence",
    description: "Inspect the signal, follow the reasoning, and evaluate a structured case verdict.",
  },
];

import { redirect } from "next/navigation";

// NOTE: Landing page is temporarily deactivated to route directly into investigation.
// To reactivate, return <LandingPageContent /> from Home.
export default function Home() {
  redirect("/investigate");
}

function LandingPageContent() {
  return (
    <div id="top" className="landing-shell min-h-screen overflow-hidden bg-background text-foreground">
      <LandingNavigation />

      <main>
        <section className="relative mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-center gap-10 px-5 pb-20 pt-16 sm:px-8 lg:grid-cols-[0.9fr_1.1fr] lg:gap-8 lg:py-24">
          <div className="hero-copy relative z-10 max-w-2xl">
            <div className="mb-7 inline-flex min-h-8 items-center gap-2 rounded-full border border-brand-500/25 bg-brand-500/[0.06] px-3 font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-brand-300 sm:text-[11px]">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500 shadow-[0_0_12px_rgba(121,199,245,0.8)]" />
              Financial risk intelligence
            </div>
            <h1 className="text-balance text-5xl font-semibold leading-[0.98] tracking-[-0.06em] text-foreground sm:text-6xl lg:text-[5.15rem]">
              See beneath<br />the surface.
            </h1>
            <p className="mt-7 max-w-xl text-pretty text-base leading-7 text-muted sm:text-lg sm:leading-8">
              Polar turns complex transaction records into a focused map of connected risk—revealing the patterns that isolated reviews leave hidden.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <a
                href="/investigate"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-brand-500 px-5 text-sm font-semibold text-brand-ink transition-colors duration-200 hover:bg-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:ring-offset-4 focus-visible:ring-offset-background"
              >
                Explore the platform
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
              <a
                href="#workflow"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-surface-border bg-surface/70 px-5 text-sm font-medium text-foreground transition-colors duration-200 hover:border-brand-500/50 hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-4 focus-visible:ring-offset-background"
              >
                How it works
                <ArrowDown className="h-4 w-4 text-brand-500" aria-hidden="true" />
              </a>
            </div>
            <div className="mt-12 flex flex-wrap gap-x-6 gap-y-3 border-t border-surface-border/70 pt-5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
              <span className="flex items-center gap-2"><span className="h-1 w-1 rounded-full bg-brand-500" />Graph-based</span>
              <span className="flex items-center gap-2"><span className="h-1 w-1 rounded-full bg-brand-500" />Evidence-focused</span>
              <span className="flex items-center gap-2"><span className="h-1 w-1 rounded-full bg-brand-500" />Real-time</span>
            </div>
          </div>

          <div className="hero-visual relative flex min-h-[440px] items-center justify-center lg:min-h-[620px]">
            <div className="absolute inset-x-8 top-1/2 h-px bg-gradient-to-r from-transparent via-brand-500/20 to-transparent" />
            <IcebergVisual />
          </div>
        </section>

        <section id="platform" className="reveal-section scroll-mt-24 border-y border-surface-border/70 bg-surface-deep py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="mb-12 grid gap-6 lg:grid-cols-[0.7fr_1fr] lg:items-end">
              <div>
                <p className="section-label">The platform</p>
                <h2 className="mt-4 max-w-lg text-balance text-3xl font-semibold tracking-[-0.045em] text-foreground sm:text-5xl">
                  From transaction noise to a defensible signal.
                </h2>
              </div>
              <p className="max-w-xl text-base leading-7 text-muted lg:justify-self-end">
                Polar narrows a dense financial network into the relationships that matter, while keeping the surrounding context visible for investigation.
              </p>
            </div>
            <InvestigationPreview />
          </div>
        </section>

        <section id="capabilities" className="reveal-section scroll-mt-24 py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="max-w-2xl">
              <p className="section-label">Core capabilities</p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.045em] text-foreground sm:text-5xl">
                Precision without the black box.
              </h2>
              <p className="mt-5 text-base leading-7 text-muted">
                A focused workflow for teams that need to understand not only what was flagged, but how the signal connects.
              </p>
            </div>

            <div className="mt-14 grid border-l border-t border-surface-border sm:grid-cols-2">
              {capabilities.map((capability) => {
                const Icon = capability.icon;
                return (
                  <article key={capability.index} className="group min-h-[270px] border-b border-r border-surface-border bg-surface/35 p-6 transition-colors duration-200 hover:bg-surface/70 sm:p-8">
                    <div className="flex items-start justify-between">
                      <div className="flex h-11 w-11 items-center justify-center rounded-md border border-surface-border bg-surface-raised text-brand-300 transition-colors group-hover:border-brand-500/40">
                        <Icon className="h-5 w-5" aria-hidden="true" />
                      </div>
                      <span className="font-mono text-[10px] tracking-[0.16em] text-muted">{capability.index}</span>
                    </div>
                    <h3 className="mt-10 text-xl font-medium tracking-[-0.025em] text-foreground">{capability.title}</h3>
                    <p className="mt-3 max-w-md text-sm leading-6 text-muted">{capability.description}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section id="workflow" className="reveal-section scroll-mt-24 border-y border-surface-border/70 bg-surface/25 py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="grid gap-12 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
              <div>
                <p className="section-label">How it works</p>
                <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.045em] text-foreground sm:text-5xl">
                  One clear path through the investigation.
                </h2>
                <ScanSearch className="mt-10 h-12 w-12 text-brand-500/70" strokeWidth={1.2} aria-hidden="true" />
              </div>

              <ol className="border-t border-surface-border">
                {workflow.map((step) => (
                  <li key={step.number} className="grid gap-4 border-b border-surface-border py-7 sm:grid-cols-[54px_0.7fr_1fr] sm:items-start sm:gap-6 sm:py-9">
                    <span className="font-mono text-[11px] tracking-[0.14em] text-brand-300">{step.number}</span>
                    <h3 className="text-lg font-medium tracking-[-0.02em] text-foreground">{step.title}</h3>
                    <p className="text-sm leading-6 text-muted">{step.description}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section className="reveal-section py-24 sm:py-32">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="relative overflow-hidden rounded-xl border border-surface-border bg-surface px-6 py-16 sm:px-12 sm:py-20 lg:px-20">
              <div className="absolute -right-20 -top-36 h-80 w-80 rounded-full border border-brand-500/10" />
              <div className="absolute -right-5 -top-20 h-56 w-56 rounded-full border border-brand-500/15" />
              <PolarMark className="h-10 w-auto" />
              <h2 className="mt-8 max-w-3xl text-balance text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-5xl">
                The risk is rarely on the surface. Your investigation should go deeper.
              </h2>
              <a
                href="/investigate"
                className="mt-9 inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-brand-500 px-5 text-sm font-semibold text-brand-ink transition-colors duration-200 hover:bg-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:ring-offset-4 focus-visible:ring-offset-surface"
              >
                Explore Polar
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-surface-border/70">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <a href="#top" aria-label="Polar home" className="flex min-h-11 w-fit items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
            <PolarLogo className="h-6 w-auto" />
          </a>
          <p className="text-xs leading-5 text-muted">Financial pattern intelligence for focused investigations.</p>
          <a href="#top" className="flex min-h-11 w-fit items-center text-xs text-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">Back to top</a>
        </div>
      </footer>
    </div>
  );
}
