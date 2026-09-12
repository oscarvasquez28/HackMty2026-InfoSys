// Structural validation ported 1:1 from student-materials/forensic-auditor/validate_format.py
// (validate_structure), plus renderer-side warnings that go beyond that script's scope. This is the
// browser-side mirror judges run offline; keep messages and ordering identical to the Python source
// so the two never disagree about what counts as a format error.

import { isRecord } from "@/types/investigation";
import type { ValidationIssue } from "@/types/caseFile";
import {
  SCHEME_TYPES,
  SOURCE_TABLES,
  CONFIDENCE_LEVELS,
  CLOSED_BY_VALUES,
} from "@/types/caseFile";
import { isSchemeType, isSourceTable, isConfidence, isClosedBy, MIN_EXHIBITS, MAX_NARRATIVE_WORDS } from "@/lib/caseFile/constants";
import type { CaseFileView } from "@/lib/caseFile/derive";
import { computePerTableSubtotals, pickBestMatch } from "@/lib/caseFile/derive";

export function pyRepr(value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return `'${value.replace(/'/g, "\\'")}'`;
  if (Array.isArray(value)) return `[${value.map((item) => pyRepr(item)).join(", ")}]`;
  return String(value);
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}

function hasOwn(obj: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

function err(path: string, code: string, message: string): ValidationIssue {
  return { severity: "error", code, path, message };
}

function warn(path: string, code: string, message: string): ValidationIssue {
  return { severity: "warning", code, path, message };
}

const SORTED_SCHEME_TYPES = [...SCHEME_TYPES].sort();
const SORTED_SOURCE_TABLES = [...SOURCE_TABLES].sort();
const SORTED_CONFIDENCE = [...CONFIDENCE_LEVELS].sort();
const SORTED_CLOSED_BY = [...CLOSED_BY_VALUES].sort();

/** Structural check mirroring validate_format.py::validate_structure. Operates on the raw parsed
 * JSON (not the lenient normalized document) so messages match the Python validator exactly. */
export function validateStructure(raw: unknown): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const sub: Record<string, unknown> = isRecord(raw) ? raw : {};

  for (const key of ["seed", "findings", "leads_not_pursued", "run_metadata"]) {
    if (!hasOwn(sub, key)) {
      issues.push(err(`submission.${key}`, "E_MISSING_KEY", `submission: missing required key ${pyRepr(key)}`));
    }
  }

  const seedValue = hasOwn(sub, "seed") ? sub.seed : 0;
  if (!(typeof seedValue === "number" && Number.isInteger(seedValue))) {
    issues.push(err("submission.seed", "E_SEED_TYPE", "submission.seed must be an integer"));
  }

  let findings: unknown[] = [];
  if (hasOwn(sub, "findings")) {
    if (!Array.isArray(sub.findings)) {
      issues.push(err("submission.findings", "E_FINDINGS_TYPE", "submission.findings must be an array"));
    } else {
      findings = sub.findings;
    }
  }

  findings.forEach((fRaw, i) => {
    const f: Record<string, unknown> = isRecord(fRaw) ? fRaw : {};
    const p = `findings[${i}]`;

    for (const key of ["scheme_type", "entities", "narrative", "rule_broken", "peso_amount", "exhibits", "confidence"]) {
      if (!hasOwn(f, key)) {
        issues.push(err(`${p}.${key}`, "E_MISSING_KEY", `${p}: missing required key ${pyRepr(key)}`));
      }
    }

    const schemeType = hasOwn(f, "scheme_type") ? f.scheme_type : undefined;
    if (typeof schemeType !== "string" || !isSchemeType(schemeType)) {
      issues.push(
        err(
          `${p}.scheme_type`,
          "E_SCHEME_TYPE",
          `${p}.scheme_type must be one of ${pyRepr(SORTED_SCHEME_TYPES)}, got ${pyRepr(schemeType)}`
        )
      );
    }

    const ents = hasOwn(f, "entities") ? f.entities : [];
    if (!Array.isArray(ents) || ents.length === 0) {
      issues.push(err(`${p}.entities`, "E_ENTITIES_EMPTY", `${p}.entities must be a non-empty array`));
    } else {
      ents.forEach((e: unknown) => {
        if (!String(e).includes(":")) {
          issues.push(
            err(
              `${p}.entities`,
              "E_ENTITY_PREFIX",
              `${p}.entities: ${pyRepr(e)} is missing a type prefix (expected e.g. 'RFC:...' or 'EMP:...')`
            )
          );
        }
      });
    }

    const narrativeRaw = hasOwn(f, "narrative") ? f.narrative : "";
    const words = countWords(String(narrativeRaw));
    if (words === 0) {
      issues.push(err(`${p}.narrative`, "E_NARRATIVE_EMPTY", `${p}.narrative is empty`));
    } else if (words > MAX_NARRATIVE_WORDS) {
      issues.push(
        err(`${p}.narrative`, "E_NARRATIVE_WORDS", `${p}.narrative is ${words} words, maximum is ${MAX_NARRATIVE_WORDS}`)
      );
    }

    const ruleBrokenRaw = hasOwn(f, "rule_broken") ? f.rule_broken : "";
    if (String(ruleBrokenRaw).trim() === "") {
      issues.push(err(`${p}.rule_broken`, "E_RULE_EMPTY", `${p}.rule_broken is empty`));
    }

    const amt = hasOwn(f, "peso_amount") ? f.peso_amount : undefined;
    if (!(typeof amt === "number" && Number.isFinite(amt) && amt > 0)) {
      issues.push(
        err(`${p}.peso_amount`, "E_AMOUNT_INVALID", `${p}.peso_amount must be a positive number, got ${pyRepr(amt)}`)
      );
    }

    const confidenceRaw = hasOwn(f, "confidence") ? f.confidence : undefined;
    if (typeof confidenceRaw !== "string" || !isConfidence(confidenceRaw)) {
      issues.push(
        err(
          `${p}.confidence`,
          "E_CONFIDENCE",
          `${p}.confidence must be one of ${pyRepr(SORTED_CONFIDENCE)}, got ${pyRepr(confidenceRaw)}`
        )
      );
    }

    const exhibitsRaw = hasOwn(f, "exhibits") ? f.exhibits : [];
    const exhibitsIsArray = Array.isArray(exhibitsRaw);
    const exhibits: unknown[] = exhibitsIsArray ? (exhibitsRaw as unknown[]) : [];
    if (!exhibitsIsArray || exhibits.length < MIN_EXHIBITS) {
      issues.push(
        err(
          `${p}.exhibits`,
          "E_EXHIBITS_MIN",
          `${p}.exhibits must have at least ${MIN_EXHIBITS} entries, got ${exhibitsIsArray ? exhibits.length : "non-array"}`
        )
      );
    }

    const seenIds = new Set<unknown>();
    exhibits.forEach((exRaw, j) => {
      const ex: Record<string, unknown> = isRecord(exRaw) ? exRaw : {};
      const q = `${p}.exhibits[${j}]`;
      for (const key of ["exhibit_id", "source_table", "record_id", "note"]) {
        if (!hasOwn(ex, key)) {
          issues.push(err(q, "E_MISSING_KEY", `${q}: missing required key ${pyRepr(key)}`));
        }
      }
      const sourceTable = hasOwn(ex, "source_table") ? ex.source_table : undefined;
      if (typeof sourceTable !== "string" || !isSourceTable(sourceTable)) {
        issues.push(
          err(
            `${q}.source_table`,
            "E_SOURCE_TABLE",
            `${q}.source_table must be one of ${pyRepr(SORTED_SOURCE_TABLES)}, got ${pyRepr(sourceTable)}`
          )
        );
      }
      const eid = hasOwn(ex, "exhibit_id") ? ex.exhibit_id : undefined;
      if (seenIds.has(eid)) {
        issues.push(err(`${q}.exhibit_id`, "E_EXHIBIT_DUPLICATE", `${q}.exhibit_id ${pyRepr(eid)} is duplicated within this finding`));
      }
      seenIds.add(eid);
      const note = hasOwn(ex, "note") ? ex.note : "";
      if (String(note).trim() === "") {
        issues.push(err(`${q}.note`, "E_EXHIBIT_NOTE_EMPTY", `${q}.note is empty - state what this record proves`));
      }
    });

    const trailPresent = hasOwn(f, "money_trail");
    const trail = trailPresent ? f.money_trail : null;
    if (trail === null || trail === undefined) {
      issues.push(
        err(
          `${p}.money_trail`,
          "E_MONEY_TRAIL_ABSENT",
          `${p}.money_trail is absent - a rendered money trail is required for full Clarity credit`
        )
      );
    } else if (!Array.isArray(trail)) {
      issues.push(err(`${p}.money_trail`, "E_MONEY_TRAIL_TYPE", `${p}.money_trail must be an array`));
    } else {
      trail.forEach((stepRaw, k) => {
        const step: Record<string, unknown> = isRecord(stepRaw) ? stepRaw : {};
        const r = `${p}.money_trail[${k}]`;
        for (const key of ["from", "to", "amount", "date", "exhibit_id"]) {
          if (!hasOwn(step, key)) {
            issues.push(err(r, "E_MISSING_KEY", `${r}: missing required key ${pyRepr(key)}`));
          }
        }
        const stepExhibitId = hasOwn(step, "exhibit_id") ? step.exhibit_id : undefined;
        if (stepExhibitId && !seenIds.has(stepExhibitId)) {
          issues.push(
            err(
              `${r}.exhibit_id`,
              "E_STEP_EXHIBIT_MISMATCH",
              `${r}.exhibit_id ${pyRepr(stepExhibitId)} does not match any exhibit in this finding`
            )
          );
        }
      });
    }
  });

  let leads: unknown[] = [];
  if (hasOwn(sub, "leads_not_pursued")) {
    if (!Array.isArray(sub.leads_not_pursued)) {
      issues.push(err("submission.leads_not_pursued", "E_LEADS_TYPE", "submission.leads_not_pursued must be an array"));
    } else {
      leads = sub.leads_not_pursued;
    }
  }

  leads.forEach((lRaw, i) => {
    const l: Record<string, unknown> = isRecord(lRaw) ? lRaw : {};
    const p = `leads_not_pursued[${i}]`;
    for (const key of ["entity", "signal", "reason"]) {
      const present = hasOwn(l, key);
      const value = present ? l[key] : "";
      if (!present || String(value).trim() === "") {
        issues.push(err(`${p}.${key}`, "E_LEAD_FIELD_EMPTY", `${p}: ${pyRepr(key)} is missing or empty`));
      }
    }
    if (hasOwn(l, "closed_by")) {
      const closedBy = l.closed_by;
      if (typeof closedBy !== "string" || !isClosedBy(closedBy)) {
        issues.push(
          err(
            `${p}.closed_by`,
            "E_LEAD_CLOSED_BY",
            `${p}.closed_by must be one of ${pyRepr(SORTED_CLOSED_BY)}, got ${pyRepr(closedBy)}`
          )
        );
      }
    }
  });

  const meta: unknown = hasOwn(sub, "run_metadata") ? sub.run_metadata : {};
  if (!isRecord(meta)) {
    issues.push(err("run_metadata", "E_RUN_METADATA_TYPE", "submission.run_metadata must be an object"));
  } else {
    for (const key of ["llm_calls", "mxn_cost", "wall_clock_seconds"]) {
      if (!hasOwn(meta, key)) {
        issues.push(err(`run_metadata.${key}`, "E_RUN_METADATA_MISSING_KEY", `run_metadata: missing required key ${pyRepr(key)}`));
      } else if (!(typeof meta[key] === "number" && Number.isFinite(meta[key] as number))) {
        issues.push(
          err(
            `run_metadata.${key}`,
            "E_RUN_METADATA_FIELD_TYPE",
            `run_metadata.${key} must be a number, got ${pyRepr(meta[key])}`
          )
        );
      }
    }
  }

  return issues;
}

const STATISTICAL_RE = /\b(outlier|anomal\w*|standard deviations?|z-?score|percentile|statistic\w*|benford)\b/i;
const LEGAL_RE = /(art[ií]culo|article|art\.|nif|ley|c[oó]digo|cff|lfpiorpi|disposici)/i;
const MERMAID_TYPE_RE = /^\s*(graph|flowchart)\s+(LR|RL|TB|TD|BT)\b/;
const GENERIC_REASON_RE = /^(insufficient|not enough|no) evidence\.?$|^n\/?a$|^not suspicious\.?$/i;

/** Renderer-side warnings beyond validate_format.py's scope: missing optional sections, weak
 * citations, disconnected trails, and reconciliation quality. Operates on the derived view so it
 * can reuse the same reconciliation and trail-linking logic the UI renders. */
export function collectWarnings(view: CaseFileView): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const { document } = view;

  if (document.header === null) {
    issues.push(warn("header", "W_HEADER_MISSING", "No header was supplied: company, audit period and RFC will show as not reported."));
  }
  if (document.executive_summary === null) {
    issues.push(warn("executive_summary", "W_EXEC_SUMMARY_MISSING", "No executive summary narrative was supplied; one was generated from the findings."));
  }
  if (document.method_and_limits === null) {
    issues.push(warn("method_and_limits", "W_METHOD_MISSING", "No method and limits section was supplied."));
  }
  if (document.run_metadata.deterministic === null) {
    issues.push(warn("run_metadata.deterministic", "W_DETERMINISM_NOT_REPORTED", "run_metadata.deterministic was not reported."));
  }

  for (const findingView of view.findings) {
    const { finding, index, reconciliation, trail } = findingView;
    const p = `findings[${index}]`;

    for (const entity of finding.entities) {
      const colonIndex = entity.indexOf(":");
      if (colonIndex === -1) continue; // missing-prefix case is already an E_ENTITY_PREFIX error
      const prefix = entity.slice(0, colonIndex);
      const rest = entity.slice(colonIndex + 1);
      if (prefix !== "RFC" && prefix !== "EMP") {
        issues.push(warn(`${p}.entities`, "W_ENTITY_UNKNOWN_PREFIX", `${p}.entities: ${entity} uses an unrecognized prefix (expected RFC or EMP).`));
      }
      const found = finding.exhibits.some((ex) => ex.record_id.includes(rest) || ex.record_id.includes(entity) || ex.note.includes(rest) || ex.note.includes(entity));
      if (!found) {
        issues.push(warn(`${p}.entities`, "W_ENTITY_NO_EXHIBIT", `${p}.entities: ${entity} is not referenced by any exhibit's record_id or note.`));
      }
    }

    if (finding.rule_broken && STATISTICAL_RE.test(finding.rule_broken) && !LEGAL_RE.test(finding.rule_broken)) {
      issues.push(warn(`${p}.rule_broken`, "W_RULE_STATISTICAL", `${p}.rule_broken reads as a statistical description rather than a cited rule or article.`));
    }

    if (finding.mermaid_source && !MERMAID_TYPE_RE.test(finding.mermaid_source)) {
      issues.push(warn(`${p}.mermaid_source`, "W_MERMAID_TYPE", `${p}.mermaid_source does not start with 'graph' or 'flowchart' followed by a direction (LR/RL/TB/TD/BT).`));
    }

    if (trail) {
      trail.forEach((step, k) => {
        if (step.breaksAfter) {
          const nextStep = trail[k + 1];
          issues.push(
            warn(
              `${p}.money_trail[${k}]`,
              "W_TRAIL_DISCONNECTED",
              `${p}.money_trail: step ${k + 1} ends at ${step.step.to}, but step ${k + 2} starts at ${nextStep.step.from}.`
            )
          );
        }
      });
    }

    if (reconciliation.status === "unverifiable") {
      issues.push(warn(`${p}.reconciliation`, "W_RECONCILIATION_UNVERIFIABLE", `${p}: no exhibit cites an amount-bearing table, so peso_amount cannot be reconciled.`));
    } else if (reconciliation.status === "not_reconciled") {
      issues.push(warn(`${p}.reconciliation`, "W_RECONCILIATION_FAILED", `${p}: peso_amount does not reconcile to cited exhibits within 2%.`));
    }

    if (reconciliation.origin === "backend" && finding.peso_amount !== null) {
      const derivedPerTable = computePerTableSubtotals(finding);
      const derivedBest = pickBestMatch(finding.peso_amount, derivedPerTable);
      if (derivedBest) {
        const derivedVariance = (Math.abs(finding.peso_amount - derivedBest.subtotal) / Math.max(derivedBest.subtotal, 1)) * 100;
        const tableMismatch = reconciliation.matchedTable !== null && derivedBest.table !== reconciliation.matchedTable;
        const varianceMismatch =
          reconciliation.variancePct !== null && Math.abs(derivedVariance - reconciliation.variancePct) > 0.01;
        if (tableMismatch || varianceMismatch) {
          issues.push(
            warn(
              `${p}.reconciliation`,
              "W_RECONCILIATION_MISMATCH",
              `${p}: the run's reported reconciliation does not match the exhibit amounts computed in the browser.`
            )
          );
        }
      }
    }
  }

  for (const leadView of view.leads) {
    const { lead, index } = leadView;
    const p = `leads_not_pursued[${index}]`;
    if (lead.reason && (countWords(lead.reason) < 8 || GENERIC_REASON_RE.test(lead.reason.trim()))) {
      issues.push(warn(`${p}.reason`, "W_LEAD_GENERIC_REASON", `${p}.reason reads as generic rather than specific to this entity and its evidence.`));
    }
    if (!lead.tool_calls_made || lead.tool_calls_made.length === 0) {
      issues.push(warn(`${p}.tool_calls_made`, "W_LEAD_NO_TOOLS", `${p}.tool_calls_made is empty: no tools are recorded as having been called before closing this lead.`));
    }
    if (!lead.closed_by) {
      issues.push(warn(`${p}.closed_by`, "W_LEAD_NO_CLOSED_BY", `${p}.closed_by was not reported.`));
    }
    if (lead.closure_category !== null && leadView.category === null) {
      issues.push(warn(`${p}.closure_category`, "W_LEAD_INVALID_CATEGORY", `${p}.closure_category ${pyRepr(lead.closure_category)} is not a recognized closure category.`));
    }
  }

  return issues;
}
