// Browser-side mirror of validate_format.py::validate_against_estate: confirms every cited exhibit
// record exists in the loaded estate, and that peso_amount reconciles to the best-matching
// amount-bearing table -- the same check judges run offline with `--estate`.

import type { CaseFileDocument, ValidationIssue } from "@/types/caseFile";
import { isSourceTable, ID_COLUMN, AMOUNT_COLUMN, PESO_TOLERANCE } from "@/lib/caseFile/constants";
import { pyRepr } from "@/lib/caseFile/validate";
import type { EstateRow, EstateTables } from "@/types/estate";
import type { SourceTable } from "@/types/caseFile";

export function findEstateRecord(tables: EstateTables, table: SourceTable, recordId: string): EstateRow | null {
  const pkColumn = ID_COLUMN[table];
  return tables[table].find((row) => String(row[pkColumn] ?? "") === String(recordId)) ?? null;
}

/** Mirrors validate_against_estate's per-finding reconciliation, including its exact error text. */
export function validateAgainstEstate(document: CaseFileDocument, tables: EstateTables): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  document.findings.forEach((finding, i) => {
    const perTable: Record<string, number> = {};
    const order: string[] = [];

    finding.exhibits.forEach((exhibit, j) => {
      const table = exhibit.source_table;
      if (!isSourceTable(table)) return; // already an E_SOURCE_TABLE structural error
      const record = findEstateRecord(tables, table, exhibit.record_id);
      if (!record) {
        issues.push({
          severity: "error",
          code: "E_ESTATE_RECORD_MISSING",
          path: `findings[${i}].exhibits[${j}]`,
          message: `findings[${i}].exhibits[${j}]: ${table}.${exhibit.record_id} does not exist in the loaded estate`,
        });
        return;
      }
      const amountColumn = AMOUNT_COLUMN[table];
      if (amountColumn) {
        const amount = Number(record[amountColumn] ?? 0);
        if (!(table in perTable)) {
          order.push(table);
          perTable[table] = 0;
        }
        perTable[table] += amount;
      }
    });

    const claimed = finding.peso_amount ?? 0;
    if (order.length === 0) {
      issues.push({
        severity: "error",
        code: "E_ESTATE_NO_AMOUNT",
        path: `findings[${i}]`,
        message: `findings[${i}]: no exhibit cites an amount-bearing table (${pyRepr([...Object.keys(AMOUNT_COLUMN)].sort())}), so peso_amount cannot reconcile`,
      });
      return;
    }

    let bestTable = order[0];
    let bestDelta = Math.abs(claimed - perTable[bestTable]);
    for (const table of order.slice(1)) {
      const delta = Math.abs(claimed - perTable[table]);
      if (delta < bestDelta) {
        bestTable = table;
        bestDelta = delta;
      }
    }
    if (bestDelta > PESO_TOLERANCE * Math.max(perTable[bestTable], 1)) {
      const detail = [...order]
        .sort()
        .map((t) => `${t}=${perTable[t].toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
        .join(", ");
      issues.push({
        severity: "error",
        code: "E_ESTATE_RECONCILE",
        path: `findings[${i}]`,
        message: `findings[${i}]: peso_amount ${claimed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} does not reconcile to cited exhibits [${detail}]`,
      });
    }
  });

  return issues;
}
