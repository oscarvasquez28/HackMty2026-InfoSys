# Case File & Data Estate — Progress Ledger

Plan: doc/frontend/case-file-plan.md
Regla: una fase a la vez; no avanzar sin checkpoint completo.

| Fase | Estado | Checkpoint (resultado real) | Fecha |
|---|---|---|---|
| 0 Preflight | [x] | mermaid 11.17.2 exact; /lib/ anchored; tsc 0 errors | 2026-09-12 |
| 1 Lógica pura | [x] | tsc 0 errors; lib/caseFile/* has no Date.now/Math.random/new Date( | 2026-09-12 |
| 2 Fixtures expediente | [x] | sample PASS; no-findings PASS; edge-cases 10 errors exact match | 2026-09-12 |
| 3 Rutas, sesión y carga | [x] | tsc 0 errors; /investigate loads empty state + sample (seed 7, 2 findings, 4 leads) with no console errors; /investigate/simulation shows deprecated banner; / unchanged | 2026-09-12 |
| 4 Secciones T1–T12 | [x] | tsc 0 errors; npm run build OK (7 pages); sample/no-findings/edge-cases render correctly in browser, no console errors | 2026-09-12 |
| 5 Exportación T13 | [x] | tsc 0 errors; markdown deterministic (2 mermaid blocks, sections 1-5); HTML export clean (no hidden attrs, no script src, no external refs) even with UI collapsed/filtered; format-check chip toggles panel | 2026-09-12 |
| 6 Data estate (XML/DB/CSV/JSON) | [x] | tsc 0 errors; npm run build OK (8 pages); sample estate 24 rows/0 err/2 warn; roundTripSqlite equal:true; validate_format.py --estate PASS (sample) / 13 errors (edge-cases); estate persists across /investigate ↔ /investigate/data nav | 2026-09-12 |
| 7 Documentación | [x] | 4 docs actualizados; rutas/archivos referenciados verificados con Glob; tsc 0 errors | 2026-09-12 |
| 8 Verificación final | [x] | tsc/build/validator OK; pytest backend no corrible en este entorno (falta venv, preexistente); resto del checklist de navegador verificado | 2026-09-12 |

## Log

### Fase 0 — 2026-09-12
- Archivos tocados: doc/frontend/case-file-plan.md (nuevo), doc/frontend/case-file-progress.md (nuevo)
- Comandos y resultado:
  - `git branch --show-current` → `dev-emiliano`
  - `git status --short` → limpio
  - `node -v` → `v20.16.0`
  - (pendiente) `npm install mermaid@11.17.2 --save-exact`
- Desviaciones del plan (y por qué): ninguna
- Pendientes / riesgos: confirmar `.gitignore` `/lib/` anclado; instalar mermaid exacto

### Fase 1 — 2026-09-12
- Archivos tocados: tailwind.config.js, lib/utils.ts, types/caseFile.ts (nuevo), types/estate.ts (nuevo),
  lib/caseFile/constants.ts, normalize.ts, validate.ts, derive.ts, mermaid.ts, toMarkdown.ts, download.ts, toHtml.ts (todos nuevos)
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → 2 errores iniciales (Blob BlobPart typing en download.ts; Map iteration sin downlevelIteration en mermaid.ts) → corregidos → 0 errores
  - `grep -rn "Date.now|Math.random|new Date(" lib/caseFile` → sin resultados (determinismo OK)
- Desviaciones del plan (y por qué):
  - `download.ts`: `new Blob([content as BlobPart], ...)` en vez de `new Blob([content], ...)` — el lib.dom.d.ts instalado no acepta `Uint8Array<ArrayBufferLike>` directo como `BlobPart` sin narrowing; cast explícito soluciona sin cambiar comportamiento.
  - `mermaid.ts`: `Array.from(nodeIds.entries())` en vez de iterar el Map directo con for-of — el tsconfig del proyecto no fija `target`, así que TS usa el default y la iteración directa de `Map.entries()` requiere `--downlevelIteration`. `Array.from` evita el problema sin tocar tsconfig.
- Pendientes / riesgos: ninguno bloqueante

### Fase 2 — 2026-09-12
- Archivos tocados: frontend/fixtures/case-file.sample.json, case-file.no-findings.json, case-file.edge-cases.json (nuevos)
- Comandos y resultado:
  - `python -X utf8 student-materials/forensic-auditor/validate_format.py --submission frontend/fixtures/case-file.sample.json` → PASS (exit 0)
  - idem `case-file.no-findings.json` → PASS (exit 0)
  - idem `case-file.edge-cases.json` → 10 format error(s) (exit 1), mensajes idénticos y en el mismo orden que el Apéndice B.2
  - `npx --no-install tsc --noEmit --incremental false` → 0 errores
- Desviaciones del plan (y por qué): ninguna
- Pendientes / riesgos: ninguno

### Fase 3 — 2026-09-12
- Archivos tocados:
  - hooks/useAgentSimulation.ts, components/InvestigationDashboard.tsx (JSDoc @deprecated agregado, sin más cambios)
  - app/investigate/simulation/page.tsx (nuevo, banner deprecado)
  - app/investigate/page.tsx (reescrito → CaseFileWorkspace)
  - app/investigate/layout.tsx (nuevo → InvestigateSessionProvider)
  - app/investigate/data/ (directorio vacío creado, page.tsx pendiente de Fase 6)
  - hooks/useCaseFileSource.ts (nuevo)
  - .env.example (NEXT_PUBLIC_CASE_FILE_API=disabled)
  - components/investigate/InvestigateSessionProvider.tsx, InvestigateAppBar.tsx (nuevos)
  - components/case-file/CaseFileUiContext.tsx, Collapsible.tsx, IssueNotice.tsx, ValidationPanel.tsx,
    CaseFileSourcePanel.tsx, ExportToolbar.tsx (placeholder), CaseFileDocument.tsx (placeholder Fase 4),
    CaseFileWorkspace.tsx (nuevos)
  - .claude/launch.json (nuevo, config del dev server para Browser preview)
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → 0 errores
  - Browser preview (`npm run dev` vía skill run) en :3000:
    - `/investigate` → panel de carga vacío, sin errores de consola
    - clic "Open sample case" → `document.title` cambia a `case-file-seed-7`, placeholder muestra "Seed 7 · 2 finding(s) · 4 lead(s) closed", sin errores
    - `/investigate/simulation` → banner deprecado visible + simulación funcional, sin errores
    - `/` sin cambios
- Desviaciones del plan (y por qué):
  - `ExportToolbar.tsx` es un placeholder con solo Expand all/Collapse all (según plan); el toggle de
    "Format check" se puso temporalmente como botón suelto en `CaseFileWorkspace.tsx` (fuera de
    ExportToolbar) para no bloquear el checkpoint — Fase 5 lo absorbe dentro del chip real del toolbar.
  - `CaseFileDocument.tsx` es un stub mínimo (según plan, T1–T12 llegan en Fase 4).
  - Se creó `.claude/launch.json` (no estaba en el árbol de archivos del plan) para poder usar el
    Browser preview del skill `run` contra `frontend` desde la raíz del repo.
- Pendientes / riesgos: ninguno bloqueante

### Fase 4 — 2026-09-12
- Archivos tocados (todos nuevos salvo indicado):
  components/case-file/ConfidenceBadge.tsx, CaseHeader.tsx, ExecutiveSummary.tsx, EntityId.tsx,
  SchemeTypeBadge.tsx, RuleBrokenCallout.tsx, AmountConfidence.tsx, FindingNarrative.tsx,
  MermaidDiagram.tsx, MoneyTrailTimeline.tsx, MoneyTrail.tsx, ExhibitsTable.tsx, ReconciliationBlock.tsx,
  AdversarialReview.tsx, FindingSection.tsx, LeadsNotPursued.tsx, MethodAndLimits.tsx,
  CaseFileDocument.tsx (reemplazado, ya no es el stub de Fase 3), CaseFileWorkspace.tsx (pasa `issues` a
  CaseFileDocument)
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → 1 error inicial (narrowing de `source_table` en
    ExhibitsTable.tsx) → corregido → 0 errores
  - `npm run build` → falló primero por el lock conocido de `.next/trace` (dev server propio corriendo);
    detuve mi propio `preview_start`, reintenté → build exitoso, 7 páginas generadas; reinicié el dev server
  - Browser preview, fixture **sample**: cintillo `#7 · 38 · $18.45 MXN · 14.2s · REPRODUCIBLE (SEED 7)`;
    resumen `2 · PROBABLE (1 proven · 1 probable) · $156,600.00 MXN · 4`; F1 diagrama "supplied by the run"
    con SVG renderizado, timeline 4 pasos, reconciliación `invoices` RECONCILED; F2 diagrama "generated
    from money_trail steps" con nodos marcados, reconciliación backend `bank_txns` RECONCILED; leads con
    filtros de texto/closed_by/category verificados vía JS (el filtro de texto funciona correctamente —
    una prueba manual con "EMP" pareció fallar pero era falso positivo: "Ejemplo" contiene la subcadena
    "emp"; con "EMP:" filtra a 1 fila correctamente); Method and limits colapsado; footer "Format check: PASS"
  - Fixture **no-findings**: `0 · NO FINDINGS · $0.00 MXN · 3`, sin errores de consola
  - Fixture **edge-cases**: sin crashear; "Company not reported", "Wall clock Not reported",
    "NON-DETERMINISTIC RUN", "Missing id prefix", "INVALID SCHEME TYPE" + `EFOS_INVOICE_MILL`,
    "160 / 150 words" + `console.warn [case-file]`, diagrama "(supplied diagram failed to render)",
    "Trail breaks here", `NOT RECONCILED — VARIANCE EXCEEDS 2%` `11.11%`, F-B sin money trail +
    `W_RULE_STATISTICAL` + `INVALID CONFIDENCE: certain`, leads "Unclassified", "Invalid: auditor",
    "No tool calls recorded"; footer "Format check: 10 error(s)"; sin errores de consola (solo los
    `console.warn` esperados)
- Desviaciones del plan (y por qué):
  - `ExhibitsTable.tsx`: se usa `isSourceTable(sourceTable)` inline en vez de una variable `validTable`
    booleana para indexar `AMOUNT_COLUMN`, porque TS no propaga el narrowing de un type-guard a través de
    una variable booleana intermedia cuando se usa para indexar un `Partial<Record<...>>`.
  - `MoneyTrail.tsx`: el texto de "Diagram source" en el `figcaption` lee `usedFallback` real desde
    `useCaseFileUi().diagrams[anchorId]` (estado runtime del render de Mermaid) en vez de inferirlo
    estáticamente de la sola presencia de `mermaidPrimary`, para reflejar correctamente el caso
    "(supplied diagram failed to render)" cuando el `mermaid_source` del run es inválido.
- Pendientes / riesgos: ninguno bloqueante

### Fase 5 — 2026-09-12
- Archivos tocados:
  - components/case-file/ExportToolbar.tsx (reescrito completo: chips fuente/format-check, Expand/Collapse,
    4 botones de export, `window.__caseFileDebug` movido aquí desde CaseFileWorkspace para usar
    `renderedSources` reales de `useCaseFileUi().diagrams`)
  - components/case-file/CaseFileWorkspace.tsx (retirado el botón temporal y el debug placeholder de Fase 3;
    ahora pasa `loaded/view/issues/showValidation/onToggleValidation` a ExportToolbar)
  - app/globals.css (agregado el bloque de impresión y focus-visible del Apéndice D)
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → 0 errores
  - Browser (sample, seed 7):
    - botones Print/HTML/Markdown/JSON habilitados una vez que `diagramsSettled` (~800ms tras cargar)
    - `__caseFileDebug.buildMarkdown()` llamado dos veces → idéntico (determinismo), 2 bloques ` ```mermaid `,
      secciones `## 1.`…`## 5.` en orden
    - `__caseFileDebug.buildHtml()` → 16 `<svg` (mermaid + iconos), `id="case-file-data"` presente, sin
      `data-collapsible-body hidden`, sin `<script src`, sin refs externas (`src|href="https?:` / `url(https?:`)
    - Con "Collapse all" + filtro de leads a "EMP:" activos en pantalla (0 secciones visibles, 1 fila visible):
      el HTML exportado sigue sin atributos `hidden` en `data-collapsible-body` ni en `data-filterable-row`
      (los conteos de "data-finding-section"/"data-filterable-row" en el HTML incluyen las apariciones del
      propio selector CSS de impresión inlined, no son un bug)
    - Chip "Format check: PASS" abre/cierra `ValidationPanel` correctamente
- Desviaciones del plan (y por qué):
  - `window.__caseFileDebug` vive en `ExportToolbar.tsx` (dentro de `CaseFileUiProvider`) en vez de
    `CaseFileWorkspace.tsx`, porque necesita `renderedSources` reales del contexto de diagramas
    (`useCaseFileUi().diagrams`), al que `CaseFileWorkspace` (el provider, no un consumidor) no tiene acceso
    directo. Mismo contrato público (`buildMarkdown`, `buildHtml`, `issues`).
- Pendientes / riesgos: la prueba humana de `Ctrl+P` (fondo blanco, sin toolbar, hallazgos expandidos,
  salto de página por hallazgo) queda para el checkpoint final (Fase 8), que pide pedírsela al usuario.

### Fase 6 — 2026-09-12
- Archivos tocados:
  - `frontend/package.json` (sql.js@1.14.2, papaparse@5.7.0, @types/sql.js@1.4.11, @types/papaparse@5.5.2
    exactos; scripts `copy:sqlwasm`/`predev`/`prebuild`)
  - `frontend/next.config.js` (webpack fallback fs/path/crypto para cliente)
  - `.gitignore` (raíz): **`data` → `/data`** (anclado a raíz) — el patrón bare `data` swallowaba
    `frontend/app/investigate/data/`, igual que el gotcha histórico de `/lib/`; se agregó también
    `frontend/public/sql-wasm.wasm` (binario generado, no se versiona)
  - `frontend/types/estate.ts` (agregado `ParsedEstateFile`)
  - `frontend/lib/estate/{schema,coerce,parseCsv,parseJson,parseXml,sqlite,ingest,validateEstate,estateCheck}.ts` (nuevos)
  - `frontend/lib/caseFile/derive.ts` (extendido: `buildCaseFileView(document, estate?)`, `exhibitEstate`,
    reconciliación con origen `estate` con prioridad sobre `backend`/`derived`)
  - `frontend/hooks/useEstate.ts` (nuevo)
  - `frontend/components/investigate/InvestigateSessionProvider.tsx` (agrega `estate`)
  - `frontend/components/investigate/InvestigateAppBar.tsx` (tab "Data estate")
  - `frontend/components/estate/{EstateUploadZone,EstateFileList,EstateTableSummary,EstateTablePreview,
    EstateIssuesPanel,EstateExportBar,DataEstateWorkspace}.tsx` (nuevos)
  - `frontend/app/investigate/data/page.tsx` (nuevo)
  - `frontend/components/case-file/CaseFileWorkspace.tsx` (view/issues incluyen estate cuando `hasEstate`)
  - `frontend/components/case-file/ExportToolbar.tsx` (prop `estateChecked`, chip "Estate check")
  - `frontend/components/case-file/CaseFileSourcePanel.tsx` (nota de estate cargado)
  - `frontend/components/case-file/ExhibitsTable.tsx` (badge "in estate"/"not in estate" + `<details>` con el registro)
  - `frontend/.env.example` (`NEXT_PUBLIC_ESTATE_UPLOAD_API=disabled`)
  - `frontend/public/samples/estate/{vendors.csv,estate.partial.json,cfdi-INV-00101.xml,cfdi-INV-00102.xml}` (nuevos)
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → varios errores de narrowing/iteración
    (mismo patrón de Fase 1) → corregidos → 0 errores
  - `npm run build` (deteniendo mi propio dev server primero) → éxito, 8 páginas incluyendo `/investigate/data`
  - Browser, "Load sample estate": `__estateDebug.summary()` → filas exactas
    `{vendors:6, invoices:5, ledger:2, bank_txns:4, purchase_orders:2, contracts:2, employees:2, efos_list:1}`
    (24), **0 errores, 2 warnings** (`W_CFDI_STATUS_UNKNOWN` ×2) — coincide exacto con el checkpoint
  - `__estateDebug.roundTripSqlite()` → `{equal: true}`
  - `__estateDebug.ingestText("export.csv", <vendors.csv>)` → `CSV → vendors`; `ingestText("data.csv","foo,bar\n1,2")`
    → `CSV → table not detected` (needs_table); el select "Import as table" en la UI lo asignó a `vendors`
    correctamente (`CSV → vendors (assigned)`)
  - `estate.db` exportado (vía `exportSqliteBase64` decodificado a archivo) validado con
    `python -X utf8 validate_format.py --submission case-file.sample.json --estate estate.db` → **PASS**
    (`estate check: yes`); con `case-file.edge-cases.json --estate estate.db` → **13 errores** (los 10
    estructurales + 3 de estate: `INV-09001`/`BNK-09001` no existen + "no exhibit cites an amount-bearing
    table"), exactamente lo previsto
  - Navegando de `/investigate/data` a `/investigate` **sin recargar** (nav cliente, estado persiste en
    `InvestigateSessionProvider`): sample → chip `Estate check: PASS`, 11/11 exhibits `in estate`, ambas
    reconciliaciones "Computed in the browser from the loaded data estate."; edge-cases → `Estate check: 3 error(s)`
  - Subir un `.txt` → fila `Failed` con "Unsupported file type. Use .db, .sqlite, .csv, .json or .xml.";
    recargar `/investigate/data` → estate vacío (0 filas en las 8 tablas, "No files loaded yet.")
  - Sin errores de consola en ningún paso
- Desviaciones del plan (y por qué):
  - **`.gitignore` raíz**: se corrigió `data` → `/data` (bug real preexistente que bloqueaba
    `frontend/app/investigate/data/`, no introducido por este plan pero descubierto al crearlo). Se
    documentará en AGENTS.md §6 en la Fase 7 junto al gotcha histórico de `/lib/`.
  - **`hooks/useEstate.ts`**: `issues` expuesto = `files.flatMap(f => f.fileIssues)` **+**
    `buildEstate(files).issues` (el plan lo pedía así en 6.7 pero mi primera implementación solo
    exponía el segundo conjunto; corregido tras notar que `__estateDebug.summary()` reportaba 0
    warnings en vez de las 2 esperadas de `W_CFDI_STATUS_UNKNOWN`).
  - `WASM_SOURCE` confirmado como `sql-wasm-browser.wasm` (export "browser" del package.json de sql.js;
    Next.js bundlea esa variante para el cliente) — validado end-to-end (carga, export, round-trip).
- Pendientes / riesgos: ninguno bloqueante. El archivo de prueba `estate.db` queda en el scratchpad de
  la sesión (no en el repo).

### Fase 7 — 2026-09-12
- Archivos tocados: doc/frontend/README.md (entry points, árbol de archivos, matriz de componentes,
  nuevas §10 Case File Viewer and Export Engine y §11 Data Estate Ingestion, gotchas §8.6/§8.7, config
  reference), doc/architecture/README.md (nueva §4.6 Case File JSON Contract), AGENTS.md (§6 gotchas
  reescrito — quitado el gotcha stale de `frontend/lib/`, agregados los de `.gitignore`/mermaid-Node/
  sql.js-WASM/`python -X utf8`; §7 reescrito con los 3 entry points), doc/index.md (filas del dispatcher
  para Case File Viewer y Data Estate, corregida referencia stale "Section 6" → "Section 8.1")
- Comandos y resultado:
  - Verificación cruzada de rutas/archivos citados con Glob (`doc/data-and-compliance/data_estate_seeder.md`,
    `backend/api/routes/*.py`) → todos existen; ningún doc afirma que los endpoints propuestos
    (`/case-file`, `/estates/upload`) ya existen
  - `npx --no-install tsc --noEmit --incremental false` → 0 errores (cambios solo de documentación)
- Desviaciones del plan (y por qué): ninguna
- Pendientes / riesgos: ninguno

### Fase 8 — 2026-09-12
- Comandos y resultado:
  - `npx --no-install tsc --noEmit --incremental false` → 0 errores
  - `python -X utf8 validate_format.py --submission case-file.sample.json` → PASS;
    `--submission case-file.no-findings.json` → PASS;
    `--submission case-file.edge-cases.json` → 10 errores (match exacto);
    con `--estate estate.db`: sample → PASS, edge-cases → 13 errores (match exacto)
  - `npm run build` (deteniendo mi propio dev server primero) → éxito, 8 páginas
  - `python -m pytest backend/tests/test_pipeline.py -v` → **no se pudo ejecutar**: no existe `venv/` en
    este entorno y falta `sqlalchemy` (y el resto de `backend/requirements.txt`) en el Python del
    sistema. Preexistente y no causado por este trabajo (cero archivos de `backend/` tocados en todo
    el plan); instalar ~10 paquetes (incluyendo binarios como `psycopg`) en el Python de sistema es una
    acción invasiva fuera del alcance frontend-only, así que no se intentó. **Pendiente para quien
    tenga el venv del backend configurado.**
  - Browser (build de producción, servidor reiniciado):
    - `/` carga sin errores de consola tras el build final
    - Subir `.json` local válido al visor → chip `Local file: my-submission.json`, sin banner de sample;
      subir `.txt` → error `"Select a .json file produced by the auditor (submission.json)."`
    - `read_network_requests` (390 requests observadas) → 100% a `localhost:3000` (incluye
      `sql-wasm.wasm` y el chunk de `mermaid`, ambos servidos localmente); cero llamadas a CDN externo
    - Viewport 375×812 en `/investigate` (con sample cargado) y `/investigate/data` (vacío): `document.body.scrollWidth`
      == `window.innerWidth` en ambos (sin overflow horizontal del body); los `.case-scroll` internos
      (tablas anchas, diagrama) sí desbordan dentro de su propio contenedor (`scrollWidth > clientWidth`),
      como se diseñó
- Desviaciones del plan (y por qué): ninguna, salvo la limitación de pytest arriba explicada
- Pendientes / riesgos:
  - **pytest del backend sin correr** — verificar en un entorno con el venv del backend activado
    (`pip install -r backend/requirements.txt`); no hay razón para esperar que falle, ya que ningún
    archivo de `backend/` fue tocado.
  - **Prueba humana de Ctrl+P pendiente** — pedir al usuario que la haga (fondo blanco, sin toolbar,
    hallazgos expandidos, salto de página por hallazgo, badges con color).
  - El copy de la landing (`app/page.tsx`) sigue hablando de "transaction CSVs" / la simulación anterior;
    fuera de alcance de este plan (la landing no se tocó), se avisa al usuario.

## Handoff (llenar si la sesión se corta)
- Última fase completa: Fase 8 (todas las fases del plan completas)
- Fase en curso y qué quedó hecho: ninguna — plan terminado
- Siguiente paso exacto: ninguno obligatorio. Pendientes opcionales: (1) correr
  `pytest backend/tests/test_pipeline.py` con el venv del backend activado para cerrar la verificación
  de AGENTS.md §5; (2) pedir al usuario la prueba manual de Ctrl+P; (3) decidir si se conecta
  `NEXT_PUBLIC_CASE_FILE_API`/`NEXT_PUBLIC_ESTATE_UPLOAD_API` una vez el backend implemente esos
  endpoints propuestos.
