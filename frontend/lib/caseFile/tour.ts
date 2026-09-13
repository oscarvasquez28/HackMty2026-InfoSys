// Chapter model for the guided case file tour (components/case-file/tour/*). Pure: same view and
// layout -> same chapters. `baseKey` is layout-independent (a finding shown on one screen and the
// same finding split into parts share it), so position and "visited" survive a layout switch.

import type { CaseFileView } from "@/lib/caseFile/derive";

export type FindingLayout = "single" | "steps";
export type FindingPart = "accusation" | "trail" | "evidence" | "review";
export type TourChapterKind = "opening" | "summary" | "finding" | "leads" | "method" | "conclusion";

export interface TourChapter {
  id: string;
  kind: TourChapterKind;
  baseKey: string;
  label: string;
  groupLabel: string;
  purpose: string;
  findingIndex: number | null;
  part: FindingPart | null;
}

export const FINDING_PARTS: Array<{ part: FindingPart; label: string; purpose: string }> = [
  { part: "accusation", label: "The accusation", purpose: "Who is accused, the rule they broke, and how much is at stake." },
  { part: "trail", label: "What happened", purpose: "The story in plain words, and the money moving step by step." },
  { part: "evidence", label: "Evidence", purpose: "The records cited as proof, and whether the amounts add up." },
  { part: "review", label: "Adversarial review", purpose: "The strongest defense argument, and why the finding held." },
];

export const FINDING_LAYOUT_STORAGE_KEY = "polar.caseTour.findingLayout";

export function buildTourChapters(view: CaseFileView, layout: FindingLayout): TourChapter[] {
  const chapters: TourChapter[] = [
    {
      id: "opening",
      kind: "opening",
      baseKey: "opening",
      label: "Case opening",
      groupLabel: "Opening",
      purpose: "Who was audited, over which period, and how the run behaved.",
      findingIndex: null,
      part: null,
    },
    {
      id: "summary",
      kind: "summary",
      baseKey: "summary",
      label: "Executive summary",
      groupLabel: "Summary",
      purpose: "The result in one read: what was found and how certain it is.",
      findingIndex: null,
      part: null,
    },
  ];

  const total = view.findings.length;
  view.findings.forEach((finding, i) => {
    const baseKey = `finding-${i}`;
    const groupLabel = `Finding ${finding.number}`;
    if (layout === "single") {
      chapters.push({
        id: baseKey,
        kind: "finding",
        baseKey,
        label: `Finding ${finding.number} of ${total}`,
        groupLabel,
        purpose: "The accusation, the money trail, the evidence, and the review that tried to break it.",
        findingIndex: i,
        part: null,
      });
      return;
    }
    for (const { part, label, purpose } of FINDING_PARTS) {
      chapters.push({
        id: `${baseKey}-${part}`,
        kind: "finding",
        baseKey,
        label: `Finding ${finding.number} · ${label}`,
        groupLabel,
        purpose,
        findingIndex: i,
        part,
      });
    }
  });

  chapters.push(
    {
      id: "leads",
      kind: "leads",
      baseKey: "leads",
      label: "Leads investigated and closed",
      groupLabel: "Closed leads",
      purpose: "Signals that were investigated and deliberately closed without an accusation.",
      findingIndex: null,
      part: null,
    },
    {
      id: "method",
      kind: "method",
      baseKey: "method",
      label: "Method and limits",
      groupLabel: "Method",
      purpose: "What this system claims, and what it cannot see.",
      findingIndex: null,
      part: null,
    },
    {
      id: "conclusion",
      kind: "conclusion",
      baseKey: "conclusion",
      label: "Review route",
      groupLabel: "Conclusion",
      purpose: "Revisit any part of the case file, or conclude the report.",
      findingIndex: null,
      part: null,
    }
  );

  return chapters;
}

/** Index of `target` in `chapters`, falling back to the same part, then the same baseKey, then 0. */
export function resolveChapterIndex(chapters: TourChapter[], target: TourChapter | null): number {
  if (!target) return 0;
  const exact = chapters.findIndex((c) => c.id === target.id);
  if (exact !== -1) return exact;
  const samePart = chapters.findIndex((c) => c.baseKey === target.baseKey && c.part === (target.part ?? "accusation"));
  if (samePart !== -1) return samePart;
  const sameBase = chapters.findIndex((c) => c.baseKey === target.baseKey);
  return sameBase === -1 ? 0 : sameBase;
}

export interface TourChapterGroup {
  baseKey: string;
  label: string;
  startIndex: number;
  indices: number[];
}

export function groupTourChapters(chapters: TourChapter[]): TourChapterGroup[] {
  const groups: TourChapterGroup[] = [];
  chapters.forEach((chapter, index) => {
    const last = groups[groups.length - 1];
    if (last && last.baseKey === chapter.baseKey) {
      last.indices.push(index);
    } else {
      groups.push({ baseKey: chapter.baseKey, label: chapter.groupLabel, startIndex: index, indices: [index] });
    }
  });
  return groups;
}
