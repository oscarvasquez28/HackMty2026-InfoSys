// Shared constants for the case file viewer: enum guards, validator thresholds copied from
// student-materials/forensic-auditor/validate_format.py, and display copy for enum values.

import {
  SCHEME_TYPES,
  SOURCE_TABLES,
  CONFIDENCE_LEVELS,
  CLOSED_BY_VALUES,
  CLOSURE_CATEGORIES,
  type SchemeType,
  type SourceTable,
  type Confidence,
  type ClosedBy,
  type ClosureCategory,
} from "@/types/caseFile";

export function isSchemeType(value: string): value is SchemeType {
  return (SCHEME_TYPES as readonly string[]).includes(value);
}

export function isSourceTable(value: string): value is SourceTable {
  return (SOURCE_TABLES as readonly string[]).includes(value);
}

export function isConfidence(value: string): value is Confidence {
  return (CONFIDENCE_LEVELS as readonly string[]).includes(value);
}

export function isClosedBy(value: string): value is ClosedBy {
  return (CLOSED_BY_VALUES as readonly string[]).includes(value);
}

export function isClosureCategory(value: string): value is ClosureCategory {
  return (CLOSURE_CATEGORIES as readonly string[]).includes(value);
}

// Primary key column per table, copied from validate_format.py::ID_COLUMN.
export const ID_COLUMN: Record<SourceTable, string> = {
  ledger: "entry_id",
  invoices: "uuid",
  bank_txns: "txn_id",
  vendors: "rfc",
  efos_list: "rfc",
  purchase_orders: "po_id",
  contracts: "contract_id",
  employees: "emp_id",
};

// Amount-bearing column per table, copied from validate_format.py::AMOUNT_COLUMN. Tables absent
// from this map cannot back a peso reconciliation on their own.
export const AMOUNT_COLUMN: Partial<Record<SourceTable, string>> = {
  invoices: "total",
  bank_txns: "amount",
  purchase_orders: "amount",
  contracts: "value",
};

export const MIN_EXHIBITS = 3;
export const MAX_NARRATIVE_WORDS = 150;
export const PESO_TOLERANCE = 0.02;
export const MAX_JSON_BYTES = 5 * 1024 * 1024;

export const SCHEME_LABELS: Record<SchemeType, string> = {
  phantom_vendor: "Phantom vendor",
  kickback: "Kickback",
  round_tripping: "Round-tripping",
  threshold_splitting: "Threshold splitting",
  revenue_inflation: "Revenue inflation",
};

export const CONFIDENCE_COPY: Record<Confidence, { label: string; description: string }> = {
  proven: {
    label: "PROVEN",
    description: "Complete documentary evidence and fully traced funds.",
  },
  probable: {
    label: "PROBABLE",
    description: "Serious documented inconsistencies; a secondary record is missing.",
  },
};

export const CLOSED_BY_LABELS: Record<ClosedBy, string> = {
  investigator: "Investigator",
  challenger: "Adversarial reviewer",
  validator: "Validator",
};

export const CLOSURE_LABELS: Record<ClosureCategory, string> = {
  materiality_verified: "False positive · materiality verified",
  administrative_error: "Administrative error · no intent",
  no_bank_correlation: "No bank correlation",
  other: "Other",
};

export const UNCLASSIFIED_CLOSURE_LABEL = "Unclassified";

export const ENTITY_PREFIXES: Record<string, string> = {
  RFC: "Vendor / company",
  EMP: "Employee",
};

// Cross-reference for common rule_broken codes. Names only, no legal content — the citation text
// always comes from the run's own rule_detail.legal_text_citation.
export const RULE_CATALOG: Record<string, { authority: string; article: string }> = {
  SAT_ART_69B: { authority: "SAT", article: "Article 69-B, Código Fiscal de la Federación" },
  NIF_A2_MATERIALIDAD: { authority: "CINIF", article: "NIF A-2, Substance over form" },
  CFF_ART_108: { authority: "SAT", article: "Article 108, Código Fiscal de la Federación" },
  CFF_ART_109_IV: { authority: "SAT", article: "Article 109, Section IV, Código Fiscal de la Federación" },
  UIF_DISP_CARACTER_GENERAL: { authority: "UIF", article: "Disposiciones de carácter general (AML)" },
  CPF_ART_388: { authority: "Código Penal Federal", article: "Article 388, Administración fraudulenta" },
};
