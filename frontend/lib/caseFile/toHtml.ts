// Exports the rendered case file DOM as a self-contained HTML file: inlines every stylesheet,
// strips interactive-only chrome, force-opens collapsed sections and filtered rows (a judge reading
// the HTML offline should see everything, not whatever state the last viewer left it in), and
// embeds the original submission JSON for anyone who wants the machine-readable source alongside it.

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function collectStylesheetCss(): string {
  const chunks: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      for (const rule of Array.from(sheet.cssRules)) {
        chunks.push(rule.cssText);
      }
    } catch {
      // Cross-origin or otherwise inaccessible stylesheet; skip it.
    }
  }
  return chunks.join("\n");
}

export interface BuildStandaloneHtmlParams {
  documentElement: HTMLElement;
  title: string;
  raw: unknown;
}

export function buildStandaloneHtml({ documentElement, title, raw }: BuildStandaloneHtmlParams): string {
  const clone = documentElement.cloneNode(true) as HTMLElement;

  clone.querySelectorAll('[data-export="exclude"]').forEach((el) => el.remove());
  clone.querySelectorAll('[data-print="hide"]').forEach((el) => el.remove());
  clone.querySelectorAll("[data-collapsible-body]").forEach((el) => el.removeAttribute("hidden"));
  clone.querySelectorAll("[data-filterable-row]").forEach((el) => el.removeAttribute("hidden"));

  const css = collectStylesheetCss();
  const json = JSON.stringify(raw, null, 2).replace(/</g, "\\u003c");

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>${css}
body.case-export{margin:0;padding:32px 16px;background:#EEF1F5 !important;color:#161B22}
@media print{body.case-export{background:#fff !important;padding:0}}</style></head>
<body class="case-export">${clone.outerHTML}
<script type="application/json" id="case-file-data">${json}</script></body></html>`;
}
