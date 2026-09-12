# Plan de ejecución — Expediente Pericial + Data Estate (`/investigate`)

> Plan pensado para que lo ejecute un modelo (Sonnet 5) sin ambigüedad. Prosa en español; **código,
> identificadores, comentarios y textos de UI en inglés** (decisión del usuario). Todo lo marcado con
> "EXACTO" se copia tal cual.

---

## 0. Contexto

`/investigate` hoy monta una simulación multi‑agente (`InvestigationDashboard` + `useAgentSimulation`)
que no corresponde a lo que exige el reto. El artefacto que evalúan los jueces es el **case file**
definido en `student-materials/forensic-auditor/` (`case_file_structure.md`, `submission_schema.json`,
`validate_format.py`, `estate_schema.sql`). El backend/seeder/flujo de IA todavía no produce esos
datos, así que el frontend debe quedar **listo para recibirlos**:

1. **Visor de expediente** (`/investigate`): renderiza las 13 tareas, valida con las mismas reglas que
   `validate_format.py` y exporta a Print/PDF, HTML autocontenido, Markdown y JSON — sin red.
2. **Data Estate** (`/investigate/data`): carga el estado de datos de la empresa en **SQLite (.db),
   CSV, XML (CFDI 4.0 / estate XML) y JSON**, lo valida contra `estate_schema.sql`, lo previsualiza,
   lo exporta a `estate.db`/`estate.json`, y permite que el visor verifique cada exhibit contra el estate
   (equivalente en navegador de `validate_format.py --estate`).

La simulación vieja queda en `/investigate/simulation`, marcada como deprecada.

---

## 1. Protocolo de ejecución y checkpoints (OBLIGATORIO)

> ⛔ **REGLA DE ORO — LEER ANTES DE ESCRIBIR CÓDIGO**
>
> Trabaja **una fase a la vez**. Al terminar cada fase **DETENTE** y ejecuta su bloque
> "⛔ CHECKPOINT". **Prohibido** empezar la siguiente fase si el checkpoint no pasó completo.
> El objetivo es que, si la sesión se corta (límite de contexto, de uso o de tiempo), el repo quede
> **compilando** y el siguiente agente sepa **exactamente** dónde retomar.
>
> En cada checkpoint, sin excepción:
> 1. **Relee** la sección de la fase y compárala ítem por ítem con lo implementado (archivos, nombres,
>    firmas, textos EXACTOS). Corrige cualquier diferencia antes de seguir.
> 2. **Typecheck**: `cd frontend && npx --no-install tsc --noEmit --incremental false` → 0 errores.
> 3. **Alcance**: `git status` / `git diff --stat` → solo archivos listados en esa fase; **nada** bajo `backend/` ni `student-materials/`.
> 4. **Criterios de salida** de la fase: ejecútalos y anota el resultado real (no supongas).
> 5. **Registro**: actualiza `doc/frontend/case-file-progress.md` (plantilla en Apéndice H): marca la fase `[x]`,
>    archivos tocados, comandos + resultado, desviaciones del plan y por qué, pendientes.
> 6. **Si algo falla**: arréglalo antes de avanzar. Si tras **2 intentos** no se resuelve, **detente** y
>    reporta al usuario el error exacto y lo que intentaste. No "sigas y luego vemos".
> 7. **Presupuesto**: si estimas que no te alcanza el contexto/uso para terminar la **siguiente** fase completa,
>    **no la empieces**: deja el registro al día con una sección "Handoff" (siguiente paso exacto) y termina
>    con un resumen para el usuario.

**Al iniciar cualquier sesión (incluida una reanudación):**
1. Si no existe, copiar este plan tal cual a `doc/frontend/case-file-plan.md` y crear `doc/frontend/case-file-progress.md` desde el Apéndice H.
2. Leer `doc/frontend/case-file-progress.md` y `git status`. Retomar en la **primera fase no marcada**; si una fase quedó a medias, primero verificar lo que existe contra el plan y luego completarla.
3. No rehacer fases marcadas `[x]` salvo que su checkpoint falle hoy.

**Sesiones sugeridas** (cada una cabe con margen): A = Fases 0–2 · B = Fases 3–4 · C = Fase 5 · D = Fase 6 · E = Fases 7–8.

---

## 2. Decisiones cerradas (no reabrir)

| # | Decisión | Detalle |
|---|---|---|
| D1 | **Contrato oficial** manda | Nombres y enums de `submission_schema.json`. Donde las tareas usan otros nombres aplica el mapeo §4.1. Lo que el oficial no tiene va como **claves extra opcionales** (el validador ignora claves desconocidas). |
| D2 | `scheme_type` | Solo `phantom_vendor`, `kickback`, `round_tripping`, `threshold_splitting`, `revenue_inflation`. Los valores de la tarea (`EFOS_INVOICE_MILL`, etc.) **no se usan**. |
| D3 | Idioma | UI en inglés (AGENTS.md §7). Datos (narrativas, nombres legales) se muestran como vienen. |
| D4 | Simulación | Se conserva intacta en `/investigate/simulation`, marcada `@deprecated`. No se borra nada. |
| D5 | Diagramas | `mermaid` **`11.17.2` exacto**. mermaid 12 exige Node ≥ 22.12; el repo usa Node 20 (local y `node:20-alpine`). |
| D6 | Estética | Chrome de la app en tema oscuro Polar; el **documento** es una hoja "papel" clara institucional (pantalla = impresión = export). |
| D7 | Solo frontend | No tocar `backend/`. Endpoints de backend se documentan como *propuestos* y quedan detrás de flags. |
| D8 | Determinismo | Mismo JSON ⇒ mismo Markdown/HTML: sin `Date.now()`, sin `Math.random()`, fechas mostradas como string (nunca `new Date()`), claves ordenadas al iterar para mostrar. |
| D9 | Data estate en navegador | `sql.js` **`1.14.2`** (SQLite WASM, servido desde `public/`, sin CDN), `papaparse` **`5.7.0`**, tipos `@types/sql.js` **`1.4.11`** y `@types/papaparse` **`5.5.2`** (dev). XML con `DOMParser` nativo. Todo exacto (`--save-exact`). |
| D10 | Estado compartido | Un provider en `app/investigate/layout.tsx` guarda case file + estate en memoria de la pestaña; sobrevive a navegar entre `/investigate` y `/investigate/data`, **no** a recargar (la UI lo dice). |

---

## 3. Reglas duras para el ejecutor

1. No modificar `backend/`, `student-materials/`, ni la landing (`app/page.tsx` y sus componentes).
2. Dependencias permitidas: solo las de D5 y D9. Nada de CDNs, Google Fonts, `react-markdown`, workers de terceros.
3. Convenciones AGENTS.md §4: `"use client"` en componentes/hooks, imports `@/*`, named exports,
   `React.FC<XProps>` con `interface XProps`, iconos `lucide-react`, moneda vía `formatCurrencyMXN`.
4. Iconos: la versión instalada (0.363) usa `TriangleAlert`, `CircleCheck`, `CircleX`, `CircleHelp`
   (no `AlertTriangle`/`CheckCircle2`/`XCircle`/`HelpCircle`). Verificados además: `Gavel, Lock, Stamp, Scale,
   ShieldCheck, ShieldAlert, Swords, FileJson, FileCode2, FileText, Printer, Download, Upload, ChevronDown,
   Fingerprint, Coins, Cpu, Clock, Search, Filter, Info, ListChecks, BookOpen, ArrowRight, Link2, BadgeCheck`.
   Cualquier otro icono: confirmar en `node_modules/lucide-react/dist/lucide-react.d.ts` antes de usarlo.
5. Lock de `.next/trace` en `npm run build`: **detenerse y pedir ayuda** (no borrar `.next`, no matar procesos).
6. No hacer commits salvo que el usuario lo pida.
7. **No ejecutar `npm run lint`**: no hay config ESLint y `next lint` abre un prompt interactivo.

---

## 4. Contrato de datos

### 4.1 Mapeo tarea → contrato (EXACTO)

| Tarea | Campo pedido | Campo real que consume la UI | Origen |
|---|---|---|---|
| T1 | `company` | `header.company` | ext. |
| T1 | `audit_period{start,end}` | `header.audit_period{start,end}` (+ opcional `header.company_rfc`) | ext. |
| T1 | `seed` | `seed` | oficial |
| T1 | `cost_figures.llm_calls/mxn_cost/wall_clock_s` | `run_metadata.llm_calls/mxn_cost/wall_clock_seconds` (+ `cost_by_role`) | oficial |
| T1 | `determinism_flag` | `run_metadata.deterministic` | oficial |
| T2 | `plain_narrative` | `executive_summary.plain_narrative` | ext. |
| T2 | `summary_table.*` | **derivado** en el front (`derive.ts`) | calculado |
| T3 | `entity` | `entities[]` (el primero es el principal) + `entity_names{id: name}` top‑level | oficial + ext. |
| T3 | `scheme_type` | `scheme_type` (enum oficial) | oficial |
| T4 | `rule_broken{code,authority,legal_text_citation}` | `rule_broken` (string) + `rule_detail{code,authority,article,legal_text_citation}` | oficial + ext. |
| T5 | `amount_pesos` / `confidence` | `peso_amount` / `confidence` | oficial |
| T6 | `what_happened` | `narrative` (≤ 150 palabras) | oficial |
| T7 | `money_trail[].step_order/from_account/to_account/amount_pesos/timestamp/exhibit_id` | `money_trail[].from/to/amount/date/exhibit_id`; `step_order` = índice+1 | oficial |
| T7 | `mermaid_source` | `mermaid_source` opcional; si falta se **genera** desde `money_trail` | ext. |
| T8 | `exhibits[]` | igual, `source_table` con las 8 tablas oficiales (`ledger, invoices, bank_txns, vendors, efos_list, purchase_orders, contracts, employees`) + opcional `amount` | oficial + ext. |
| T9 | `reconciliation{...}` | `reconciliation{claimed_pesos, exhibits_sum, variance_percentage, matched_table?, per_table_breakdown[]}` opcional; si falta se **deriva** | ext. |
| T10 | `adversarial_review{...}` | igual | ext. |
| T11 | `specific_documentary_reason` / `tool_calls_made:int` / `closed_by:string` | `reason` / `tool_calls_made:string[]` (conteo = `.length`) / `closed_by` enum `investigator/challenger/validator` | oficial |
| T11 | etiquetas de descarte | `closure_category` enum `materiality_verified/administrative_error/no_bank_correlation/other` | ext. |
| T12 | `method_and_limits{...}` | igual (top‑level) | ext. |

`variance_percentage` está en **puntos porcentuales** (0.86 = 0.86 %).

### 4.2 Dos capas de datos

- **Raw** (`unknown`): el JSON tal cual. `validateStructure(raw)` corre aquí (paridad con Python) y es lo que exporta el botón JSON.
- **Normalizado** (`CaseFileDocument`): versión *leniente* para renderizar sin crashear. Enums como `string` (se validan después), números inválidos → `null`, strings faltantes → `""`, arrays faltantes → `[]`, **excepto** `money_trail`: `null` si está ausente.

### 4.3 `frontend/types/caseFile.ts` (EXACTO)

```ts
export const SCHEME_TYPES = ["phantom_vendor", "kickback", "round_tripping", "threshold_splitting", "revenue_inflation"] as const;
export type SchemeType = (typeof SCHEME_TYPES)[number];
export const SOURCE_TABLES = ["ledger", "invoices", "bank_txns", "vendors", "efos_list", "purchase_orders", "contracts", "employees"] as const;
export type SourceTable = (typeof SOURCE_TABLES)[number];
export const CONFIDENCE_LEVELS = ["proven", "probable"] as const;
export type Confidence = (typeof CONFIDENCE_LEVELS)[number];
export const CLOSED_BY_VALUES = ["investigator", "challenger", "validator"] as const;
export type ClosedBy = (typeof CLOSED_BY_VALUES)[number];
export const CLOSURE_CATEGORIES = ["materiality_verified", "administrative_error", "no_bank_correlation", "other"] as const;
export type ClosureCategory = (typeof CLOSURE_CATEGORIES)[number];

export interface MoneyTrailStep { from: string; to: string; amount: number | null; date: string; exhibit_id: string; }
export interface Exhibit { exhibit_id: string; source_table: string; record_id: string; note: string; amount: number | null; }
export interface RuleDetail { code: string; authority: string; article: string; legal_text_citation: string; }
export interface ReconciliationTableSubtotal { table: string; subtotal: number; }
export interface Reconciliation {
  claimed_pesos: number; exhibits_sum: number; variance_percentage: number;
  matched_table: string | null; per_table_breakdown: ReconciliationTableSubtotal[];
}
export interface AdversarialReview { challenger_argument: string; why_finding_held: string; reviewer_agent_role: string; }

export interface CaseFinding {
  finding_id: string | null;
  scheme_type: string;
  entities: string[];
  narrative: string;
  rule_broken: string;
  rule_detail: RuleDetail | null;
  peso_amount: number | null;
  confidence: string;
  money_trail: MoneyTrailStep[] | null;
  mermaid_source: string | null;
  exhibits: Exhibit[];
  reconciliation: Reconciliation | null;
  adversarial_review: AdversarialReview | null;
}
export interface LeadNotPursued {
  entity: string; signal: string; reason: string;
  tool_calls_made: string[] | null; closed_by: string | null; closure_category: string | null;
}
export interface RunMetadata {
  llm_calls: number | null; mxn_cost: number | null; wall_clock_seconds: number | null;
  cost_by_role: Record<string, number>;   // only finite numeric values kept
  deterministic: boolean | null;           // null = not reported
}
export interface CaseHeader { company: string; company_rfc: string | null; audit_period: { start: string; end: string } | null; }
export interface MethodAndLimits {
  architecture_summary: string; out_of_scope: string[]; undetectable_fraud_types: string[]; reproducibility_steps: string[];
}
export interface CaseFileDocument {
  seed: number | null;
  header: CaseHeader | null;
  executive_summary: { plain_narrative: string } | null;
  entity_names: Record<string, string>;
  findings: CaseFinding[];
  leads_not_pursued: LeadNotPursued[];
  run_metadata: RunMetadata;
  method_and_limits: MethodAndLimits | null;
}

export type IssueSeverity = "error" | "warning";
export interface ValidationIssue { severity: IssueSeverity; code: string; path: string; message: string; }
```

### 4.4 `frontend/types/estate.ts` (EXACTO, se crea en Fase 1 aunque se use en Fase 6)

```ts
import type { SourceTable } from "@/types/caseFile";

export type EstateColumnType = "TEXT" | "REAL" | "INTEGER";
export interface EstateColumnSpec { name: string; type: EstateColumnType; primaryKey: boolean; }
export type EstateValue = string | number | null;
export type EstateRow = Record<string, EstateValue>;
export type EstateTables = Record<SourceTable, EstateRow[]>;
export type EstateFileFormat = "sqlite" | "csv" | "json" | "xml";
export type EstateFileStatus = "imported" | "needs_table" | "failed" | "case_file";
export interface EstateIssue {
  severity: "error" | "warning"; code: string; message: string;
  fileName: string | null; table: SourceTable | null; rowIndex: number | null; column: string | null;
}
export interface EstateFileEntry {
  id: string; fileName: string; format: EstateFileFormat; sizeBytes: number; status: EstateFileStatus;
  detectedAs: string;
  contributions: Partial<Record<SourceTable, EstateRow[]>>;
  pendingCsv: { header: string[]; rows: string[][] } | null;
  caseFileRaw: unknown | null;
  fileIssues: EstateIssue[];
}
```

Reusar `isRecord` de `@/types/investigation` (`frontend/types/investigation.ts:157`).

---

## 5. Árbol de archivos

```text
frontend/
├── app/investigate/layout.tsx                 NUEVO (F3) → <InvestigateSessionProvider>
├── app/investigate/page.tsx                   MODIFICAR (F3) → <CaseFileWorkspace />
├── app/investigate/simulation/page.tsx        NUEVO (F3) → simulación deprecada + banner
├── app/investigate/data/page.tsx              NUEVO (F6) → <DataEstateWorkspace />
├── app/globals.css                            MODIFICAR (F5) → Apéndice D
├── tailwind.config.js                         MODIFICAR (F1) → Apéndice E
├── next.config.js                             MODIFICAR (F6) → fallback fs/path/crypto para sql.js
├── package.json                               MODIFICAR (F0/F6) → deps exactas + scripts predev/prebuild
├── .env.example                               MODIFICAR (F3/F6) → flags de API
├── public/sql-wasm.wasm                       GENERADO (F6) por script, ignorado en git
├── public/samples/estate/*                    NUEVO (F6) → Apéndice F/G
├── lib/utils.ts                               MODIFICAR (F1) → formatPesos, formatSeconds, formatInteger
├── lib/caseFile/{constants,normalize,validate,derive,mermaid,toMarkdown,toHtml,download}.ts   NUEVO (F1)
├── lib/estate/{schema,coerce,parseCsv,parseJson,parseXml,sqlite,ingest,validateEstate,estateCheck}.ts  NUEVO (F6)
├── types/caseFile.ts, types/estate.ts         NUEVO (F1)
├── hooks/useCaseFileSource.ts                 NUEVO (F3)
├── hooks/useEstate.ts                         NUEVO (F6)
├── fixtures/case-file.sample.json             NUEVO (F2) Apéndice A
├── fixtures/case-file.no-findings.json        NUEVO (F2) Apéndice B.1
├── fixtures/case-file.edge-cases.json         NUEVO (F2) Apéndice B.2
├── components/investigate/
│   ├── InvestigateSessionProvider.tsx         F3 (case file) / F6 (estate)
│   └── InvestigateAppBar.tsx                  F3 (tab Case file) / F6 (tab Data estate)
├── components/case-file/                      F3–F5
│   CaseFileWorkspace, CaseFileUiContext, CaseFileSourcePanel, ExportToolbar, ValidationPanel, IssueNotice,
│   Collapsible, CaseFileDocument, CaseHeader, ExecutiveSummary, ConfidenceBadge, FindingSection, EntityId,
│   SchemeTypeBadge, RuleBrokenCallout, AmountConfidence, FindingNarrative, MoneyTrail, MermaidDiagram,
│   MoneyTrailTimeline, ExhibitsTable, ReconciliationBlock, AdversarialReview, LeadsNotPursued, MethodAndLimits
└── components/estate/                         F6
    DataEstateWorkspace, EstateUploadZone, EstateFileList, EstateTableSummary, EstateTablePreview,
    EstateIssuesPanel, EstateExportBar
doc/frontend/case-file-plan.md                 NUEVO (F0) copia de este plan
doc/frontend/case-file-progress.md             NUEVO (F0) registro de avance (Apéndice H)
```
No borrar: componentes/hooks de la simulación, `useInvestigationStream`, `useAudioStream`, `FileUpload`.

---

## 6. Fases

### Fase 0 — Preflight

1. `git status`; confirmar rama `dev-emiliano`. No revertir cambios ajenos (hay cambios sin commit en `doc/` y `.gitignore` que no son tuyos).
2. Copiar plan a `doc/frontend/case-file-plan.md` y crear `doc/frontend/case-file-progress.md` (Apéndice H).
3. `node -v` = 20.x.
4. `cd frontend && npm install mermaid@11.17.2 --save-exact`.
5. Confirmar que `.gitignore` tiene `/lib/` anclado (línea 14) → `frontend/lib/` sí se versiona.

> ⛔ **CHECKPOINT FASE 0** — Criterios de salida: `package.json` tiene `"mermaid": "11.17.2"` (sin `^`); `npx --no-install tsc --noEmit --incremental false` sigue en 0 errores; existen `case-file-plan.md` y `case-file-progress.md`. Registrar en el progreso y **detenerse** antes de la Fase 1.

### Fase 1 — Tokens, formato y lógica pura (sin UI)

**1.1 `tailwind.config.js`** — aplicar Apéndice E.

**1.2 `lib/utils.ts`** — agregar (no tocar lo existente):
```ts
export function formatPesos(amount: number): string { return `${formatCurrencyMXN(amount)} MXN`; }      // 1450000 → "$1,450,000.00 MXN"
export function formatSeconds(seconds: number): string { return `${seconds.toFixed(1)}s`; }             // 14.2 → "14.2s"
export function formatInteger(value: number): string { return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value); }
```
(Verificado: `formatCurrencyMXN` → `"$1,450,000.00"`, `"-$150.00"`, `"$18.45"`.)

**1.3 Tipos**: crear `types/caseFile.ts` (§4.3) y `types/estate.ts` (§4.4).

**1.4 `lib/caseFile/constants.ts`**
- Helpers `isSchemeType(v: string): v is SchemeType` (idem `isSourceTable`, `isConfidence`, `isClosedBy`, `isClosureCategory`).
- `ID_COLUMN` y `AMOUNT_COLUMN` copiados de `validate_format.py` (`ledger: "entry_id", invoices: "uuid", bank_txns: "txn_id", vendors: "rfc", efos_list: "rfc", purchase_orders: "po_id", contracts: "contract_id", employees: "emp_id"`; montos: `invoices: "total", bank_txns: "amount", purchase_orders: "amount", contracts: "value"`).
- `MIN_EXHIBITS = 3`, `MAX_NARRATIVE_WORDS = 150`, `PESO_TOLERANCE = 0.02`, `MAX_JSON_BYTES = 5 * 1024 * 1024`.
- `SCHEME_LABELS`: `phantom_vendor → "Phantom vendor"`, `kickback → "Kickback"`, `round_tripping → "Round-tripping"`, `threshold_splitting → "Threshold splitting"`, `revenue_inflation → "Revenue inflation"`.
- `CONFIDENCE_COPY`: `proven → { label: "PROVEN", description: "Complete documentary evidence and fully traced funds." }`, `probable → { label: "PROBABLE", description: "Serious documented inconsistencies; a secondary record is missing." }`.
- `CLOSED_BY_LABELS`: `investigator → "Investigator"`, `challenger → "Adversarial reviewer"`, `validator → "Validator"`.
- `CLOSURE_LABELS`: `materiality_verified → "False positive · materiality verified"`, `administrative_error → "Administrative error · no intent"`, `no_bank_correlation → "No bank correlation"`, `other → "Other"`; sin valor/inválido → `"Unclassified"`.
- `ENTITY_PREFIXES`: `RFC → "Vendor / company"`, `EMP → "Employee"`.
- `RULE_CATALOG: Record<string, { authority: string; article: string }>` (solo nombres): `SAT_ART_69B → { "SAT", "Article 69-B, Código Fiscal de la Federación" }`, `NIF_A2_MATERIALIDAD → { "CINIF", "NIF A-2, Substance over form" }`, `CFF_ART_108 → { "SAT", "Article 108, Código Fiscal de la Federación" }`, `CFF_ART_109_IV → { "SAT", "Article 109, Section IV, Código Fiscal de la Federación" }`, `UIF_DISP_CARACTER_GENERAL → { "UIF", "Disposiciones de carácter general (AML)" }`, `CPF_ART_388 → { "Código Penal Federal", "Article 388, Administración fraudulenta" }`.

**1.5 `lib/caseFile/normalize.ts`**
```ts
export type NormalizeResult = { ok: true; document: CaseFileDocument } | { ok: false; error: string };
export function normalizeCaseFile(raw: unknown): NormalizeResult;
```
- Falla dura solo si: no es objeto → `"Expected a JSON object at the top level."`; o no tiene **ninguna** de `seed`, `findings`, `leads_not_pursued`, `run_metadata` → `"This JSON does not look like a Forensic Auditor submission (expected seed, findings, leads_not_pursued, run_metadata)."`
- Todo lo demás leniente (§4.2). `seed`: entero o `null`. `cost_by_role`: solo numéricos finitos. Objetos de extensión: `null` si no son objeto; strings internos faltantes → `""`.

**1.6 `lib/caseFile/validate.ts`**
```ts
export function validateStructure(raw: unknown): ValidationIssue[];    // "error", paridad 1:1 con validate_structure()
export function collectWarnings(view: CaseFileView): ValidationIssue[]; // "warning"
export function countWords(text: string): number; // text.trim() === "" ? 0 : text.trim().split(/\s+/).length  (== Python str.split())
export function pyRepr(value: unknown): string;
```
- `validateStructure`: portar **en el mismo orden** cada chequeo de `validate_structure` (`validate_format.py` líneas 45–156) con el mismo `path` y mensaje. `pyRepr`: string → `'texto'` (escapar `'`), `null/undefined` → `None`, boolean → `True/False`, número → `String(n)`, arrays → `['a', 'b']`. Listas de enums **ordenadas** como `sorted()` (p. ej. `['kickback', 'phantom_vendor', 'revenue_inflation', 'round_tripping', 'threshold_splitting']`). `code`: `E_` + nombre corto (`E_SCHEME_TYPE`, `E_NARRATIVE_WORDS`, …).
- `collectWarnings` (códigos EXACTOS):
  - `W_HEADER_MISSING`, `W_EXEC_SUMMARY_MISSING`, `W_METHOD_MISSING`, `W_DETERMINISM_NOT_REPORTED`.
  - `W_ENTITY_UNKNOWN_PREFIX`: tiene `:` pero prefijo ≠ `RFC`/`EMP`.
  - `W_ENTITY_NO_EXHIBIT`: ni el id ni su parte tras `:` aparece en algún `record_id` o `note` de los exhibits del hallazgo.
  - `W_RULE_STATISTICAL`: `rule_broken` matchea `/\b(outlier|anomal\w*|standard deviations?|z-?score|percentile|statistic\w*|benford)\b/i` **y no** `/(art[ií]culo|article|art\.|nif|ley|c[oó]digo|cff|lfpiorpi|disposici)/i`.
  - `W_MERMAID_TYPE`: `mermaid_source` que no empieza con `/^\s*(graph|flowchart)\s+(LR|RL|TB|TD|BT)\b/`.
  - `W_TRAIL_DISCONNECTED` (uno por quiebre `steps[k].to !== steps[k+1].from`).
  - `W_RECONCILIATION_FAILED`, `W_RECONCILIATION_UNVERIFIABLE`, `W_RECONCILIATION_MISMATCH` (backend vs derivado difieren > 0.01 pp o en tabla).
  - `W_LEAD_GENERIC_REASON`: `countWords(reason) < 8` o match `/^(insufficient|not enough|no) evidence\.?$|^n\/?a$|^not suspicious\.?$/i`.
  - `W_LEAD_NO_TOOLS`, `W_LEAD_NO_CLOSED_BY`, `W_LEAD_INVALID_CATEGORY`.

**1.7 `lib/caseFile/derive.ts`**
```ts
export interface EntityRef { id: string; prefix: string | null; kindLabel: string | null; name: string | null; }
export interface TrailStepView { stepOrder: number; step: MoneyTrailStep; fromName: string | null; toName: string | null;
  exhibitAnchor: string | null; exhibitResolved: boolean; breaksAfter: boolean; }
export type ReconciliationOrigin = "estate" | "backend" | "derived" | "none";   // "estate" solo se produce desde Fase 6
export interface ReconciliationView { status: "reconciled" | "not_reconciled" | "unverifiable"; origin: ReconciliationOrigin;
  claimed: number | null; matchedTable: string | null; matchedSubtotal: number | null; delta: number | null;
  variancePct: number | null; perTable: ReconciliationTableSubtotal[]; }
export interface RuleView { title: string; code: string | null; authority: string | null; citation: string | null; citedAs: string; }
export interface FindingView { index: number; number: number; anchorId: string; workpaperId: string; finding: CaseFinding;
  schemeType: SchemeType | null; confidence: Confidence | null; entities: EntityRef[]; narrativeWords: number;
  rule: RuleView; trail: TrailStepView[] | null; mermaidPrimary: string | null; mermaidGenerated: string | null;
  exhibitAnchors: Record<string, string>; duplicateExhibitIds: string[]; reconciliation: ReconciliationView; }
export interface SummaryView { findingsCount: number; proven: number; probable: number; invalid: number;
  globalConfidence: Confidence | null; totalExposure: number; closedLeadsCount: number;
  narrative: string; narrativeOrigin: "run" | "derived"; }
export interface LeadView { index: number; anchorId: string; lead: LeadNotPursued; name: string | null;
  closedBy: ClosedBy | null; category: ClosureCategory | null; toolCount: number; }
export interface CaseFileView { document: CaseFileDocument; summary: SummaryView; findings: FindingView[]; leads: LeadView[]; }
export function buildCaseFileView(document: CaseFileDocument): CaseFileView;   // Fase 6 agrega 2º parámetro opcional `estate`
export function exhibitAnchor(findingAnchor: string, exhibitId: string): string;
// `${findingAnchor}-exhibit-${exhibitId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`
```
Reglas:
- `anchorId = "finding-" + number`; `workpaperId = finding_id ?? "F-" + String(number).padStart(2, "0")`. Lead `anchorId = "lead-" + slug(entity)` (`slug` = lowercase y `[^a-z0-9]+` → `-`); repetidos → sufijo `-2`, `-3`…
- `globalConfidence`: `null` si 0 hallazgos; `"proven"` si todos `proven`; si no, `"probable"`.
- `totalExposure` = suma de `peso_amount` no nulos. `closedLeadsCount = leads_not_pursued.length`.
- Narrativa derivada (si falta o está vacía), EXACTO:
  - 0 hallazgos: `` `No accusation was made in this run. ${L} lead(s) were investigated and closed with documentary reasons.` ``
  - ≥1: `` `${N} finding(s) with a total exposure of ${formatPesos(total)}: ${P} proven and ${Q} probable. ${L} lead(s) were investigated and closed without an accusation.` ``
- `RuleView`: `authority = rule_detail?.authority || RULE_CATALOG[code]?.authority || null`; `article = rule_detail?.article || RULE_CATALOG[code]?.article || rule_broken`; `title = authority ? `${authority} — ${article}` : article`; `citation = rule_detail?.legal_text_citation || null`; `citedAs = rule_broken`.
- **Reconciliación** (paridad con `validate_against_estate`):
  1. `perTable`: recorrer exhibits en orden; si `source_table ∈ AMOUNT_COLUMN` y `amount !== null`, acumular (orden = primera aparición).
  2. Si existe `finding.reconciliation` → `origin "backend"`, usar sus números; `status = variance_percentage <= 2 ? "reconciled" : "not_reconciled"`; `delta = claimed_pesos − exhibits_sum`.
  3. Si no, con `perTable` no vacío y `peso_amount !== null` → `origin "derived"`: `best` = mínimo `|claimed − subtotal|` (empate → primera en aparecer); `delta = claimed − subtotal`; `variancePct = |delta| / max(subtotal, 1) * 100`; `status = |delta| <= 0.02 * max(subtotal, 1) ? "reconciled" : "not_reconciled"`.
  4. Si no → `unverifiable`, `origin "none"`.
- Trail: `exhibitResolved` = el `exhibit_id` existe en el hallazgo; `breaksAfter` = `steps[k].to !== steps[k+1].from`.
- `mermaidPrimary = mermaid_source?.trim() || null`; `mermaidGenerated = trail?.length ? buildMermaidFromTrail(...) : null`.

**1.8 `lib/caseFile/mermaid.ts`**
```ts
export function loadMermaid(): Promise<typeof import("mermaid").default>;   // singleton con import("mermaid") dinámico
export function renderMermaidSvg(renderId: string, source: string): Promise<string>; // serializado en cola
export function buildMermaidFromTrail(steps: MoneyTrailStep[], entityNames: Record<string, string>, findingEntities: string[]): string;
```
- `initialize` EXACTO:
```ts
{ startOnLoad: false, securityLevel: "strict", theme: "base", deterministicIds: true, deterministicIDSeed: "polar-case-file",
  flowchart: { htmlLabels: false, curve: "basis", useMaxWidth: true },
  themeVariables: { fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif", fontSize: "13px",
    primaryColor: "#FFFFFF", primaryTextColor: "#161B22", primaryBorderColor: "#161B22", lineColor: "#3A4250",
    secondaryColor: "#F2EFE8", tertiaryColor: "#FBFAF7", edgeLabelBackground: "#FBFAF7" } }
```
- Cola: `let queue: Promise<unknown> = Promise.resolve();` cada render encadena `await mermaid.parse(source)` y `mermaid.render(renderId, source)`; en `finally` eliminar `document.getElementById("d" + renderId)`; `queue = task.catch(() => undefined)`. (mermaid no es concurrente; StrictMode duplica efectos.)
- `buildMermaidFromTrail` EXACTO:
  1. `lines = ["flowchart LR"]`.
  2. Nodos por primera aparición (por step: `from`, luego `to`): ids `N1`, `N2`…; label = `name ? `${name} · ${account}` : account` → `  N1["<esc(label)>"]`.
  3. Por step `i`: `  Na -->|"<esc(`Step ${i+1} · ${amount === null ? "amount n/a" : formatPesos(amount)} · ${date} · ${exhibit_id}`)>"| Nb`.
  4. Marcados = cuentas iguales a algún `findingEntities[j]` o a su parte tras `:`. Si hay: `  classDef flagged fill:#F6E1DF,stroke:#8E1B1F,stroke-width:2px,color:#161B22` y `  class N1,N3 flagged`.
  5. `esc`: `"`→`#quot;`, `<`→`#lt;`, `>`→`#gt;`, `|`→`/`, saltos → espacio.
  6. `lines.join("\n")`.
  - Si en navegador mermaid rechaza `-->|"..."|`, cambiar **solo** el paso 3 a `  Na -- "<label>" --> Nb` y anotarlo como desviación.

**1.9 `lib/caseFile/toMarkdown.ts`** — `buildCaseFileMarkdown(view: CaseFileView, options: { isSample: boolean; renderedSources: Record<string, string | null>; estateChecked: boolean }): string`. Plantilla EXACTA en Apéndice C. Fuente del diagrama: `renderedSources[anchorId] ?? mermaidPrimary ?? mermaidGenerated`. Escapar celdas (`|`→`\|`, saltos → espacio). `\n` y un `\n` final.

**1.10 `lib/caseFile/download.ts`** — `downloadTextFile(filename: string, content: string | Uint8Array, mime: string): void` (Blob → `URL.createObjectURL` → `<a download>` click → `setTimeout(() => URL.revokeObjectURL(url), 1000)`).

**1.11 `lib/caseFile/toHtml.ts`** — `buildStandaloneHtml(params: { documentElement: HTMLElement; title: string; raw: unknown }): string`:
1. `clone = documentElement.cloneNode(true) as HTMLElement`.
2. Quitar del clon `[data-export="exclude"]` y `[data-print="hide"]`.
3. `removeAttribute("hidden")` en `[data-collapsible-body]` y `[data-filterable-row]`.
4. CSS: `Array.from(document.styleSheets)` → `cssRules` → `cssText` (cada hoja en `try/catch`).
5. `json = JSON.stringify(raw, null, 2).replace(/</g, "\\u003c")`.
6. Devolver:
```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escapeHtml(title)}</title>
<style>{css}
body.case-export{margin:0;padding:32px 16px;background:#E9E6DF !important;color:#161B22}
@media print{body.case-export{background:#fff !important;padding:0}}</style></head>
<body class="case-export">{clone.outerHTML}
<script type="application/json" id="case-file-data">{json}</script></body></html>
```

> ⛔ **CHECKPOINT FASE 1** — Criterios de salida: `tsc` 0 errores; ningún componente/página creado todavía; grep confirma que `lib/caseFile/*` no usa `Date.now`, `Math.random` ni `new Date(`; `countWords("a  b\nc")` sería 3 por construcción (revisar el código). Registrar y **detenerse**.

### Fase 2 — Fixtures de expediente

1. Crear `fixtures/case-file.sample.json` (Apéndice A, tal cual), `case-file.no-findings.json` (B.1) y `case-file.edge-cases.json` (B.2).
2. Desde la raíz del repo (`-X utf8` obligatorio en Windows: `Path.read_text()` usa cp1252 y rompe con acentos):
   - `python -X utf8 student-materials/forensic-auditor/validate_format.py --submission frontend/fixtures/case-file.sample.json` → `PASS`.
   - Idem `case-file.no-findings.json` → `PASS`.
   - Idem `case-file.edge-cases.json` → exit ≠ 0 con **exactamente** los 10 errores de B.2. Si no coinciden, corregir el fixture (nunca el validador).

> ⛔ **CHECKPOINT FASE 2** — Criterios de salida: los 3 comandos dan exactamente lo esperado (pegar la línea resumen de cada uno en el progreso). `tsc` 0 errores. **Detenerse.**

### Fase 3 — Rutas, sesión compartida, shell y carga

**3.1 Simulación deprecada**
- `app/investigate/simulation/page.tsx`: `metadata.title = "Legacy simulation (deprecated) | Polar"`; banner EXACTO + `<InvestigationDashboard />`:
  `<div className="border-b border-status-warning/40 bg-surface-deep px-4 py-2 text-center text-xs text-status-warning">Deprecated: this multi-agent simulation predates the case file contract and is kept for reference only. <Link href="/investigate" className="underline">Open the case file viewer</Link></div>`
- JSDoc `/** @deprecated Legacy frontend-only simulation. Superseded by CaseFileWorkspace at /investigate. */` encima del símbolo exportado en `components/InvestigationDashboard.tsx` y `hooks/useAgentSimulation.ts`. Ningún otro cambio.
- `app/investigate/page.tsx`: `metadata = { title: "Case File | Polar", description: "Forensic case file viewer: findings, money trails, exhibits, reconciliation and declined leads." }` → `<CaseFileWorkspace />`.

**3.2 `hooks/useCaseFileSource.ts`**
```ts
export type CaseFileSourceKind = "sample" | "file" | "estate-page" | "api";
export type FixtureId = "sample" | "no-findings" | "edge-cases";
export interface CaseFileSource { kind: CaseFileSourceKind; label: string; }
export interface LoadedCaseFile { raw: unknown; document: CaseFileDocument; structureIssues: ValidationIssue[]; source: CaseFileSource; loadId: number; }
export interface UseCaseFileSourceReturn {
  status: "idle" | "loading" | "ready" | "error"; loaded: LoadedCaseFile | null; error: string | null;
  loadFixture: (id: FixtureId) => void; loadFile: (file: File) => Promise<void>;
  loadRaw: (raw: unknown, source: CaseFileSource) => void;
  loadFromApi: (caseId: string) => Promise<void>; reset: () => void;
}
```
- Fixtures vía `import sample from "@/fixtures/case-file.sample.json"` (etc.). Labels: `"Sample case (illustrative)"`, `"Sample: no findings (illustrative)"`, `"Sample: edge cases (invalid on purpose)"`; `kind "sample"`.
- `loadFile`: extensión `.db/.sqlite/.sqlite3/.csv/.xml` → `"This is data estate input. Open it from the Data estate page."`; otra que no sea `.json` → `"Select a .json file produced by the auditor (submission.json)."`; `size > MAX_JSON_BYTES` → `"File exceeds 5 MB."`; `JSON.parse` falla → `` `Invalid JSON: ${message}` ``; luego `normalizeCaseFile` + `validateStructure`. Label `` `Local file: ${file.name}` ``.
- `loadRaw`: mismo pipeline sin lectura de archivo.
- `loadFromApi`: solo visible si `process.env.NEXT_PUBLIC_CASE_FILE_API === "enabled"`. `GET ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/investigations/${encodeURIComponent(caseId)}/case-file`, `AbortController` en `useRef`, timeout 15 s, abort en teardown. 404 → `"The backend does not expose a case file for this case yet (HTTP 404)."`; otro → `` `Backend request failed (HTTP ${status}).` ``; red → `"Backend unreachable. Load a local JSON file instead."`. Label `` `Backend case ${caseId}` ``.
- `loadId` incrementa en cada carga.
- `.env.example`: `NEXT_PUBLIC_CASE_FILE_API=disabled` con comentario `# "enabled" shows the backend case-file loader (endpoint proposed, not implemented yet)`.

**3.3 Sesión compartida**
- `components/investigate/InvestigateSessionProvider.tsx` (`"use client"`): llama `useCaseFileSource()` y expone `{ caseFile }` vía contexto; `export function useInvestigateSession()` (lanza error si se usa fuera del provider). En Fase 6 se agrega `estate`.
- `app/investigate/layout.tsx` (server component): `export default function InvestigateLayout({ children }) { return <InvestigateSessionProvider>{children}</InvestigateSessionProvider>; }`.
- `components/investigate/InvestigateAppBar.tsx` (`data-print="hide"`, estilos como el header de `InvestigationDashboard`): `PolarMark` + `polar` (Link `/`), separador, tabs `Case file` (`/investigate`) — Fase 6 agrega `Data estate` —, a la derecha `sourceLabel` opcional, botón opcional `Open another file`, y link discreto `Legacy simulation (deprecated)` → `/investigate/simulation`. Tab activa con `aria-current="page"` usando `usePathname()`.

**3.4 `CaseFileUiContext.tsx`**
```ts
export type DiagramState = { status: "pending" | "ready" | "failed"; renderedSource: string | null; usedFallback: boolean };
interface CaseFileUiContextValue {
  isOpen: (id: string, defaultOpen: boolean) => boolean; setOpen: (id: string, open: boolean) => void;
  expandAll: () => void; collapseAll: () => void;
  reportDiagram: (id: string, state: DiagramState) => void; diagrams: Record<string, DiagramState>; diagramsSettled: boolean;
}
export const CaseFileUiProvider: React.FC<{ expectedDiagramIds: string[]; children: React.ReactNode }>;
export function useCaseFileUi(): CaseFileUiContextValue;
```
- `openMap` + `override: boolean | null`; `isOpen = openMap[id] ?? override ?? defaultOpen`; `expandAll` = `setOverride(true); setOpenMap({})`; `collapseAll` = `setOverride(false); setOpenMap({})`.
- `reportDiagram` solo hace `setState` si cambió algún campo.
- `diagramsSettled = expectedDiagramIds.every(id => diagrams[id] && diagrams[id].status !== "pending")`; `expectedDiagramIds` = `anchorId` de hallazgos con `mermaidPrimary || mermaidGenerated`.

**3.5 `Collapsible.tsx`** — `interface CollapsibleProps { id: string; defaultOpen: boolean; summary: React.ReactNode; children: React.ReactNode; className?: string; summaryClassName?: string; }`. `<button type="button" aria-expanded aria-controls={`${id}-body`}>` + `summary` + `<ChevronDown data-print="hide" data-export="exclude" />` (rotado si abierto) y `<div id={`${id}-body`} data-collapsible-body hidden={!open}>`. **Siempre** renderizar el cuerpo con `hidden`, nunca condicional.

**3.6 `CaseFileWorkspace.tsx`**
```tsx
<div className="case-workspace min-h-[100dvh] bg-background text-foreground">
  <InvestigateAppBar sourceLabel={loaded?.source.label} onReset={loaded ? reset : undefined} />
  {!loaded ? <CaseFileSourcePanel /> : (
    <CaseFileUiProvider key={loaded.loadId} expectedDiagramIds={...}>
      <ExportToolbar />       {/* sticky, data-print="hide" (F5) */}
      <ValidationPanel />     {/* data-print="hide", cerrado por defecto */}
      <main className="px-4 py-8 sm:px-6 print:p-0"><CaseFileDocument /></main>
    </CaseFileUiProvider>
  )}
</div>
```
- `view = useMemo(() => buildCaseFileView(loaded.document), [loaded])`; `issues = [...structureIssues, ...collectWarnings(view)]`.
- Dev (`process.env.NODE_ENV !== "production"`): `useEffect` por `loadId` → `console.warn("[case-file] " + path + ": " + message)` una vez por issue; expone `window.__caseFileDebug = { buildMarkdown, buildHtml, issues }` (limpiar en teardown; declarar el tipo con `declare global`).
- Mientras hay caso: `document.title = `case-file-seed-${seed ?? "unknown"}``; restaurar al desmontar.
- En Fase 3 `ExportToolbar` puede ser un placeholder mínimo con solo `Expand all`/`Collapse all`; se completa en Fase 5.

**3.7 `CaseFileSourcePanel.tsx`** (oscuro, `mx-auto max-w-2xl py-16`)
- `h1`: `"Open a forensic case file"`; `p`: `"Load the JSON your auditor run produced — the same submission.json checked by validate_format.py — to render the case file, or open the illustrative sample."`
- Botón `app-primary` `"Open sample case"` (`FileText`).
- Dropzone (`role="button"`, `tabIndex={0}`, Enter/Space abren `<input type="file" accept=".json,application/json" className="sr-only">`, drag&drop): `"Drop submission JSON here or browse"`, sub `"Read locally in your browser. Nothing is uploaded. Max 5 MB."` (`Upload`).
- Link: `"Have .db, .csv or .xml estate data? Open the Data estate page"` → `/investigate/data`.
- API habilitada: input `"Backend case ID"` + botón `"Load from backend"`.
- Solo dev: `<select>` `"Developer fixtures"` con las 3 fixtures.
- Error en `<p role="alert" className="text-status-danger">`.

**3.8 `ValidationPanel.tsx` / `IssueNotice.tsx`**
- `ValidationPanel`: título `"Format check (mirrors validate_format.py)"`; subtítulo `"Structure only. Exhibit records are checked only when a data estate is loaded."`; grupos Errors / Warnings con `path` mono. Visible en todos los modos, solo pantalla.
- `IssueNotice({ issues })`: `null` en producción o sin issues; si no, caja `data-print="hide" data-export="exclude"` (error: borde `evidence-proven`; warning: borde `evidence-probable`) con `TriangleAlert`. Filtrado por prefijo de `path`.

> ⛔ **CHECKPOINT FASE 3** — Criterios de salida: `tsc` 0 errores; con `npm run dev` (vía skill `run`/Browser preview): `/investigate` muestra el panel de carga; "Open sample case" carga sin errores de consola (el documento puede estar incompleto); `/investigate/simulation` funciona con banner; `/` sin cambios. Registrar y **detenerse**.

### Fase 4 — Documento y secciones (T1–T12)

**4.0 `CaseFileDocument.tsx`**
- `<article id="case-file-document" className="case-paper mx-auto max-w-[960px] rounded-sm bg-paper px-6 py-8 text-paper-ink shadow-panel ring-1 ring-paper-border sm:px-12 sm:py-12">`
- Si `source.kind === "sample"`: primer hijo (se exporta e imprime) `"Sample data — illustrative, fictional entities. Not a real audit."` (`border border-evidence-probable bg-evidence-probable-soft px-3 py-2 font-mono text-xs text-evidence-probable`).
- Orden EXACTO: `CaseHeader` (`#case-header`) → índice `<nav aria-label="Contents" id="contents">` (links 1–5 y cada hallazgo) → `ExecutiveSummary` (`#executive-summary`) → `<section id="findings">` con `h2 "3. Findings"` y un `FindingSection` por hallazgo (0: `"No findings were validated in this run."`) → `LeadsNotPursued` (`#leads-not-pursued`) → `MethodAndLimits` (`#method-and-limits`) → pie `font-mono text-[11px] text-paper-muted`: `` `Case file for estate seed ${seed} · Format check: ${errors === 0 ? "PASS" : `${errors} error(s)`}` ``.
- `h2` = `mb-6 mt-12 border-b border-paper-ink pb-2 font-serif text-2xl font-semibold tracking-tight`; `h4` de hallazgo = `mb-2 mt-8 font-mono text-[11px] uppercase tracking-[0.16em] text-paper-muted`.

**4.1 T1 `CaseHeader.tsx`**
- Eyebrow `font-mono text-[11px] uppercase tracking-[0.18em] text-paper-muted`: `"Forensic case file · 1. Header"`.
- `h1 font-serif text-3xl font-semibold`: `header.company` o `"Company not reported"` (`text-paper-muted`).
- Línea mono `text-sm text-paper-muted`: `RFC {company_rfc}` · `Audit period {start} → {end}` (faltantes → `not reported`).
- Cintillo: `<dl className="mt-6 grid grid-cols-2 overflow-hidden rounded-sm border border-paper-ink bg-paper-ink font-mono text-paper sm:grid-cols-5">`; celdas `px-4 py-3 sm:border-l sm:first:border-l-0 border-paper/15`; `dt` `text-[10px] uppercase tracking-[0.16em] text-paper/60`; `dd` `mt-1 text-sm font-semibold tabular-nums`:
  `Seed` → `#${seed}` · `LLM calls` → `formatInteger` · `MXN cost` → `formatPesos` · `Wall clock` → `formatSeconds` · `Determinism` → badge. `null` → `"Not reported"` (`text-paper/60`).
- Badge (`inline-flex gap-1 rounded-sm px-2 py-0.5 text-[11px] font-bold`): `true` → `bg-evidence-reconciled text-white` `ShieldCheck` `REPRODUCIBLE (SEED ${seed})`; `false` → `bg-evidence-probable text-white` `TriangleAlert` `NON-DETERMINISTIC RUN`; `null` → `bg-paper-muted text-white` `DETERMINISM NOT REPORTED`.
- `cost_by_role` con claves: `mt-2 font-mono text-xs text-paper-muted` `Cost by role: ` + claves **alfabéticas** `key formatPesos(v)` unidas con ` · `.

**4.2 T2 `ExecutiveSummary.tsx` + `ConfidenceBadge.tsx`**
- `h2 "2. Executive summary"`; `<p className="max-w-prose font-serif text-[17px] leading-8">`; si derivada: `text-xs text-paper-muted` `"Summary generated from the findings data (the run supplied no narrative)."`
- Tarjetas `grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 print:grid-cols-4`, cada una `case-avoid-break rounded-sm border border-paper-border bg-paper-raised p-4`:
  1. `Findings` → `findingsCount` (`font-serif text-3xl`), sub `"validated accusations"`.
  2. `Overall confidence` → `ConfidenceBadge(globalConfidence)`, sub `` `${proven} proven · ${probable} probable` `` (+ `` ` · ${invalid} invalid` ``).
  3. `Total exposure` → `formatPesos` (`font-mono text-2xl tabular-nums`), sub `"sum of finding amounts"`.
  4. `Leads investigated and closed` → `closedLeadsCount`, sub `"closed without an accusation"`.
- `ConfidenceBadge { value: string | null; size?: "sm" | "lg"; showDescription?: boolean }`, `data-confidence={value ?? ""}`: `proven` → `bg-evidence-proven text-white` `Gavel` `PROVEN`; `probable` → `bg-evidence-probable text-white` `TriangleAlert` `PROBABLE`; `null` → `bg-evidence-neutral-soft text-evidence-neutral` `NO FINDINGS`; inválido → `border border-evidence-proven text-evidence-proven` `` `INVALID CONFIDENCE: ${value}` ``. `lg` = `px-3 py-1.5 text-sm`; `sm` = `px-2 py-0.5 text-[11px]`. `showDescription` agrega `CONFIDENCE_COPY[value].description`.

**4.3 T3 `FindingSection.tsx` + `EntityId.tsx` + `SchemeTypeBadge.tsx`**
- `<section id={anchorId} data-finding-section data-scheme-type={finding.scheme_type} className="mt-10 border-t-2 border-paper-ink pt-6 first:mt-0">`.
- `Collapsible` id `anchorId`, `defaultOpen: true`. Summary: eyebrow mono `` `Finding ${number} of ${total} · Workpaper ${workpaperId}` ``; `<h3 className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">` con cada `EntityId` + `SchemeTypeBadge`; a la derecha `formatPesos(peso_amount)` + `ConfidenceBadge size="sm"` + chevron.
- `EntityId`: `<span data-entity-id={id} className="font-mono text-sm font-bold text-paper-ink">{id}</span>`, nombre `font-serif text-base` si existe, `kindLabel` `text-[11px] text-paper-muted`; sin `:` → chip rojo `"Missing id prefix"`; prefijo desconocido → chip ámbar `"Unknown id prefix"`.
- `SchemeTypeBadge`: `<span data-scheme-type={raw} className="inline-flex items-center gap-1.5 rounded-sm border border-paper-ink/30 bg-paper-raised px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-paper-ink">{SCHEME_LABELS[raw]}<code className="font-mono text-[10px] normal-case opacity-70">{raw}</code></span>`. Inválido: `border-evidence-proven bg-evidence-proven-soft text-evidence-proven` + `Invalid scheme type` + `<code>{raw}</code>`.
- Cuerpo en orden EXACTO con su `h4`: `Rule broken` → `Amount and confidence` → `What happened` → `Money trail` → `Exhibits` → `Reconciliation` → `Adversarial review`, cada uno con su `IssueNotice`.

**4.4 T4 `RuleBrokenCallout.tsx`** — `<aside role="note" className="case-avoid-break border-l-4 border-evidence-proven bg-evidence-proven-soft/60 px-5 py-4">`: `Scale` + `<p className="font-serif text-lg font-semibold">{rule.title}</p>` + chip `rule.code` (`border border-evidence-proven/40 px-1.5 font-mono text-[11px]`); `citation` → `<blockquote className="mt-2 font-serif italic leading-7">“{citation}”</blockquote>`; con `rule_detail` → `mt-2 font-mono text-[11px] text-paper-muted` `` `Cited as: ${citedAs}` ``. `IssueNotice` para `W_RULE_STATISTICAL` y error de `rule_broken` vacío.

**4.5 T5 `AmountConfidence.tsx`** — `flex flex-wrap items-end justify-between gap-4`; izq. caption `Amount at issue` + `<p className="font-mono text-3xl font-semibold tabular-nums">` (`null` → `"Amount not reported"` `text-evidence-probable`); der. `ConfidenceBadge size="lg" showDescription`.

**4.6 T6 `FindingNarrative.tsx`** — `<p className="max-w-prose whitespace-pre-line font-serif text-base leading-7">`. Solo dev: `font-mono text-[11px] text-paper-muted` `` `${words} / 150 words` `` (rojo si > 150) + `IssueNotice` del error `E_NARRATIVE_WORDS`.

**4.7 T7 `MoneyTrail.tsx` + `MermaidDiagram.tsx` + `MoneyTrailTimeline.tsx`**
- `trail === null`: `border border-dashed border-paper-border p-4 text-sm text-paper-muted` `"No money trail was supplied for this finding."` (siempre) + `IssueNotice`.
- `<figure className="case-avoid-break rounded-sm border border-paper-border bg-white p-4">`:
  - Zoom (`data-print="hide" data-export="exclude"`): `Fit` (default → wrapper `[&_svg]:max-w-full`) | `100%` (→ `case-scroll overflow-x-auto [&_svg]:!max-w-none`).
  - `MermaidDiagram { diagramId: string; primarySource: string | null; fallbackSource: string | null; ariaLabel: string }`: efecto → `reportDiagram(pending)` → `renderMermaidSvg(`${diagramId}-svg`, primary)`; si falla y hay fallback → intentar fallback (`usedFallback: true`); éxito → `reportDiagram(ready, renderedSource)`; ambos fallan → `failed`. Flag `cancelled` en cleanup. `<div role="img" aria-label={ariaLabel} dangerouslySetInnerHTML={{ __html: svg }} />` (seguro por `securityLevel: "strict"`). Cargando `"Rendering diagram…"`; fallido `"The money trail diagram could not be rendered."` + `<details data-print="hide" data-export="exclude">` con el error.
  - `<figcaption className="mt-3 font-mono text-[11px] text-paper-muted">`: `` `Figure ${number}. Money trail — ${steps} step(s). Diagram source: ${usedFallback || !primary ? "generated from money_trail steps" : "supplied by the run"}${usedFallback && primary ? " (supplied diagram failed to render)" : ""}.` ``
  - `<details data-print="hide" data-export="exclude"><summary>View diagram source</summary><pre className="overflow-x-auto font-mono text-xs">…</pre></details>`.
- `MoneyTrailTimeline` `<ol>`, `li` = `case-avoid-break grid grid-cols-[auto_1fr] gap-4`: círculo `grid h-7 w-7 place-items-center rounded-full border-2 border-paper-ink font-mono text-xs` con `stepOrder` + línea `w-px bg-paper-border`; contenido: fecha (string tal cual) · `{fromName} <mono>{from}</mono> → {toName} <mono>{to}</mono>` · `formatPesos(amount)` · chip `<a href={`#${exhibitAnchor}`} data-exhibit-ref className="rounded-sm border border-evidence-held bg-evidence-held-soft px-1.5 font-mono text-[11px] text-evidence-held">{exhibit_id}</a>` (no resuelto → `<span>` rojo `title="Not found in this finding's exhibits"`). `breaksAfter` → `border-t border-dashed border-evidence-probable` + `text-[11px] text-evidence-probable` `` `Trail breaks here: step ${k} ends at ${to}, step ${k+1} starts at ${nextFrom}.` `` (siempre visible).

**4.8 T8 `ExhibitsTable.tsx`**
- Cabecera cédula `flex justify-between border border-b-0 border-paper-ink bg-paper-raised px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em]`: `` `Workpaper ${workpaperId} · Exhibit schedule` `` | `` `${n} exhibits · minimum 3` `` (rojo si < 3).
- `<div className="case-scroll overflow-x-auto"><table className="w-full min-w-[640px] table-fixed border-collapse border border-paper-ink text-sm">`, `<colgroup>` 14/18/22/46 %.
- `thead` `bg-paper-ink font-mono text-[11px] uppercase tracking-[0.12em] text-paper`; columnas EXACTAS: `Exhibit ID`, `Source table`, `Record ID`, `What it proves`.
- `<tr id={exhibitAnchor} className="scroll-mt-24 border-t border-paper-border align-top odd:bg-white even:bg-paper-raised target:bg-evidence-held-soft">`, celdas `px-3 py-2`: `exhibit_id` mono bold (duplicado → `duplicate` rojo); `source_table` mono + (si ∈ `AMOUNT_COLUMN`) `text-[11px] text-paper-muted` `` `${col}: ${formatPesos(amount)}` `` o `` `${col}: amount not supplied` ``; inválida → `invalid table` rojo; `record_id` mono `break-all`; `note` serif.
- `tfoot` (`colSpan=4`, `text-[11px] text-paper-muted`): `"Amount-bearing columns used for reconciliation: invoices.total, bank_txns.amount, purchase_orders.amount, contracts.value."`

**4.9 T9 `ReconciliationBlock.tsx`**
- `<div className="case-avoid-break overflow-hidden rounded-sm border border-paper-ink">`; `<dl>` 3 filas `grid grid-cols-[1fr_auto] gap-4 border-b border-paper-border px-4 py-2`, valores `text-right font-mono tabular-nums`:
  1. `Claimed amount` → `formatPesos(claimed)`
  2. `` `Sum of cited exhibits — best-matching table ${matchedTable}` `` (tabla en `<code>`) → `formatPesos(matchedSubtotal)`
  3. `Variance (Δ)` → `` `${formatPesos(delta)} (${variancePct.toFixed(2)}%)` ``
- Barra estado `flex items-center gap-2 px-4 py-2 font-mono text-xs font-bold`: `reconciled` → `bg-evidence-reconciled text-white` `CircleCheck` `RECONCILED (≤ 2% VARIANCE)`; `not_reconciled` → `bg-evidence-proven text-white` `CircleX` `NOT RECONCILED — VARIANCE EXCEEDS 2%`; `unverifiable` → `bg-paper-muted text-white` `CircleHelp` `NOT VERIFIABLE — NO EXHIBIT AMOUNTS SUPPLIED` (filas con `—`).
- Mini‑tabla `Per-table subtotals` (Table | Subtotal | `matched`).
- `text-[11px] text-paper-muted`: `"Amounts reconcile per table: an invoice and the bank transfer that settled it are the same pesos seen twice, so subtotals are never added across tables."` + origen: `estate` → `"Computed in the browser from the loaded data estate."`; `derived` → `"Computed in the browser from exhibit amounts."`; `backend` → `"Reported by the run."`.

**4.10 T10 `AdversarialReview.tsx`** — con datos: `<div className="case-avoid-break grid border border-paper-border md:grid-cols-2 print:grid-cols-2">`; izq. `bg-evidence-neutral-soft p-4 md:border-r md:border-paper-border`: `Swords` + `"Defense position"`, sub mono `` `Challenger · ${reviewer_agent_role}` ``, cuerpo serif; der. `bg-evidence-held-soft p-4`: `ShieldCheck text-evidence-held` + `"Why the finding held"`, cuerpo serif. Sin datos: `text-sm italic text-paper-muted` `"No adversarial review was recorded for this finding."`

**4.11 T11 `LeadsNotPursued.tsx`**
- `h2 "4. Leads investigated and closed"`; intro `"Each entry is a lead that tripped a detector, was investigated, and was closed without an accusation."`
- Filtros (`data-print="hide" data-export="exclude"`, `flex flex-wrap gap-2`): search (`Search`) `"Filter by entity or name"` (includes case‑insensitive en `entity` y `name`); select Closed by `All closers | Investigator | Adversarial reviewer | Validator | Not recorded` (inválidos = Not recorded); select Closure type `All closure types | Materiality verified | Administrative error | No bank correlation | Other | Unclassified`; `` `Showing ${x} of ${y}` ``; botón `"Clear filters"`.
- Tabla `case-scroll overflow-x-auto`, `min-w-[760px] table-fixed`, anchos 20/20/32/16/12; columnas EXACTAS `Entity`, `Signal`, `Reason closed`, `Tools called`, `Closed by`.
- `<tr id={anchorId} data-filterable-row hidden={!matches}>` (**filtrar con `hidden`, nunca desmontar**).
  - Entity: `EntityId` + nombre + tag: `materiality_verified` → `bg-evidence-reconciled-soft text-evidence-reconciled`; `administrative_error` → `bg-evidence-probable-soft text-evidence-probable`; `no_bank_correlation` → `bg-evidence-held-soft text-evidence-held`; `other` → `bg-evidence-neutral-soft text-evidence-neutral`; ninguna/inválida → `border border-paper-border text-paper-muted` `Unclassified`.
  - Tools: `` `${n} call(s)` `` + chips mono 11px; vacío → ámbar `"No tool calls recorded"`.
  - Closed by: investigator neutro, challenger azul held, validator verde reconciled; ausente `Not recorded`; inválido rojo `` `Invalid: ${raw}` ``.
- Sin leads: `"No leads were closed in this run."`; sin coincidencias: fila `data-print="hide"` `"No leads match the current filters."`. `IssueNotice` por fila.

**4.12 T12 `MethodAndLimits.tsx`** — `<section id="method-and-limits" className="border-t-2 border-paper-ink">`, `h2 "5. Method and limits"`; 4 `Collapsible` `defaultOpen: false` (ids `method-architecture`, `method-out-of-scope`, `method-cannot-detect`, `method-reproducibility`) con títulos EXACTOS `Architecture` (párrafo), `Out of scope for this run` (`ul list-disc`), `What this system cannot detect` (`ul list-disc`), `Reproducibility` (`ol list-decimal`). Vacío/ausente → `italic text-paper-muted` `"Not provided by this run."`

> ⛔ **CHECKPOINT FASE 4** (hacer mini‑checkpoint de `tsc` también tras 4.3 y 4.7) — Criterios de salida: `tsc` 0 errores; en navegador con el **sample**: se ven las 5 secciones en orden, F1 con diagrama "supplied by the run", F2 con diagrama "generated", reconciliaciones correctas, filtros de leads funcionando; con **edge-cases** la app no crashea. Consola sin errores (solo `[case-file]` warnings en edge-cases). Registrar y **detenerse**.

### Fase 5 — Motor de exportación (T13)

**5.1 `ExportToolbar.tsx`** — `<div data-print="hide" className="sticky top-0 z-30 border-b border-surface-border bg-surface-deep/95 backdrop-blur">`, interior `mx-auto flex max-w-[1200px] flex-wrap items-center gap-2 px-4 py-2`.
- Izq.: chip fuente (`Sample data` / `Local file: x.json` / `Backend case X` / `From Data estate page`); chip formato (abre/cierra `ValidationPanel`): sin errores ni warnings → verde `Format check: PASS`; sin errores con warnings → verde `` `Format check: PASS · ${w} warning(s)` ``; errores → rojo `` `Format check: ${e} error(s) · ${w} warning(s)` ``. (Fase 6 agrega chip de estate.)
- Der.: `Expand all`, `Collapse all`, separador, `Print / PDF` (`Printer`), `HTML` (`FileCode2`), `Markdown` (`FileText`), `JSON` (`FileJson`); clase `app-button text-xs`; export `disabled={!diagramsSettled}` con `title="Rendering diagrams…"`.
- Acciones (`seed === null` → `unknown` en nombres):
  - Print → `window.print()`.
  - HTML → `downloadTextFile(`case-file-seed-${seed}.html`, buildStandaloneHtml({ documentElement: document.getElementById("case-file-document")!, title: `Case file · seed ${seed}`, raw }), "text/html;charset=utf-8")`.
  - Markdown → `downloadTextFile(`case-file-seed-${seed}.md`, buildCaseFileMarkdown(view, { isSample, renderedSources, estateChecked }), "text/markdown;charset=utf-8")`.
  - JSON → `downloadTextFile(`submission-seed-${seed}.json`, JSON.stringify(raw, null, 2) + "\n", "application/json")`.

**5.2 `app/globals.css`** — agregar Apéndice D al final.

> ⛔ **CHECKPOINT FASE 5** — Criterios de salida: `tsc` 0 errores; en consola del navegador con sample: `__caseFileDebug.buildMarkdown() === __caseFileDebug.buildMarkdown()` → `true`; `buildHtml()` contiene 2 `<svg`, `id="case-file-data"`, sin `data-collapsible-body hidden`, sin `<script src`, y `/(src|href)="https?:|url\(https?:/.test(h) === false`; con todo colapsado y filtros activos, el HTML sigue trayendo todo. `npm run build` pasa. Registrar y **detenerse**.

### Fase 6 — Página Data Estate: carga y manejo de XML, DB, CSV y JSON

Objetivo: `/investigate/data` para cargar el estate en cualquiera de los 4 formatos, validarlo contra `estate_schema.sql`, previsualizarlo, exportarlo como `estate.db`/`estate.json` y conectar el visor para verificar exhibits (paridad con `validate_format.py --estate`).

**6.1 Dependencias y WASM**
1. `cd frontend && npm install sql.js@1.14.2 papaparse@5.7.0 --save-exact && npm install -D @types/sql.js@1.4.11 @types/papaparse@5.5.2 --save-exact`.
2. Ver qué WASM usa la entrada de navegador: `grep -o "sql-wasm[a-z-]*\.wasm" node_modules/sql.js/dist/sql-wasm-browser.js | sort -u` (si no existe ese archivo, usar `dist/sql-wasm.js`). Ese nombre es `WASM_SOURCE`.
3. `package.json` scripts: `"copy:sqlwasm": "node -e \"require('fs').mkdirSync('public',{recursive:true});require('fs').copyFileSync('node_modules/sql.js/dist/<WASM_SOURCE>','public/sql-wasm.wasm')\""`, `"predev": "npm run copy:sqlwasm"`, `"prebuild": "npm run copy:sqlwasm"`. Correr `npm run copy:sqlwasm`.
4. Root `.gitignore`: **agregar al final** (sin tocar lo demás) `frontend/public/sql-wasm.wasm`.
5. `next.config.js`: agregar `webpack: (config, { isServer }) => { if (!isServer) { config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false, crypto: false }; } return config; }` manteniendo `reactStrictMode: true`.
6. `lib/estate/sqlite.ts`: `loadSqlJs()` singleton con `import("sql.js")` dinámico y `initSqlJs({ locateFile: () => "/sql-wasm.wasm" })`.

**6.2 `lib/estate/schema.ts`**
- `ESTATE_TABLE_ORDER` (orden del archivo SQL): `vendors, invoices, ledger, bank_txns, purchase_orders, contracts, employees, efos_list`.
- `ESTATE_SCHEMA: Record<SourceTable, EstateColumnSpec[]>` EXACTO según `estate_schema.sql`:
  - vendors: `rfc TEXT PK, legal_name TEXT, registered_date TEXT, address TEXT, bank_clabe TEXT, category TEXT, contact_email TEXT`
  - invoices: `uuid TEXT PK, issuer_rfc TEXT, receiver_rfc TEXT, issue_date TEXT, subtotal REAL, iva REAL, total REAL, concepto_text TEXT, uso_cfdi TEXT, forma_pago TEXT, metodo_pago TEXT, status TEXT`
  - ledger: `entry_id INTEGER PK, date TEXT, account_code TEXT, account_name TEXT, debit REAL, credit REAL, description TEXT, invoice_uuid TEXT, cost_center TEXT, approver TEXT`
  - bank_txns: `txn_id TEXT PK, date TEXT, from_clabe TEXT, to_clabe TEXT, amount REAL, reference TEXT, channel TEXT`
  - purchase_orders: `po_id TEXT PK, vendor_rfc TEXT, date TEXT, amount REAL, requester TEXT, approver TEXT, description TEXT`
  - contracts: `contract_id TEXT PK, vendor_rfc TEXT, start_date TEXT, value REAL, scope_text TEXT`
  - employees: `emp_id TEXT PK, name TEXT, role TEXT, bank_clabe TEXT, hire_date TEXT`
  - efos_list: `rfc TEXT PK, legal_name TEXT, status TEXT, publication_date TEXT`
- `ESTATE_DDL`: los 8 `CREATE TABLE` copiados **literalmente** de `estate_schema.sql` sin comentarios.
- `REQUIRED_COLUMNS` (vacío → warning `W_REQUIRED_EMPTY`): vendors `rfc, legal_name`; invoices `uuid, issuer_rfc, receiver_rfc, issue_date, total`; ledger `entry_id, date, account_code`; bank_txns `txn_id, date, amount`; purchase_orders `po_id, vendor_rfc, amount`; contracts `contract_id, vendor_rfc, value`; employees `emp_id, name, bank_clabe`; efos_list `rfc, status`.
- `MAX_ESTATE_FILE_BYTES = 50 * 1024 * 1024`, `MAX_FILES_PER_BATCH = 50`, `PREVIEW_PAGE_SIZE = 50`.
- `emptyEstateTables(): EstateTables`.

**6.3 `lib/estate/coerce.ts`** — `coerceRow(table, record: Record<string, unknown>, ctx: { fileName: string; rowIndex: number }): { row: EstateRow; issues: EstateIssue[] }`:
- Match de claves case‑insensitive tras `trim()`; claves desconocidas → `W_UNKNOWN_COLUMN` (una vez por archivo+columna) y se descartan; columnas faltantes → `null` (`W_MISSING_COLUMN` una vez por archivo+columna).
- Strings `trim()`; `""` → `null`.
- `REAL`/`INTEGER`: número finito tal cual; string → quitar comas **solo** si matchea `^-?\d{1,3}(,\d{3})+(\.\d+)?$`, luego `Number()`; no finito → `null` + error `E_TYPE`; `INTEGER` no entero → error `E_TYPE`.
- `TEXT`: número → `String(n)`; si la columna termina en `clabe` y llegó como número → warning `W_CLABE_NUMERIC` ("leading zeros may have been lost"). Blob/objeto → `null` + `E_TYPE`.

**6.4 Parsers** (todos devuelven `{ detectedAs: string; status: EstateFileStatus; contributions; pendingCsv; caseFileRaw; fileIssues }`)
- `parseCsv.ts`: `Papa.parse<string[]>(text.replace(/^﻿/, ""), { skipEmptyLines: "greedy" })` (delimitador autodetectado). Fila 0 = header. Tabla: (a) nombre de archivo sin extensión, lowercase, que **termine** en un nombre de tabla con `/(^|[_\-. ])(ledger|invoices|bank_txns|vendors|efos_list|purchase_orders|contracts|employees)$/`; (b) si no, por header: candidata si contiene la PK y `matched/columns ≥ 0.6`; gana la de mayor ratio; empate o ninguna → `status "needs_table"` guardando `pendingCsv`. `detectedAs` `` `CSV → ${table}` `` o `"CSV → table not detected"`. Filas con distinto número de columnas → warning `W_CSV_ROW_LENGTH`.
- `parseJson.ts`: (a) objeto con alguna de `findings`/`leads_not_pursued`/`run_metadata` → `status "case_file"`, `caseFileRaw`, `detectedAs "Case file JSON"`; (b) objeto con ≥1 clave ∈ tablas cuyo valor es array de objetos → tablas (`` `Estate JSON (${n} tables)` ``; claves no‑tabla → `W_UNKNOWN_KEY`); (c) array de objetos + tabla detectada por nombre de archivo (regla CSV‑a) → esa tabla; si no → `failed` `"Unsupported JSON: expected a case file, an object keyed by table name, or an array named after a table (e.g. vendors.json)."`
- `parseXml.ts`: `new DOMParser().parseFromString(text, "application/xml")`; si hay `parsererror` → `failed` `"Invalid XML."`
  - **CFDI 4.0** (raíz `localName === "Comprobante"`) → 1 fila `invoices` (`detectedAs "CFDI 4.0 invoice"`). Mapeo EXACTO (buscar por `localName`, namespace‑agnóstico):
    `uuid` ← `TimbreFiscalDigital@UUID` dentro de `Complemento` (si falta: `` `${Serie ?? ""}${Folio}` `` + warning `W_CFDI_NO_UUID`; si tampoco hay Folio → `failed`) · `issuer_rfc` ← `Emisor@Rfc` · `receiver_rfc` ← `Receptor@Rfc` · `issue_date` ← `@Fecha` · `subtotal` ← `@SubTotal` · `iva` ← `@TotalImpuestosTrasladados` del `Impuestos` **hijo directo** de `Comprobante` (no el de `Concepto`; usar `Array.from(root.children)`), si no existe → suma de sus `Traslado` con `Impuesto="002"`, si tampoco → `null` + `W_CFDI_NO_IVA` · `total` ← `@Total` · `concepto_text` ← `Concepto@Descripcion` unidos con ` | ` · `uso_cfdi` ← `Receptor@UsoCFDI` · `forma_pago` ← `@FormaPago` · `metodo_pago` ← `@MetodoPago` · `status` ← `null` + warning `W_CFDI_STATUS_UNKNOWN` (`"CFDI XML does not carry SAT cancellation status; provide status in invoices data if known."`).
    `Version` ≠ `4.0` → warning `W_CFDI_VERSION`. No crear filas de `vendors` a partir del XML.
  - **Estate XML** (raíz `estate`, o raíz con nombre de tabla): hijos con nombre de tabla → hijos `row` → hijos = columnas (texto; vacío → `null`). `` `Estate XML (${n} tables)` ``.
  - Otro → `failed` `"Unsupported XML: expected a CFDI 4.0 Comprobante or an <estate> document."`
- `sqlite.ts` (además de `loadSqlJs`):
  - `parseSqliteFile(bytes: Uint8Array, fileName)`: primeros 16 bytes deben ser `"SQLite format 3\0"` → si no, `failed` `"Not a SQLite database file."`. `new SQL.Database(bytes)`; tablas de `sqlite_master`; por cada tabla del estate presente `db.exec(`SELECT * FROM ${table}`)` (**solo nombres de la whitelist**) → objetos → `coerceRow`; tablas faltantes → `W_TABLE_MISSING`; tablas extra → ignoradas (`W_EXTRA_TABLE` una por archivo); `db.close()` en `finally`. `` `SQLite estate (${n} of 8 tables)` ``.
  - `exportEstateSqlite(tables: EstateTables): Promise<Uint8Array>`: `db.run(ESTATE_DDL)`; `BEGIN`; por tabla en `ESTATE_TABLE_ORDER` un `prepare("INSERT INTO t (cols) VALUES (?,…)")`, `run` por fila en orden de columnas del schema, `free()`; `COMMIT`; `db.export()`; `db.close()`.
- `ingest.ts`: `ingestFile(file: File, id: string): Promise<EstateFileEntry>` — por extensión en minúsculas: `.db/.sqlite/.sqlite3` → sqlite; `.csv` → csv; `.json` → json; `.xml` → xml; otra → `failed` `"Unsupported file type. Use .db, .sqlite, .csv, .json or .xml."`; `size > MAX_ESTATE_FILE_BYTES` → `failed` `"File exceeds 50 MB."`. Excepciones del parser → `failed` con el mensaje. `assignCsvTable(entry, table)`: convierte `pendingCsv` con `coerceRow` → `imported`.

**6.5 `lib/estate/validateEstate.ts`** — `buildEstate(files: EstateFileEntry[]): { tables: EstateTables; issues: EstateIssue[] }`:
- Plegar `contributions` de archivos `imported` en orden; PK duplicada → se conserva la primera, error `E_DUPLICATE_PK` (`` `${table}.${pk} appears again in ${fileName}; the first occurrence was kept.` ``); PK `null` → error `E_PK_EMPTY` y la fila se descarta.
- Reglas por fila (warnings salvo indicación; formato y enums solo se evalúan sobre valores **no nulos**):
  - RFC (`vendors.rfc`, `efos_list.rfc`, `invoices.issuer_rfc/receiver_rfc`, `purchase_orders.vendor_rfc`, `contracts.vendor_rfc`): `/^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/` → `W_RFC_FORMAT`.
  - CLABE (`vendors.bank_clabe`, `employees.bank_clabe`, `bank_txns.from_clabe/to_clabe`): `/^\d{18}$/` → `W_CLABE_FORMAT`.
  - Fechas (`registered_date, issue_date, ledger.date, bank_txns.date, purchase_orders.date, start_date, hire_date, publication_date`): `/^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/` → `W_DATE_FORMAT`.
  - Enums: `metodo_pago ∈ {PUE, PPD}`, `invoices.status ∈ {vigente, cancelado}`, `channel ∈ {SPEI, cheque, efectivo}`, `efos_list.status ∈ {definitivo, presunto}` → `W_ENUM_VALUE`.
  - invoices: `|iva − 0.16·subtotal| > 0.01` → `W_IVA_RATE`; `|total − (subtotal + iva)| > 0.01` → `W_TOTAL_MISMATCH` (solo si los 3 no son null).
  - ledger: `debit > 0 && credit > 0` → `W_LEDGER_BOTH_SIDES`.
  - employees: `emp_id` `/^EMP:\d{4}$/` → `W_EMP_ID_FORMAT`.
  - `REQUIRED_COLUMNS` vacíos → `W_REQUIRED_EMPTY`.
  - Referenciales: `purchase_orders.vendor_rfc` y `contracts.vendor_rfc` ∈ `vendors.rfc` → `W_REF_VENDOR`; `ledger.invoice_uuid` (no null) ∈ `invoices.uuid` → `W_REF_INVOICE`.

**6.6 `lib/estate/estateCheck.ts`** (paridad con `validate_against_estate`)
- `findEstateRecord(tables, table, recordId): EstateRow | null` — compara `String(row[ID_COLUMN[table]]) === String(recordId)` (equivale a la afinidad de SQLite en `entry_id = '5521'`).
- `validateAgainstEstate(document, tables): ValidationIssue[]` por hallazgo `i`:
  - Exhibit `j` con tabla inválida → se omite (ya es error de estructura). Registro inexistente → error `E_ESTATE_RECORD_MISSING` `` `findings[${i}].exhibits[${j}]: ${table}.${rid} does not exist in the loaded estate` `` y `continue`.
  - Si la tabla tiene `AMOUNT_COLUMN`: `perTable[table] += Number(row[col] ?? 0)`.
  - `perTable` vacío → error `E_ESTATE_NO_AMOUNT` `` `findings[${i}]: no exhibit cites an amount-bearing table (['bank_txns', 'contracts', 'invoices', 'purchase_orders']), so peso_amount cannot reconcile` ``.
  - Si no: `best` = mínimo `|claimed − v|` (empate → primera en aparecer); `|claimed − best| > 0.02 * max(best, 1)` → error `E_ESTATE_RECONCILE` `` `findings[${i}]: peso_amount ${fmt(claimed)} does not reconcile to cited exhibits [${detail}]` `` con `detail` = tablas ordenadas alfabéticamente `t=fmt(v)` unidas con `, ` y `fmt` = en-US 2 decimales con miles (`139,200.00`).
- Extender `buildCaseFileView(document, estate: EstateTables | null = null)`: con estate, cada exhibit obtiene `estateStatus: "found" | "missing"` y `estateRecord`, y la reconciliación usa **origen `estate`** (prioridad estate > backend > derived) con el algoritmo de arriba; sin estate, `estateStatus: "not_checked"`. Agregar a `FindingView`: `exhibitEstate: Record<string, { status: "not_checked" | "found" | "missing"; record: EstateRow | null }>`.

**6.7 `hooks/useEstate.ts`**
```ts
export interface UseEstateReturn {
  status: "idle" | "processing" | "ready";
  files: EstateFileEntry[]; tables: EstateTables; issues: EstateIssue[]; totalRows: number; hasEstate: boolean;
  addFiles: (files: File[]) => Promise<{ caseFiles: { fileName: string; raw: unknown }[] }>;
  assignTable: (fileId: string, table: SourceTable) => void;
  removeFile: (fileId: string) => void;
  clear: () => void;
  exportSqlite: () => Promise<Uint8Array>;
  exportJson: () => string;   // objeto en ESTATE_TABLE_ORDER, JSON.stringify(obj, null, 2) + "\n"
}
```
- Ids `file-${counter}` con `useRef`. `tables`/`issues` = `useMemo(() => buildEstate(files))` + `fileIssues` de cada archivo. `hasEstate = files.some(f => f.status === "imported")`. Más de `MAX_FILES_PER_BATCH` → procesar los primeros 50 y reportar el resto como `failed`.
- Agregar `estate: UseEstateReturn` a `InvestigateSessionProvider`.

**6.8 UI `/investigate/data`** — `app/investigate/data/page.tsx` (`metadata.title = "Data estate | Polar"`) → `components/estate/DataEstateWorkspace.tsx` (tema oscuro, `mx-auto max-w-[1400px] px-4 py-8 sm:px-6`). `InvestigateAppBar` ahora con tabs `Case file` y `Data estate`.
- Encabezado: `h1 "Data estate"`; `p`: `"Load the company's data estate — SQLite .db, CSV per table, CFDI 4.0 XML invoices, or JSON — and check it against estate_schema.sql. Everything is processed locally in this browser tab and is cleared when the page reloads."`
- `EstateUploadZone`: dropzone multi‑archivo accesible (mismo patrón que 3.7), `accept=".db,.sqlite,.sqlite3,.csv,.json,.xml"`, textos `"Drop estate files here or browse"` / `"Up to 50 files per batch · 50 MB per file"`; botones `"Load sample estate (illustrative)"` (hace `fetch` de los 4 archivos de `public/samples/estate/`, los convierte en `File` y llama `addFiles`) y `"Clear estate"`. Si `addFiles` devuelve `caseFiles`, cargar el primero con `caseFile.loadRaw(raw, { kind: "estate-page", label: `From Data estate page: ${fileName}` })` y mostrar aviso con link `"Case file loaded — open the viewer"`.
- `EstateFileList` (tabla): `File` · `Format` (badge) · `Detected as` · `Rows` · `Issues` (`e/w`) · `Status` (`Imported` verde / `Needs table` ámbar / `Failed` rojo / `Case file` azul) · acciones: `Remove`; para `needs_table` un `<select>` con las 8 tablas + botón `"Import as table"`. Errores de archivo visibles inline.
- `EstateTableSummary`: grid de 8 tarjetas (orden `ESTATE_TABLE_ORDER`): nombre mono, filas, errores/warnings, y para tablas con monto `` `Σ ${col}: ${formatPesos(sum)}` ``; clic selecciona la tabla del preview.
- `EstateTablePreview`: tabs por tabla; columnas en orden del schema; paginación de 50 (`Previous`/`Next`, `` `Rows ${a}–${b} of ${n}` ``); búsqueda `"Search in this table"`; toggle `"Only rows with issues"`; celdas con issue con `bg-status-danger/15` (error) o `bg-status-warning/15` (warning) y `title` = mensaje; `overflow-x-auto`.
- `EstateIssuesPanel`: agrupado por severidad y luego tabla; columnas `Severity · Table · Row · Column · File · Message`; muestra máx. 500 con `` `…and ${n} more` ``.
- `EstateExportBar`: `"Download estate.db"` (`downloadTextFile("estate.db", bytes, "application/vnd.sqlite3")`), `"Download estate.json"`, link `"Open case file viewer"`; si `process.env.NEXT_PUBLIC_ESTATE_UPLOAD_API === "enabled"`: `"Send estate.db to backend"` → `POST ${API}/api/v1/estates/upload` (`FormData` campo `file`), 404 → `"The backend does not accept estate uploads yet (HTTP 404)."`. Agregar a `.env.example`: `NEXT_PUBLIC_ESTATE_UPLOAD_API=disabled` con comentario `# "enabled" shows "Send estate.db to backend" (endpoint proposed, not implemented yet)`.
- Dev: `window.__estateDebug = { ingestText(fileName, content), exportSqliteBase64(), roundTripSqlite(), summary() }` donde `roundTripSqlite` exporta, re‑ingresa el `.db` en un estate temporal y devuelve `{ equal: boolean, counts }`; `summary()` → `{ rows: Record<table, number>, errors, warnings }`.

**6.9 Integración con el visor**
- `CaseFileWorkspace`: `view = buildCaseFileView(document, estate.hasEstate ? estate.tables : null)`; `issues` suma `validateAgainstEstate` cuando hay estate.
- `ExportToolbar`: chip estate: sin estate → `Estate: not loaded` (link a `/investigate/data`); con estate → `Estate check: PASS` (verde) o `` `Estate check: ${n} error(s)` `` (rojo).
- `ExhibitsTable`: en la celda Record ID, con estate: badge `in estate` (`CircleCheck`, verde) o `not in estate` (`CircleX`, rojo); si existe, `<details data-print="hide" data-export="exclude"><summary>View record</summary><dl>` con columnas del schema y valores `</dl></details>`.
- `CaseFileSourcePanel`: si `estate.hasEstate`: nota `` `Data estate loaded (${totalRows} rows). Exhibits will be checked against it.` ``.
- `toMarkdown`: si `estateChecked`, bajo cada reconciliación la línea `Amounts verified against the loaded data estate.`

**6.10 Muestras** — crear `public/samples/estate/` con los archivos de Apéndices F y G (contenido EXACTO).

> ⛔ **CHECKPOINT FASE 6** — Criterios de salida (anotar resultados reales):
> 1. `tsc` 0 errores y `npm run build` pasa (con `prebuild` copiando el WASM).
> 2. `/investigate/data` → "Load sample estate": `__estateDebug.summary()` = filas `vendors 6, invoices 5, ledger 2, bank_txns 4, purchase_orders 2, contracts 2, employees 2, efos_list 1` (24), **0 errores, 2 warnings** (`W_CFDI_STATUS_UNKNOWN` ×2).
> 3. `__estateDebug.roundTripSqlite()` → `equal: true`.
> 4. `__estateDebug.ingestText("export.csv", <contenido de vendors.csv>)` → detectado como `vendors`; `ingestText("data.csv", "foo,bar\n1,2")` → `needs_table` y en la UI el select "Import as table" funciona.
> 5. Guardar `__estateDebug.exportSqliteBase64()` en el scratchpad, decodificar a `estate.db` y correr `python -X utf8 student-materials/forensic-auditor/validate_format.py --submission frontend/fixtures/case-file.sample.json --estate <ruta>/estate.db` → `PASS` con `estate check: yes`; con `case-file.edge-cases.json` → exactamente **13** errores (los 10 de B.2 + 2 registros inexistentes + 1 sin tabla con monto).
> 6. Navegar a `/investigate` (sin recargar), abrir sample: chip `Estate check: PASS`, todos los exhibits `in estate`, reconciliación "Computed in the browser from the loaded data estate."; con edge-cases: `Estate check: 3 error(s)`.
> 7. Subir un `.txt` → `failed` con mensaje; recargar la página → estate vacío.
> Registrar y **detenerse**.

### Fase 7 — Documentación (mismo cambio)

1. `doc/frontend/README.md`: entry points (`/investigate` visor, `/investigate/data` estate, `/investigate/simulation` deprecada), matriz de componentes (`components/case-file/*`, `components/estate/*`, `components/investigate/*`, `lib/caseFile/*`, `lib/estate/*`, hooks), sección "Case file viewer & export engine", sección "Data estate ingestion" (formatos, mapeo CFDI, reglas de validación, export `.db`, verificación de exhibits), dependencias pinned y por qué; §4 simulación marcada deprecada; nota: el money trail del expediente usa Mermaid (el blueprint React Flow queda para exploración de grafos).
2. `doc/architecture/README.md`: "Case file JSON contract (frontend-ready, backend pending)" con las claves de extensión de §4.1, y endpoints **propuestos** `GET /api/v1/investigations/{case_id}/case-file` y `POST /api/v1/estates/upload` (no implementados, detrás de flags).
3. `AGENTS.md`: §7 actualizar entry points/simulación/estate; §6 quitar el gotcha obsoleto de `frontend/lib/` y agregar: mermaid 11.x por Node 20; `python -X utf8` en Windows; `public/sql-wasm.wasm` se genera en `predev`/`prebuild`.
4. `doc/index.md`: actualizar la fila de "Next.js workspace UI" para mencionar visor y data estate.

> ⛔ **CHECKPOINT FASE 7** — Criterios de salida: los 4 archivos actualizados; cada ruta/archivo mencionado existe (verificar con `Glob`); ningún doc afirma que los endpoints propuestos existen. Registrar y **detenerse**.

### Fase 8 — Verificación final

**8.1 Comandos**
1. `cd frontend && npx --no-install tsc --noEmit --incremental false` → 0 errores.
2. Validador: sample PASS, no-findings PASS, edge-cases 10 errores; con `--estate` (Fase 6): sample PASS, edge-cases 13.
3. `cd frontend && npm run build` → éxito.
4. Raíz: `python -m pytest backend/tests/test_pipeline.py -v` → 2 passed (backend no tocado; AGENTS.md §5).

**8.2 Navegador** (skill `run` / Browser preview, `npm run dev` en :3000):
- [ ] `/` carga; CTAs → `/investigate` (estado vacío "Open a forensic case file").
- [ ] `/investigate/simulation` con banner deprecado y funcionando.
- [ ] **Sample**: cintillo `#7` · `38` · `$18.45 MXN` · `14.2s` · `REPRODUCIBLE (SEED 7)`; cost by role empieza por `challenger`.
- [ ] Resumen: `2` · `PROBABLE` + `1 proven · 1 probable` · `$156,600.00 MXN` · `4`.
- [ ] F1: `RFC:AAAA010101AA1` mono; `[data-scheme-type="phantom_vendor"]` existe; regla `SAT — Article 69-B, Código Fiscal de la Federación` + `Cited as:`; `$139,200.00 MXN`; `PROVEN`; diagrama "supplied by the run"; 4 pasos; clic en chip `EX-03` salta y resalta la fila; 6 exhibits; `invoices` `$0.00 MXN (0.00%)` `RECONCILED (≤ 2% VARIANCE)`.
- [ ] F2: `RFC:BBBB020202BB2` y `EMP:0001`; diagrama "generated from money_trail steps" con nodos marcados; "Reported by the run" `bank_txns`; `PROBABLE`; careo de dos paneles.
- [ ] Leads: `EMP` → 1 fila; Closed by Validator → 1; Unclassified → 1 (`RFC:FFFF060606FF6`); Clear → 4.
- [ ] `Format check: PASS`; consola sin errores; Expand/Collapse all funcionan.
- [ ] Checks de export de la Fase 5 pasan; `read_network_requests` solo muestra localhost.
- [ ] **No findings**: `0` · `NO FINDINGS` · `$0.00 MXN` · `3`; "No findings were validated in this run."
- [ ] **Edge cases**: `10 error(s)` y los mismos paths/mensajes de B.2; `Invalid scheme type` + `EFOS_INVOICE_MILL`; `160 / 150 words` + `console.warn` `[case-file]`; "(supplied diagram failed to render)"; "Trail breaks here"; chip `EX-99` rojo; `NOT RECONCILED — VARIANCE EXCEEDS 2%` `11.11%`; F‑B sin money trail, `W_RULE_STATISTICAL`, `INVALID CONFIDENCE: certain`; `Company not reported`; Wall clock `Not reported`; `NON-DETERMINISTIC RUN`; leads `Unclassified`, `Invalid: auditor`, `No tool calls recorded`; `Not provided by this run.`
- [ ] Subir `case-file.sample.json` desde disco en el visor → chip `Local file:` y sin banner de sample; `.txt` → error.
- [ ] Checklist completo de la Fase 6 repetido.
- [ ] Viewport 375 px en ambas páginas: sin scroll horizontal del body; tablas/diagramas scrollean dentro.
- [ ] Pedir al usuario la prueba humana de `Ctrl+P` (fondo blanco, sin toolbar/filtros/chevrons, hallazgos expandidos, cada hallazgo inicia página, badges con color).

> ⛔ **CHECKPOINT FINAL** — Todo lo anterior marcado con resultado real en `doc/frontend/case-file-progress.md`; resumen al usuario con: qué quedó, desviaciones, lo que requiere backend (endpoints propuestos, producción real del JSON), y el aviso de que el copy de la landing aún menciona subir CSVs a la simulación (fuera de alcance).

---

## Apéndice A — `frontend/fixtures/case-file.sample.json` (EXACTO)

```json
{
  "_about": "Illustrative sample case file for UI development. Fictional entities; not a real audit and not output of the Polar auditor.",
  "seed": 7,
  "header": {
    "company": "Manufacturas del Norte Ejemplo SA de CV",
    "company_rfc": "MNE150301AB1",
    "audit_period": { "start": "2026-01-01", "end": "2026-06-30" }
  },
  "executive_summary": {
    "plain_narrative": "The audit of Manufacturas del Norte Ejemplo covering January to June 2026 found two cases of likely fraud worth $156,600.00 MXN in total. The company paid a vendor that the tax authority lists as an issuer of invoices for non-existent operations, and a purchasing manager received 30% of a vendor payment back into a personal account. Four other suspicious signals were investigated and closed with documentary evidence."
  },
  "entity_names": {
    "RFC:MNE150301AB1": "Manufacturas del Norte Ejemplo SA de CV",
    "RFC:AAAA010101AA1": "Servicios Integrales Ejemplo SA de CV",
    "RFC:BBBB020202BB2": "Mantenimiento Industrial Ejemplo SC",
    "EMP:0001": "Persona Ejemplo Uno",
    "RFC:CCCC030303CC3": "Logística Ejemplo Tres SA de CV",
    "EMP:0014": "Persona Ejemplo Catorce",
    "RFC:EEEE050505EE5": "Papelería Ejemplo Cinco SA de CV",
    "RFC:FFFF060606FF6": "Consultores Ejemplo Seis SC"
  },
  "findings": [
    {
      "finding_id": "F-01",
      "scheme_type": "phantom_vendor",
      "entities": ["RFC:AAAA010101AA1"],
      "rule_broken": "SAT Articulo 69-B, Codigo Fiscal de la Federacion",
      "rule_detail": {
        "code": "SAT_ART_69B",
        "authority": "SAT",
        "article": "Article 69-B, Código Fiscal de la Federación",
        "legal_text_citation": "Invoices issued by a taxpayer listed as definitivo under Article 69-B are presumed to cover non-existent operations and have no tax effect; the company deducted both invoices without evidence of materiality."
      },
      "narrative": "Between February and March 2026 the company paid $139,200.00 MXN to Servicios Integrales Ejemplo SA de CV for strategic consulting. The vendor's tax ID has been on the SAT blacklist of companies that issue invoices for non-existent operations since December 2025. The vendor was registered only 14 days before its first invoice, lists a residential address, and no purchase order or contract supports either invoice. Both invoices were paid in full by bank transfer within two weeks of issue.",
      "peso_amount": 139200.0,
      "confidence": "proven",
      "money_trail": [
        { "from": "RFC:AAAA010101AA1", "to": "RFC:MNE150301AB1", "amount": 92800.0, "date": "2026-02-03", "exhibit_id": "EX-01" },
        { "from": "RFC:MNE150301AB1", "to": "RFC:AAAA010101AA1", "amount": 92800.0, "date": "2026-02-17", "exhibit_id": "EX-03" },
        { "from": "RFC:AAAA010101AA1", "to": "RFC:MNE150301AB1", "amount": 46400.0, "date": "2026-03-02", "exhibit_id": "EX-02" },
        { "from": "RFC:MNE150301AB1", "to": "RFC:AAAA010101AA1", "amount": 46400.0, "date": "2026-03-16", "exhibit_id": "EX-04" }
      ],
      "mermaid_source": "flowchart LR\n  C[\"Manufacturas del Norte Ejemplo · RFC:MNE150301AB1\"]\n  V[\"Servicios Integrales Ejemplo · RFC:AAAA010101AA1\"]\n  V -->|\"Step 1 · Invoice INV-00101 · $92,800.00 · EX-01\"| C\n  C -->|\"Step 2 · SPEI BNK-00201 · $92,800.00 · EX-03\"| V\n  V -->|\"Step 3 · Invoice INV-00102 · $46,400.00 · EX-02\"| C\n  C -->|\"Step 4 · SPEI BNK-00202 · $46,400.00 · EX-04\"| V\n  classDef flagged fill:#F6E1DF,stroke:#8E1B1F,stroke-width:2px,color:#161B22\n  class V flagged",
      "exhibits": [
        { "exhibit_id": "EX-01", "source_table": "invoices", "record_id": "INV-00101", "amount": 92800.0, "note": "CFDI invoice from the vendor for strategic consulting with no matching purchase order." },
        { "exhibit_id": "EX-02", "source_table": "invoices", "record_id": "INV-00102", "amount": 46400.0, "note": "Second CFDI invoice from the vendor for the same unspecified consulting services." },
        { "exhibit_id": "EX-03", "source_table": "bank_txns", "record_id": "BNK-00201", "amount": 92800.0, "note": "SPEI transfer from the company to the vendor's CLABE settling INV-00101." },
        { "exhibit_id": "EX-04", "source_table": "bank_txns", "record_id": "BNK-00202", "amount": 46400.0, "note": "SPEI transfer from the company to the vendor's CLABE settling INV-00102." },
        { "exhibit_id": "EX-05", "source_table": "vendors", "record_id": "AAAA010101AA1", "note": "Vendor was registered on 2026-01-20, 14 days before its first invoice, with a residential address." },
        { "exhibit_id": "EX-06", "source_table": "efos_list", "record_id": "AAAA010101AA1", "note": "The vendor's RFC is on the SAT Article 69-B list with status definitivo since 2025-12-11." }
      ],
      "adversarial_review": {
        "reviewer_agent_role": "challenger",
        "challenger_argument": "The vendor delivered consulting services and both CFDI invoices are valid (status vigente), so the payments are legitimate expenses.",
        "why_finding_held": "A valid CFDI status does not prove materiality: the vendor is listed as definitivo on the Article 69-B list (EX-06), and no purchase order, contract, or deliverable exists for either invoice."
      }
    },
    {
      "finding_id": "F-02",
      "scheme_type": "kickback",
      "entities": ["RFC:BBBB020202BB2", "EMP:0001"],
      "rule_broken": "Codigo Penal Federal Articulo 388 (administracion fraudulenta)",
      "rule_detail": {
        "code": "CPF_ART_388",
        "authority": "Código Penal Federal",
        "article": "Article 388, Administración fraudulenta",
        "legal_text_citation": "A person entrusted with managing another's assets who harms them by altering the conditions of operations for personal gain; the purchasing manager approved the order and received 30% of its value back from the vendor."
      },
      "narrative": "In April 2026 the purchasing manager requested and personally approved a $58,000.00 MXN maintenance order with Mantenimiento Industrial Ejemplo SC. Two days after the vendor invoiced the company, the vendor transferred $17,400.00 MXN, exactly 30% of the invoice, to the manager's personal bank account. No loan, contract, or other business reason for that transfer exists in the company's records. The pattern matches a kickback: company money paid to a vendor is partly returned to the employee who approved the purchase.",
      "peso_amount": 17400.0,
      "confidence": "probable",
      "money_trail": [
        { "from": "RFC:MNE150301AB1", "to": "RFC:BBBB020202BB2", "amount": 58000.0, "date": "2026-04-10", "exhibit_id": "EX-02" },
        { "from": "RFC:BBBB020202BB2", "to": "EMP:0001", "amount": 17400.0, "date": "2026-04-12", "exhibit_id": "EX-03" }
      ],
      "exhibits": [
        { "exhibit_id": "EX-01", "source_table": "purchase_orders", "record_id": "PO-00301", "amount": 58000.0, "note": "Purchase order for maintenance services was both requested and approved by EMP:0001, bypassing segregation of duties." },
        { "exhibit_id": "EX-02", "source_table": "invoices", "record_id": "INV-00311", "amount": 58000.0, "note": "Vendor invoice for the same maintenance services, matching the purchase order amount." },
        { "exhibit_id": "EX-03", "source_table": "bank_txns", "record_id": "BNK-00402", "amount": 17400.0, "note": "SPEI transfer with reference PO-00301 from the vendor's CLABE to the employee's personal CLABE." },
        { "exhibit_id": "EX-04", "source_table": "employees", "record_id": "EMP:0001", "note": "The employee record lists bank CLABE 000000000000000501, the destination of transfer BNK-00402." },
        { "exhibit_id": "EX-05", "source_table": "vendors", "record_id": "BBBB020202BB2", "note": "The vendor's registered CLABE 000000000000000002 is the origin account of transfer BNK-00402." }
      ],
      "reconciliation": {
        "claimed_pesos": 17400.0,
        "exhibits_sum": 17400.0,
        "variance_percentage": 0.0,
        "matched_table": "bank_txns",
        "per_table_breakdown": [
          { "table": "purchase_orders", "subtotal": 58000.0 },
          { "table": "invoices", "subtotal": 58000.0 },
          { "table": "bank_txns", "subtotal": 17400.0 }
        ]
      },
      "adversarial_review": {
        "reviewer_agent_role": "challenger",
        "challenger_argument": "The transfer to the employee could be a personal loan repayment between acquaintances, unrelated to the purchase order.",
        "why_finding_held": "No loan agreement appears in contracts, the transfer references PO-00301, and its amount is exactly 30% of the invoice total. The finding stays probable because the company-to-vendor bank payment is not yet linked."
      }
    }
  ],
  "leads_not_pursued": [
    {
      "entity": "RFC:CCCC030303CC3",
      "signal": "Vendor invoice volume rose 400% quarter over quarter (invoice velocity detector).",
      "reason": "Contract CTR-00007 signed 2025-11-02 covers the expanded scope; all 12 invoices match approved purchase orders within limits and each was settled by SPEI to the vendor's registered CLABE.",
      "tool_calls_made": ["query_invoices", "query_contracts", "query_purchase_orders", "match_bank_txns"],
      "closed_by": "investigator",
      "closure_category": "materiality_verified"
    },
    {
      "entity": "EMP:0014",
      "signal": "Employee bank CLABE shares the bank prefix of vendor DDDD040404DD4 (employee-vendor CLABE linkage detector).",
      "reason": "Only the 3-digit bank institution prefix (012) matches; the full 18-digit CLABEs differ and no bank_txns record moves funds between the two accounts in the audit period.",
      "tool_calls_made": ["query_employees", "query_vendors", "trace_bank_txns"],
      "closed_by": "challenger",
      "closure_category": "no_bank_correlation"
    },
    {
      "entity": "RFC:EEEE050505EE5",
      "signal": "Two invoices of $49,900.00 within 3 days, just under the $50,000.00 approval limit (threshold splitting detector).",
      "reason": "Invoice INV-00341 was cancelled (status cancelado) and reissued as INV-00342 with a corrected concepto; a single payment BNK-00410 of $49,900.00 settled it.",
      "tool_calls_made": ["query_invoices", "query_purchase_orders", "match_bank_txns"],
      "closed_by": "validator",
      "closure_category": "administrative_error"
    },
    {
      "entity": "RFC:FFFF060606FF6",
      "signal": "Vendor registered 20 days before its first invoice (new vendor detector).",
      "reason": "Purchase order PO-00288 and contract CTR-00031 predate the first invoice, and the delivery acceptance in ledger entry 5521 was approved by the plant controller.",
      "tool_calls_made": ["query_vendors", "query_purchase_orders", "query_contracts", "query_ledger"],
      "closed_by": "investigator"
    }
  ],
  "run_metadata": {
    "llm_calls": 38,
    "mxn_cost": 18.45,
    "wall_clock_seconds": 14.2,
    "cost_by_role": { "investigator": 11.2, "challenger": 5.1, "validator": 2.15 },
    "deterministic": true
  },
  "method_and_limits": {
    "architecture_summary": "Deterministic detectors scan the estate for known risk signals. An investigator agent examines each lead with read-only database tools, a challenger agent argues the defense, and a deterministic validator rejects any finding whose cited records do not exist or whose amount does not reconcile within 2%.",
    "out_of_scope": [
      "Payroll records beyond the employees table.",
      "CFDI XML signatures; only invoice table fields were examined.",
      "Transactions outside the audit period 2026-01-01 to 2026-06-30."
    ],
    "undetectable_fraud_types": [
      "Cash bribes paid outside the banking system.",
      "Collusion documented only in email, messaging, or verbal agreements.",
      "Kickbacks routed through accounts not registered in vendors or employees."
    ],
    "reproducibility_steps": [
      "Generate the estate with seed 7 using the project seeder.",
      "Run the auditor against the estate path with network access disabled.",
      "Validate the output: python validate_format.py --submission submission.json --estate estate.db",
      "Open the exported case file; the same seed yields an identical file."
    ]
  }
}
```

## Apéndice B — Otros fixtures de expediente

**B.1 `case-file.no-findings.json`** (debe PASAR): misma estructura que A con `seed: 21`; `header.audit_period` `2026-07-01` → `2026-12-31`; `executive_summary.plain_narrative`: `"The audit of Manufacturas del Norte Ejemplo covering July to December 2026 made no accusation. Three suspicious signals were investigated and each was closed with documentary evidence, listed in section 4."`; `findings: []`; `leads_not_pursued` = los 3 primeros leads de A; `run_metadata`: `llm_calls 21`, `mxn_cost 9.8`, `wall_clock_seconds 8.6`, `cost_by_role {}`, `deterministic true`; `entity_names` solo con `RFC:MNE150301AB1` y las entidades de esos 3 leads; `method_and_limits` igual que A cambiando el periodo a `2026-07-01 to 2026-12-31` y la semilla a `21`.

**B.2 `case-file.edge-cases.json`** (debe FALLAR; contenido EXACTO):
- `seed: 13`. Sin `header`, `executive_summary`, `entity_names`, `method_and_limits`.
- `findings[0]`: `finding_id "F-A"`, `scheme_type "EFOS_INVOICE_MILL"`, `entities ["AAAA010101AA1"]`, `rule_broken "SAT Articulo 69-B"`, `peso_amount 100000.0`, `confidence "proven"`, `mermaid_source "flowchart LR\n  A -->"`; `narrative` = la oración `The vendor invoiced services that were never delivered.` (8 palabras) repetida **20 veces** separada por un espacio (160 palabras); `money_trail`: `{from "RFC:MNE150301AB1", to "RFC:AAAA010101AA1", amount 90000.0, date "2026-02-01", exhibit_id "EX-01"}`, `{from "RFC:ZZZZ999999ZZ9", to "EMP:0099", amount 90000.0, date "2026-02-05", exhibit_id "EX-99"}`; `exhibits` (solo 2): `{EX-01, invoices, INV-09001, amount 90000.0, note "Invoice for services with no delivery evidence."}`, `{EX-02, bank_txns, BNK-09001, amount 90000.0, note "Payment settling INV-09001."}`.
- `findings[1]`: `finding_id "F-B"`, `scheme_type "threshold_splitting"`, `entities ["RFC:EEEE050505EE5"]`, `narrative "Two invoices were issued three days apart, each just under the approval limit."`, `rule_broken "Statistical outlier: invoice amounts 3.2 standard deviations above the vendor mean"`, `peso_amount 99800.0`, `confidence "certain"`, **sin** `money_trail`; `exhibits`: `{EX-01, invoices, INV-00341, amount 49900.0, note "First invoice of $49,900.00."}`, `{EX-02, invoices, INV-00342, amount 49900.0, note "Second invoice of $49,900.00 three days later."}`, `{EX-03, vendors, EEEE050505EE5, note "Vendor master record."}`.
- `leads_not_pursued`:
  0. `{entity "RFC:CCCC030303CC3", signal "Invoice velocity detector.", reason "insufficient evidence", tool_calls_made []}`
  1. `{entity "EMP:0014", signal "CLABE linkage detector.", reason "Full 18-digit CLABEs differ and no transfers link the accounts.", tool_calls_made ["query_employees"], closed_by "auditor", closure_category "no_bank_correlation"}`
  2. `{entity "RFC:FFFF060606FF6", signal "", reason "Purchase order PO-00288 predates the first invoice by 30 days.", tool_calls_made ["query_purchase_orders"], closed_by "investigator", closure_category "misc_reason"}`
- `run_metadata`: `{llm_calls 12, mxn_cost 4.5, deterministic false}` (sin `wall_clock_seconds`).

Salida esperada de `validate_format.py` (10 errores, en orden):
```text
findings[0].scheme_type must be one of ['kickback', 'phantom_vendor', 'revenue_inflation', 'round_tripping', 'threshold_splitting'], got 'EFOS_INVOICE_MILL'
findings[0].entities: 'AAAA010101AA1' is missing a type prefix (expected e.g. 'RFC:...' or 'EMP:...')
findings[0].narrative is 160 words, maximum is 150
findings[0].exhibits must have at least 3 entries, got 2
findings[0].money_trail[1].exhibit_id 'EX-99' does not match any exhibit in this finding
findings[1].confidence must be one of ['probable', 'proven'], got 'certain'
findings[1].money_trail is absent - a rendered money trail is required for full Clarity credit
leads_not_pursued[1].closed_by must be one of ['challenger', 'investigator', 'validator'], got 'auditor'
leads_not_pursued[2]: 'signal' is missing or empty
run_metadata: missing required key 'wall_clock_seconds'
```
Con `--estate` del sample estate se agregan 3: `findings[0].exhibits[0]: invoices.INV-09001 does not exist…`, `findings[0].exhibits[1]: bank_txns.BNK-09001 does not exist…`, `findings[0]: no exhibit cites an amount-bearing table…` (total 13). Sin estate, en navegador: F‑A `invoices` (empata con `bank_txns`, gana la primera), Δ `$10,000.00 MXN (11.11%)`, `NOT RECONCILED`; F‑B `invoices` exacto → `RECONCILED`.

## Apéndice C — Plantilla Markdown (EXACTA)

`{...}` = valor; líneas que empiezan con `[si ...]` solo se emiten cuando aplica (sin el prefijo). Sin líneas en blanco dobles.
Nulos en celdas → `Not reported`. `{deterministicText}` = `Yes — reproducible with seed {seed}` / `No` / `Not reported`.
`**Status:**` emite exactamente uno de los tres textos (en la plantilla separados por ` | ` solo como alternativas).

~~~~markdown
# Forensic Case File — {company | "Company not reported"}

[si isSample] > Sample data — illustrative, fictional entities. Not a real audit.

## 1. Header

| Field | Value |
|---|---|
| Company | {company}[si rfc] (RFC {company_rfc}) |
| Audit period | {start} to {end} |
| Estate seed | {seed} |
| LLM calls | {formatInteger} |
| MXN cost | {formatPesos} |
| Wall-clock seconds | {formatSeconds} |
| Deterministic | {deterministicText} |
[si cost_by_role] | Cost by role | {key formatPesos} · ... (orden alfabético) |

## 2. Executive summary

{summary.narrative}

| | |
|---|---|
| Findings | {count} ({proven} proven, {probable} probable) |
| Total exposure | {formatPesos(total)} |
| Leads investigated and closed | {closedLeadsCount} |

## 3. Findings

[si 0 hallazgos] No findings were validated in this run.

### Finding {n} — {entity ids unidos con ", "} · {scheme label} (`{scheme_type}`)

[si hay nombres] **Entities:** {id} — {name}; {id} — {name}

**Rule broken:** {rule.title}
[si citation] > {citation}
[si rule_detail] Cited as: `{rule_broken}`

**Amount:** {formatPesos(peso_amount)} · **Confidence:** {confidence}

#### What happened

{narrative}

#### Money trail

```mermaid
{renderedSource}
```

| Step | Date | From | To | Amount | Exhibit |
|---|---|---|---|---|---|
| 1 | {date} | {from} | {to} | {formatPesos} | {exhibit_id} |
[si trail null] No money trail was supplied for this finding.

#### Exhibits

| Exhibit ID | Source table | Record ID | What it proves |
|---|---|---|---|
| {exhibit_id} | {source_table} | {record_id} | {note} |

#### Reconciliation

| | Amount |
|---|---|
| Claimed amount | {formatPesos} |
| Sum of cited exhibits (best-matching table: `{table}`) | {formatPesos} |
| Variance (Δ) | {formatPesos(delta)} ({pct}%) |

**Status:** RECONCILED (≤ 2% variance) | NOT RECONCILED — variance exceeds 2% | NOT VERIFIABLE — no exhibit amounts supplied
Per-table subtotals: `invoices` {formatPesos} · `bank_txns` {formatPesos}
[si estateChecked] Amounts verified against the loaded data estate.

#### Adversarial review

**Defense position (challenger · {reviewer_agent_role}):** {challenger_argument}
**Why the finding held:** {why_finding_held}
[si no hay] No adversarial review was recorded for this finding.

## 4. Leads investigated and closed

| Entity | Signal | Reason closed | Tools called | Closed by |
|---|---|---|---|---|
| {entity}[si name] ({name}) | {signal} | {reason} | {n}: {tool, tool} | {closed_by label o "Not recorded"} |
[si 0 leads] No leads were closed in this run.

## 5. Method and limits

### Architecture
{architecture_summary o "Not provided by this run."}

### Out of scope for this run
- {item}

### What this system cannot detect
- {item}

### Reproducibility
1. {step}
~~~~

## Apéndice D — CSS a agregar en `app/globals.css`

```css
.case-workspace :is(button, a, summary, input, select, [tabindex]):focus-visible { outline: 2px solid #79c7f5; outline-offset: 3px; }
.case-paper :is(button, a, summary, input, select, [tabindex]):focus-visible { outline-color: #1c4f8c; }
.case-paper tr:target { scroll-margin-top: 6rem; }

@media print {
  @page { margin: 16mm 14mm; }
  html, body { background: #ffffff !important; }
  .case-workspace { background: #ffffff !important; min-height: 0 !important; }
  .case-workspace * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  [data-print="hide"] { display: none !important; }
  /* UA stylesheet hides [hidden]; `revert` would keep it hidden, so set explicit displays */
  [data-collapsible-body][hidden] { display: block !important; }
  tr[data-filterable-row][hidden] { display: table-row !important; }
  .case-paper { max-width: none !important; margin: 0 !important; padding: 0 !important; box-shadow: none !important; border: 0 !important; border-radius: 0 !important; }
  .case-paper section[data-finding-section] + section[data-finding-section] { break-before: page; }
  .case-avoid-break, .case-paper tr, .case-paper figure { break-inside: avoid; }
  .case-paper thead { display: table-header-group; }
  .case-scroll { overflow: visible !important; }
  .case-paper a { color: inherit; text-decoration: none; }
}
```
(`@page` sin `size`: el diálogo elige A4 o Carta; el ancho útil mínimo ≈ 178 mm cabe en ambos.)

## Apéndice E — `tailwind.config.js`

- `content`: agregar `"./hooks/**/*.{ts,tsx}"` y `"./lib/**/*.{ts,tsx}"`.
- `theme.extend.colors`: agregar sin tocar lo existente:
```js
paper: { DEFAULT: "#FBFAF7", raised: "#F2EFE8", border: "#D8D2C6", ink: "#161B22", muted: "#5A6270" },
evidence: {
  proven: "#8E1B1F", "proven-soft": "#F6E1DF",
  probable: "#9A5A06", "probable-soft": "#FBEBD2",
  reconciled: "#1E6A3B", "reconciled-soft": "#DFF0E3",
  held: "#1C4F8C", "held-soft": "#E2EBF6",
  neutral: "#4B5563", "neutral-soft": "#ECEAE5",
},
```
`font-serif` (stack por defecto, sin webfonts) para títulos/narrativas; `font-mono` para IDs, montos y telemetría.

## Apéndice F — Muestras de estate en `public/samples/estate/` (EXACTO)

**F.1 `vendors.csv`**
```csv
rfc,legal_name,registered_date,address,bank_clabe,category,contact_email
AAAA010101AA1,Servicios Integrales Ejemplo SA de CV,2026-01-20,"Calle Ejemplo 14, Col. Centro, Monterrey",000000000000000001,Consultoria,contacto@serviciosejemplo.mx
BBBB020202BB2,Mantenimiento Industrial Ejemplo SC,2024-06-30,"Av. Ejemplo 200, Monterrey",000000000000000002,Mantenimiento,dos@example.mx
CCCC030303CC3,Logística Ejemplo Tres SA de CV,2023-03-15,"Blvd. Ejemplo 300, Apodaca",012000000000000003,Logistica,tres@example.mx
DDDD040404DD4,Suministros Ejemplo Cuatro SA de CV,2022-09-01,"Calle Ejemplo 400, Monterrey",012000000000000004,Suministros,cuatro@example.mx
EEEE050505EE5,Papelería Ejemplo Cinco SA de CV,2021-05-10,"Av. Ejemplo 500, San Nicolas",000000000000000005,Papeleria,cinco@example.mx
FFFF060606FF6,Consultores Ejemplo Seis SC,2026-01-10,"Calle Ejemplo 600, Monterrey",000000000000000006,Consultoria,seis@example.mx
```

**F.2 `estate.partial.json`**
```json
{
  "invoices": [
    { "uuid": "INV-00311", "issuer_rfc": "BBBB020202BB2", "receiver_rfc": "MNE150301AB1", "issue_date": "2026-04-10", "subtotal": 50000.0, "iva": 8000.0, "total": 58000.0, "concepto_text": "Mantenimiento preventivo de línea 2", "uso_cfdi": "G03", "forma_pago": "03", "metodo_pago": "PUE", "status": "vigente" },
    { "uuid": "INV-00341", "issuer_rfc": "EEEE050505EE5", "receiver_rfc": "MNE150301AB1", "issue_date": "2026-05-04", "subtotal": 43017.24, "iva": 6882.76, "total": 49900.0, "concepto_text": "Papelería y consumibles", "uso_cfdi": "G03", "forma_pago": "03", "metodo_pago": "PUE", "status": "cancelado" },
    { "uuid": "INV-00342", "issuer_rfc": "EEEE050505EE5", "receiver_rfc": "MNE150301AB1", "issue_date": "2026-05-06", "subtotal": 43017.24, "iva": 6882.76, "total": 49900.0, "concepto_text": "Papelería y consumibles (corrección)", "uso_cfdi": "G03", "forma_pago": "03", "metodo_pago": "PUE", "status": "vigente" }
  ],
  "bank_txns": [
    { "txn_id": "BNK-00201", "date": "2026-02-17", "from_clabe": "000000000000000099", "to_clabe": "000000000000000001", "amount": 92800.0, "reference": "Pago factura INV-00101", "channel": "SPEI" },
    { "txn_id": "BNK-00202", "date": "2026-03-16", "from_clabe": "000000000000000099", "to_clabe": "000000000000000001", "amount": 46400.0, "reference": "Pago factura INV-00102", "channel": "SPEI" },
    { "txn_id": "BNK-00402", "date": "2026-04-12", "from_clabe": "000000000000000002", "to_clabe": "000000000000000501", "amount": 17400.0, "reference": "PO-00301", "channel": "SPEI" },
    { "txn_id": "BNK-00410", "date": "2026-05-08", "from_clabe": "000000000000000099", "to_clabe": "000000000000000005", "amount": 49900.0, "reference": "Pago factura INV-00342", "channel": "SPEI" }
  ],
  "purchase_orders": [
    { "po_id": "PO-00301", "vendor_rfc": "BBBB020202BB2", "date": "2026-04-08", "amount": 58000.0, "requester": "EMP:0001", "approver": "EMP:0001", "description": "Mantenimiento preventivo de línea 2" },
    { "po_id": "PO-00288", "vendor_rfc": "FFFF060606FF6", "date": "2026-01-28", "amount": 35000.0, "requester": "EMP:0022", "approver": "EMP:0003", "description": "Diagnóstico de procesos" }
  ],
  "contracts": [
    { "contract_id": "CTR-00007", "vendor_rfc": "CCCC030303CC3", "start_date": "2025-11-02", "value": 1200000.0, "scope_text": "Servicios de transporte y logística, alcance ampliado 2026" },
    { "contract_id": "CTR-00031", "vendor_rfc": "FFFF060606FF6", "start_date": "2026-01-25", "value": 35000.0, "scope_text": "Diagnóstico de procesos de planta" }
  ],
  "employees": [
    { "emp_id": "EMP:0001", "name": "Persona Ejemplo Uno", "role": "Gerente de Compras", "bank_clabe": "000000000000000501", "hire_date": "2021-03-01" },
    { "emp_id": "EMP:0014", "name": "Persona Ejemplo Catorce", "role": "Analista de Almacén", "bank_clabe": "012000000000000514", "hire_date": "2023-08-15" }
  ],
  "efos_list": [
    { "rfc": "AAAA010101AA1", "legal_name": "Servicios Integrales Ejemplo SA de CV", "status": "definitivo", "publication_date": "2025-12-11" }
  ],
  "ledger": [
    { "entry_id": 5520, "date": "2026-02-03", "account_code": "5000", "account_name": "Gastos operativos", "debit": 92800.0, "credit": 0.0, "description": "Registro factura", "invoice_uuid": "INV-00101", "cost_center": "CC-100 Produccion", "approver": null },
    { "entry_id": 5521, "date": "2026-02-20", "account_code": "5000", "account_name": "Gastos operativos", "debit": 35000.0, "credit": 0.0, "description": "Aceptación de entregables diagnóstico", "invoice_uuid": null, "cost_center": "CC-100 Produccion", "approver": "Contralor de planta" }
  ]
}
```

## Apéndice G — CFDI 4.0 de muestra

**G.1 `cfdi-INV-00101.xml`** (EXACTO)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0" Serie="A" Folio="101" Fecha="2026-02-03T10:00:00" FormaPago="03" SubTotal="80000.00" Moneda="MXN" Total="92800.00" TipoDeComprobante="I" Exportacion="01" MetodoPago="PUE" LugarExpedicion="64000">
  <cfdi:Emisor Rfc="AAAA010101AA1" Nombre="SERVICIOS INTEGRALES EJEMPLO" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="MNE150301AB1" Nombre="MANUFACTURAS DEL NORTE EJEMPLO" DomicilioFiscalReceptor="64000" RegimenFiscalReceptor="601" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Consultoría estratégica" ValorUnitario="80000.00" Importe="80000.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados><cfdi:Traslado Base="80000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="12800.00"/></cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="12800.00"><cfdi:Traslados><cfdi:Traslado Base="80000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="12800.00"/></cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital Version="1.1" UUID="INV-00101" FechaTimbrado="2026-02-03T10:05:00" RfcProvCertif="SAT970701NN3" NoCertificadoSAT="00000000000000000000"/></cfdi:Complemento>
</cfdi:Comprobante>
```

**G.2 `cfdi-INV-00102.xml`**: idéntico a G.1 salvo `Folio="102"`, `Fecha="2026-03-02T10:00:00"`, `SubTotal="40000.00"`, `Total="46400.00"`, `Descripcion="Consultoría estratégica, segunda etapa"`, `ValorUnitario`/`Importe` del concepto `40000.00`, `Base="40000.00"` e `Importe="6400.00"` en ambos `Traslado`, `TotalImpuestosTrasladados="6400.00"`, `UUID="INV-00102"`, `FechaTimbrado="2026-03-02T10:05:00"`.

Resultado esperado de cargar F.1 + F.2 + G.1 + G.2: 24 filas, 0 errores, 2 warnings (`W_CFDI_STATUS_UNKNOWN`), y todos los exhibits del sample existen.

## Apéndice H — Plantilla `doc/frontend/case-file-progress.md`

```md
# Case File & Data Estate — Progress Ledger

Plan: doc/frontend/case-file-plan.md
Regla: una fase a la vez; no avanzar sin checkpoint completo.

| Fase | Estado | Checkpoint (resultado real) | Fecha |
|---|---|---|---|
| 0 Preflight | [ ] | | |
| 1 Lógica pura | [ ] | | |
| 2 Fixtures expediente | [ ] | | |
| 3 Rutas, sesión y carga | [ ] | | |
| 4 Secciones T1–T12 | [ ] | | |
| 5 Exportación T13 | [ ] | | |
| 6 Data estate (XML/DB/CSV/JSON) | [ ] | | |
| 7 Documentación | [ ] | | |
| 8 Verificación final | [ ] | | |

## Log
### Fase N — YYYY-MM-DD
- Archivos tocados:
- Comandos y resultado:
- Desviaciones del plan (y por qué):
- Pendientes / riesgos:

## Handoff (llenar si la sesión se corta)
- Última fase completa:
- Fase en curso y qué quedó hecho:
- Siguiente paso exacto:
```

---

## Riesgos / gotchas

| Riesgo | Mitigación |
|---|---|
| Sesión cortada a mitad (contexto/uso) | Checkpoints + registro de progreso + handoff (§1); cada fase deja el build verde |
| mermaid 12 requiere Node ≥ 22.12 | `11.17.2` exacto (D5) |
| Mermaid no concurrente; StrictMode duplica efectos | cola serializada + flag `cancelled` |
| Contenido colapsado/filtrado no sale en impresión/export | nunca desmontar; `hidden` + CSS print explícito + limpieza en export |
| `new Date("2026-03-16")` corre la fecha por zona horaria | fechas como string (D8) |
| `validate_format.py` en Windows falla con acentos | `python -X utf8` |
| `</script>` en el JSON embebido | `replace(/</g, "\\u003c")` |
| sql.js intenta resolver `fs` en el bundle cliente | fallback en `next.config.js` + import dinámico |
| WASM de sql.js desde CDN rompería offline | copiar a `public/sql-wasm.wasm` en `predev`/`prebuild` |
| `Impuestos` del concepto confundido con el del comprobante | leer solo hijos directos de `Comprobante` |
| CLABE numérica pierde ceros a la izquierda | warning `W_CLABE_NUMERIC` |
| Estate se pierde al recargar | aviso explícito en UI; export `.db`/`.json` |
| Clases Tailwind en `lib/` no generadas | globs de `content` |
| Lock `.next/trace` en Windows | detenerse y pedir ayuda |
| Copy de la landing aún habla de subir CSVs | fuera de alcance; avisar al final |
