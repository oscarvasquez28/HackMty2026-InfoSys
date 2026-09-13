"use client";

// Method and limits chapter: four panels in an alternating asymmetric grid, all open by default.

import React from "react";
import { Ban, EyeOff, Layers, RotateCcw } from "lucide-react";
import type { MethodAndLimits } from "@/types/caseFile";
import { TourChapterFrame, riseStyle } from "@/components/case-file/tour/TourChapterFrame";

interface TourMethodProps {
  method: MethodAndLimits | null;
  number: number;
  total: number;
  purpose: string;
}

const NotProvided = () => <p className="text-sm italic text-muted">Not provided by this run.</p>;

const Panel: React.FC<{ icon: typeof Layers; title: string; className: string; index: number; children: React.ReactNode }> = ({
  icon: Icon,
  title,
  className,
  index,
  children,
}) => (
  <section className={`tour-rise rounded-lg border border-surface-border bg-surface p-6 ${className}`} style={riseStyle(index)}>
    <div className="flex items-center gap-3">
      <span className="grid h-9 w-9 place-items-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-500">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <h3 className="text-base font-semibold tracking-tight">{title}</h3>
    </div>
    <div className="mt-4 text-sm leading-6 text-foreground/90">{children}</div>
  </section>
);

const List: React.FC<{ items: string[]; ordered?: boolean }> = ({ items, ordered }) => {
  if (items.length === 0) return <NotProvided />;
  if (ordered) {
    return (
      <ol className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="grid grid-cols-[1.75rem_1fr] gap-2">
            <span className="font-mono text-xs leading-6 text-brand-500">{String(i + 1).padStart(2, "0")}</span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ul className="list-disc space-y-1.5 pl-5 marker:text-muted">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
};

export const TourMethod: React.FC<TourMethodProps> = ({ method, number, total, purpose }) => (
  <TourChapterFrame number={number} total={total} eyebrow="Boundaries" title="Method and limits" purpose={purpose} layout="wide">
    <div className="grid gap-3 lg:grid-cols-5">
      <Panel icon={Layers} title="Architecture" className="lg:col-span-3" index={2}>
        {method?.architecture_summary ? <p className="max-w-[65ch]">{method.architecture_summary}</p> : <NotProvided />}
      </Panel>
      <Panel icon={Ban} title="Out of scope for this run" className="lg:col-span-2" index={3}>
        <List items={method?.out_of_scope ?? []} />
      </Panel>
      <Panel icon={EyeOff} title="What this system cannot detect" className="lg:col-span-2" index={4}>
        <List items={method?.undetectable_fraud_types ?? []} />
      </Panel>
      <Panel icon={RotateCcw} title="Reproducibility" className="lg:col-span-3" index={5}>
        <List items={method?.reproducibility_steps ?? []} ordered />
      </Panel>
    </div>
  </TourChapterFrame>
);
