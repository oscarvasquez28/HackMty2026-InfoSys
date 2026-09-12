"use client";

import React, { useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, FileSearch, GitCompareArrows, Route, ScanLine, Info } from "lucide-react";
import { EvidenceRef, UploadResponse } from "@/types/investigation";
import { formatCurrencyMXN } from "@/lib/utils";

interface EvidenceInspectorProps {
  currentCase: UploadResponse | null;
  selected: EvidenceRef | null;
  onSelect: (ref: EvidenceRef) => void;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({ currentCase, selected, onSelect }) => {
  const [page, setPage] = useState(0);
  const overview = !selected || selected.kind === "overview";
  const cycle = selected?.kind === "cycle" ? currentCase?.patterns.cycles[Number(selected.id)] : undefined;
  const account = selected?.kind === "passthrough" ? currentCase?.patterns.passthrough_accounts.find(item => item.account === selected.id) : undefined;
  const links = account ? currentCase?.subgraph.edges.filter(edge => edge.source === account.account || edge.target === account.account) || [] : [];
  const refs: EvidenceRef[] = currentCase ? [
    ...currentCase.patterns.cycles.map((_, index) => ({ kind: "cycle" as const, id: String(index), label: `Circular path ${index + 1}` })),
    ...currentCase.patterns.passthrough_accounts.map(item => ({ kind: "passthrough" as const, id: item.account, label: item.account })),
  ] : [];
  const visibleRefs = refs.slice(page * 8, (page + 1) * 8);

  return (
    <aside className="min-w-0 overflow-hidden rounded-xl border border-surface-border bg-surface/60" aria-label="Evidence inspector">
      <div className="flex items-center justify-between gap-3 border-b border-surface-border px-5 py-4">
        <h2 className="flex items-center gap-2 text-sm font-medium text-foreground"><FileSearch className="h-4 w-4 text-brand-300" aria-hidden="true" /> Evidence inspector</h2>
        {currentCase && <span className="rounded border border-surface-border px-1.5 py-0.5 font-mono text-[10px] text-muted">{currentCase.simulation ? "DEMO" : "SOURCE"}</span>}
      </div>
      <div className="p-5">
        {!currentCase ? <div className="py-12">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl border border-surface-border bg-surface-raised"><ScanLine className="h-6 w-6 text-muted" strokeWidth={1.25} aria-hidden="true" /></div>
          <p className="text-center text-sm font-medium text-foreground">Every finding has a source.</p>
          <p className="mt-3 text-center text-xs leading-6 text-muted">Select a finding during the review to inspect the accounts and transfers behind it.</p>
        </div> : <>
          {!overview && <button type="button" onClick={() => onSelect({ kind: "overview", id: "risk", label: "Evidence overview" })} className="mb-4 flex min-h-11 items-center gap-2 text-xs text-muted hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> All evidence</button>}
          {overview && <>
            <h3 className="text-base font-medium text-foreground">Patterns in this dataset</h3>
            <p className="mt-2 text-xs leading-5 text-muted">{currentCase.simulation ? "Illustrative demo patterns built from sample identifiers and values. They are not detected fraud." : "Computed rule matches. Open a finding to inspect the underlying records."}</p>
            <div className="my-5 grid grid-cols-2 gap-4 border-y border-surface-border py-4">
              <div><p className="text-2xl font-medium tracking-tight text-foreground">{currentCase.patterns.cycles.length}</p><p className="mt-1 text-xs text-muted">Circular paths</p></div>
              <div><p className="text-2xl font-medium tracking-tight text-foreground">{currentCase.patterns.passthrough_accounts.length}</p><p className="mt-1 text-xs text-muted">Pass-through accounts</p></div>
            </div>
            {!refs.length && <p className="rounded-lg border border-status-success/25 bg-status-success/5 p-4 text-sm leading-6 text-foreground">No patterns matched these checks. Review the final assessment for scope and limitations.</p>}
            <div className="space-y-2">
              {visibleRefs.map(ref => <button key={`${ref.kind}:${ref.id}`} type="button" onClick={() => onSelect(ref)} className="flex min-h-12 w-full items-center gap-3 rounded-lg border border-surface-border px-3 py-3 text-left text-xs transition-colors hover:border-brand-500/50 hover:bg-surface-blue">
                {ref.kind === "cycle" ? <GitCompareArrows className="h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" /> : <Route className="h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />}
                <span className="min-w-0 flex-1 break-all text-foreground">{ref.label}<span className="mt-1 block text-[11px] text-muted">{ref.kind === "cycle" ? "Closed account path" : "Matched flow and timing"}</span></span>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
              </button>)}
            </div>
            {refs.length > 8 && <div className="mt-3 flex items-center justify-between text-xs text-muted">
              <button type="button" disabled={page === 0} onClick={() => setPage(value => value - 1)} className="min-h-11 px-2 disabled:opacity-40">Previous</button>
              <span>{page * 8 + 1}-{Math.min((page + 1) * 8, refs.length)} of {refs.length}</span>
              <button type="button" disabled={(page + 1) * 8 >= refs.length} onClick={() => setPage(value => value + 1)} className="min-h-11 px-2 disabled:opacity-40">Next</button>
            </div>}
            <button type="button" onClick={() => onSelect({ kind: "dataset", id: "normalized", label: "Normalized records" })} className="mt-5 flex min-h-11 w-full items-center justify-between text-xs text-brand-300 hover:text-brand-50">View dataset evidence <ArrowUpRightIcon /></button>
          </>}
          {selected?.kind === "dataset" && <>
            <h3 className="text-base font-medium text-foreground">Dataset evidence</h3>
            <p className="mt-2 text-xs leading-5 text-muted">{currentCase.preview ? `First ${currentCase.preview.length} accepted records. These are normalized records, not original CSV line numbers.` : "The API returns flagged account-to-account links, not original CSV rows. Each link may aggregate several transactions."}</p>
            {currentCase.preview?.length ? <div className="mt-5 overflow-x-auto rounded-lg border border-surface-border" tabIndex={0} aria-label="Scrollable normalized transaction preview">
              <table className="w-full text-left text-xs">
                <caption className="sr-only">Normalized transaction preview, amounts in MXN and time in dataset units</caption>
                <thead className="bg-surface-raised text-muted"><tr>{["From", "To", "MXN", "Time"].map(label => <th key={label} scope="col" className="whitespace-nowrap px-3 py-3 font-medium">{label}</th>)}</tr></thead>
                <tbody>{currentCase.preview.map((row, index) => <tr key={index} className="border-t border-surface-border/60 text-foreground">
                  <td className="max-w-36 break-all px-3 py-3 font-mono">{row.origin}</td><td className="max-w-36 break-all px-3 py-3 font-mono">{row.destination}</td><td className="whitespace-nowrap px-3 py-3 font-mono">{formatCurrencyMXN(row.amount)}</td><td className="px-3 py-3 font-mono">{row.timestamp ?? "Unknown"}</td>
                </tr>)}</tbody>
              </table>
            </div> : <div className="mt-5 max-h-96 space-y-3 overflow-y-auto">{currentCase.subgraph.edges.slice(0, 20).map(edge => <div key={`${edge.source}:${edge.target}`} className="rounded-lg border border-surface-border bg-surface-deep p-3 text-xs"><p className="break-all font-mono text-foreground">{edge.source} <span className="text-muted">to</span> {edge.target}</p><p className="mt-2 text-brand-300">{formatCurrencyMXN(edge.amount)}</p><p className="mt-1 text-muted">{edge.count} aggregated transfer{edge.count === 1 ? "" : "s"}</p></div>)}<p className="text-xs leading-5 text-muted">{currentCase.subgraph.edges.length ? `Showing ${Math.min(20, currentCase.subgraph.edges.length)} of ${currentCase.subgraph.edges.length} flagged links.` : "No flagged links were returned. A raw record preview is not provided by this API."}</p></div>}
            <p className="mt-4 text-xs leading-5 text-muted">{currentCase.ingestion?.timestamps_synthetic ? "Time values were synthesized, not supplied by the source." : "Time values are treated as AMLSim hours. Verify the source units."}</p>
          </>}
          {cycle && <>
            <p className="text-xs text-brand-300">Circular flow</p><h3 className="mt-2 text-base font-medium text-foreground">{selected?.label}</h3>
            <p className="mt-2 text-xs leading-5 text-muted">Funds follow a closed path through {cycle.length} accounts. This relationship is a review signal, not proof of intent.</p>
            <ol className="my-5 rounded-lg border border-surface-border bg-surface-deep p-4">{cycle.path.map((id, index) => <li key={`${id}:${index}`}>
              {index > 0 && <ArrowDown className="my-2 h-3.5 w-3.5 text-brand-500/60" aria-hidden="true" />}
              <span className={`block break-all font-mono text-xs ${index === 0 || index === cycle.path.length - 1 ? "text-brand-300" : "text-foreground"}`}>{id}</span>
            </li>)}</ol>
            <dl className="text-xs"><dt className="text-muted">Aggregated path volume</dt><dd className="mt-2 text-lg text-foreground">{formatCurrencyMXN(cycle.estimated_volume)}</dd></dl>
          </>}
          {account && <>
            <p className="text-xs text-brand-300">Rapid pass-through</p><h3 className="mt-2 break-all font-mono text-sm text-foreground">{account.account}</h3>
            <dl className="my-5 grid grid-cols-2 gap-x-3 gap-y-5 text-xs">
              <div><dt className="text-muted">Incoming</dt><dd className="mt-1 break-words text-foreground">{formatCurrencyMXN(account.total_in)}</dd></div>
              <div><dt className="text-muted">Outgoing</dt><dd className="mt-1 break-words text-foreground">{formatCurrencyMXN(account.total_out)}</dd></div>
              <div><dt className="text-muted">Flow match</dt><dd className="mt-1 text-xl text-foreground">{(account.ratio * 100).toFixed(1)}%</dd></div>
              <div><dt className="text-muted">Time window</dt><dd className="mt-1 text-xl text-foreground">{account.time_delta_hours}h</dd></div>
            </dl>
            <p className="text-xs leading-5 text-muted">Flow match is the smaller of total inflows and outflows divided by the larger, not a fraud probability.</p>
            <h4 className="mb-3 mt-6 text-xs font-medium text-foreground">Connected transfers</h4>
            <div className="max-h-72 space-y-3 overflow-y-auto">{links.slice(0, 20).map(edge => <div key={`${edge.source}:${edge.target}`} className="rounded-lg border border-surface-border p-3 text-xs">
              <p className="break-all font-mono text-foreground">{edge.source} <span className="text-muted">to</span> {edge.target}</p>
              <p className="mt-2 text-brand-300">{formatCurrencyMXN(edge.amount)}</p><p className="mt-1 text-muted">{edge.count} aggregated transfer{edge.count !== 1 ? "s" : ""}</p>
            </div>)}</div>
            {links.length > 20 && <p className="mt-3 text-xs text-muted">Showing the first 20 of {links.length} connected links.</p>}
          </>}
          {!overview && selected?.kind !== "dataset" && !cycle && !account && <p className="text-sm text-muted">This finding is not available in the uploaded evidence. Select another item.</p>}
          {(cycle || account) && <div className="mt-6 flex items-start gap-2 border-t border-surface-border pt-4 text-xs leading-5 text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" /><p>Source: computed dataset results. Repeated movement can count the same funds more than once.</p></div>}
        </>}
      </div>
    </aside>
  );
};

const ArrowUpRightIcon: React.FC = () => <ArrowRight className="h-3.5 w-3.5 -rotate-45" aria-hidden="true" />;
