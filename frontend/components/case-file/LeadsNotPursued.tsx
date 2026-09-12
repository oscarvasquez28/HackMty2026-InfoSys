"use client";

// Task 11: every lead that was investigated and closed without an accusation, in the body of the
// case file (not an appendix) with quick filters so a judge can find one entity in seconds.

import React, { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { CaseFileView, LeadView } from "@/lib/caseFile/derive";
import type { ValidationIssue } from "@/types/caseFile";
import { CLOSED_BY_LABELS, CLOSURE_LABELS, UNCLASSIFIED_CLOSURE_LABEL } from "@/lib/caseFile/constants";
import { EntityId } from "@/components/case-file/EntityId";
import { IssueNotice, issuesForPath } from "@/components/case-file/IssueNotice";

interface LeadsNotPursuedProps {
  view: CaseFileView;
  issues: ValidationIssue[];
}

type ClosedByFilter = "all" | "investigator" | "challenger" | "validator" | "unrecorded";
type CategoryFilter = "all" | "materiality_verified" | "administrative_error" | "no_bank_correlation" | "other" | "unclassified";

function closedByTagClass(closedBy: string | null): string {
  if (closedBy === "validator") return "bg-evidence-reconciled-soft text-evidence-reconciled";
  if (closedBy === "challenger") return "bg-evidence-held-soft text-evidence-held";
  if (closedBy === "investigator") return "bg-evidence-neutral-soft text-evidence-neutral";
  return "text-paper-muted";
}

function categoryTagClass(category: string | null): string {
  switch (category) {
    case "materiality_verified":
      return "bg-evidence-reconciled-soft text-evidence-reconciled";
    case "administrative_error":
      return "bg-evidence-probable-soft text-evidence-probable";
    case "no_bank_correlation":
      return "bg-evidence-held-soft text-evidence-held";
    case "other":
      return "bg-evidence-neutral-soft text-evidence-neutral";
    default:
      return "border border-paper-border text-paper-muted";
  }
}

export const LeadsNotPursued: React.FC<LeadsNotPursuedProps> = ({ view, issues }) => {
  const [query, setQuery] = useState("");
  const [closedByFilter, setClosedByFilter] = useState<ClosedByFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const result = new Map<number, boolean>();
    for (const lead of view.leads) {
      const textMatch =
        q === "" || lead.lead.entity.toLowerCase().includes(q) || (lead.name ?? "").toLowerCase().includes(q);
      const closedByValue: ClosedByFilter = lead.closedBy ?? (lead.lead.closed_by ? "all" : "unrecorded");
      const closedByOk = closedByFilter === "all" || closedByValue === closedByFilter;
      const categoryValue: CategoryFilter = lead.category ?? "unclassified";
      const categoryOk = categoryFilter === "all" || categoryValue === categoryFilter;
      result.set(lead.index, textMatch && closedByOk && categoryOk);
    }
    return result;
  }, [view.leads, query, closedByFilter, categoryFilter]);

  const visibleCount = Array.from(matches.values()).filter(Boolean).length;
  const hasActiveFilters = query !== "" || closedByFilter !== "all" || categoryFilter !== "all";

  return (
    <section id="leads-not-pursued" className="border-t-2 border-paper-ink pt-6">
      <h2 className="mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight text-paper-ink">
        4. Leads investigated and closed
      </h2>
      <p className="max-w-prose text-sm leading-6 text-paper-muted">
        Each entry is a lead that tripped a detector, was investigated, and was closed without an accusation.
      </p>

      {view.leads.length === 0 ? (
        <p className="mt-4 text-sm text-paper-muted">No leads were closed in this run.</p>
      ) : (
        <>
          <div data-print="hide" data-export="exclude" className="mt-4 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-md border border-paper-border bg-white px-2 py-1">
              <Search className="h-3.5 w-3.5 text-paper-muted" aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by entity or name"
                className="min-w-40 text-sm outline-none"
              />
            </div>
            <select
              value={closedByFilter}
              onChange={(e) => setClosedByFilter(e.target.value as ClosedByFilter)}
              className="rounded-md border border-paper-border bg-white px-2 py-1 text-sm"
            >
              <option value="all">All closers</option>
              <option value="investigator">Investigator</option>
              <option value="challenger">Adversarial reviewer</option>
              <option value="validator">Validator</option>
              <option value="unrecorded">Not recorded</option>
            </select>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value as CategoryFilter)}
              className="rounded-md border border-paper-border bg-white px-2 py-1 text-sm"
            >
              <option value="all">All closure types</option>
              <option value="materiality_verified">Materiality verified</option>
              <option value="administrative_error">Administrative error</option>
              <option value="no_bank_correlation">No bank correlation</option>
              <option value="other">Other</option>
              <option value="unclassified">Unclassified</option>
            </select>
            <span className="text-xs text-paper-muted">
              Showing {visibleCount} of {view.leads.length}
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setClosedByFilter("all");
                  setCategoryFilter("all");
                }}
                className="text-xs text-brand-600 underline"
              >
                Clear filters
              </button>
            )}
          </div>

          <div className="case-scroll mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] table-fixed border-collapse border border-paper-ink text-sm">
              <colgroup>
                <col style={{ width: "20%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "32%" }} />
                <col style={{ width: "16%" }} />
                <col style={{ width: "12%" }} />
              </colgroup>
              <thead className="bg-paper-ink font-mono text-[11px] uppercase tracking-[0.12em] text-paper">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Entity</th>
                  <th className="px-3 py-2 text-left font-semibold">Signal</th>
                  <th className="px-3 py-2 text-left font-semibold">Reason closed</th>
                  <th className="px-3 py-2 text-left font-semibold">Tools called</th>
                  <th className="px-3 py-2 text-left font-semibold">Closed by</th>
                </tr>
              </thead>
              <tbody>
                {view.leads.map((lead) => (
                  <LeadRow key={lead.anchorId} lead={lead} visible={matches.get(lead.index) ?? true} />
                ))}
                <tr data-print="hide" hidden={visibleCount > 0}>
                  <td colSpan={5} className="px-3 py-3 text-center text-sm text-paper-muted">
                    No leads match the current filters.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
      <IssueNotice issues={issuesForPath(issues, "leads_not_pursued")} />
    </section>
  );
};

const LeadRow: React.FC<{ lead: LeadView; visible: boolean }> = ({ lead, visible }) => {
  const tools = lead.lead.tool_calls_made ?? [];
  const closedByLabel = lead.closedBy
    ? CLOSED_BY_LABELS[lead.closedBy]
    : lead.lead.closed_by
    ? `Invalid: ${lead.lead.closed_by}`
    : "Not recorded";
  const categoryLabel = lead.category ? CLOSURE_LABELS[lead.category] : UNCLASSIFIED_CLOSURE_LABEL;

  return (
    <tr id={lead.anchorId} data-filterable-row hidden={!visible} className="scroll-mt-24 border-t border-paper-border align-top odd:bg-white even:bg-paper-raised">
      <td className="px-3 py-2">
        <EntityId entity={{ id: lead.lead.entity, prefix: lead.lead.entity.split(":")[0] ?? null, kindLabel: null, name: lead.name }} />
        <span className={`mt-1 inline-block rounded-sm px-1.5 text-[11px] font-medium ${categoryTagClass(lead.category)}`}>{categoryLabel}</span>
      </td>
      <td className="px-3 py-2 font-serif">{lead.lead.signal}</td>
      <td className="px-3 py-2 font-serif">{lead.lead.reason}</td>
      <td className="px-3 py-2">
        {tools.length > 0 ? (
          <>
            <p className="text-xs">{tools.length} call(s)</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {tools.map((tool) => (
                <span key={tool} className="rounded-sm bg-paper-raised px-1 font-mono text-[11px] text-paper-muted">
                  {tool}
                </span>
              ))}
            </div>
          </>
        ) : (
          <span className="text-[11px] text-evidence-probable">No tool calls recorded</span>
        )}
      </td>
      <td className="px-3 py-2">
        <span className={`rounded-sm px-1.5 text-xs font-medium ${closedByTagClass(lead.closedBy)}`}>{closedByLabel}</span>
      </td>
    </tr>
  );
};
