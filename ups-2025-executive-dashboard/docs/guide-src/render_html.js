// Renders the same content.js to print-ready HTML, which Chromium turns into
// the PDF. Page geometry and type scale mirror the .docx so the two read as one
// document in different wrappers.
const fs = require("fs");
const { meta, blocks } = require("./content.js");

const esc = (t) => String(t)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const runHtml = (r) => {
  let out = esc(r.text);
  if (r.code) return `<code>${out}</code>`;
  if (r.bold) out = `<strong>${out}</strong>`;
  if (r.italic) out = `<em>${out}</em>`;
  return out;
};

const runs = (arr) => arr.map(runHtml).join("");
const cellHtml = (lines) => lines.map((l) => `<p>${runs(l)}</p>`).join("");

const KIND = { info: "info", warn: "warn", crit: "crit" };

const parts = [];
parts.push(`<div class="cover">
  <div class="eyebrow">${esc(meta.eyebrow)}</div>
  <h1 class="title">${esc(meta.title)}</h1>
  <div class="subtitle">${esc(meta.subtitle)}</div>
  <div class="facts">${meta.facts.map((f) => `<p>${runs(f)}</p>`).join("")}</div>
</div>`);

for (const b of blocks) {
  switch (b.t) {
    case "h1": parts.push(`<h1>${esc(b.text)}</h1>`); break;
    case "h2": parts.push(`<h2>${esc(b.text)}</h2>`); break;
    case "h3": parts.push(`<h3>${esc(b.text)}</h3>`); break;
    case "p":
      parts.push(`<p${b.muted ? ' class="muted"' : ""}>${runs(b.runs)}</p>`);
      break;
    case "code":
      parts.push(`<pre>${b.lines.map(esc).join("\n")}</pre>`);
      break;
    case "callout":
      parts.push(`<div class="callout ${KIND[b.kind] || "info"}">
        <div class="label">${esc(b.label)}</div>
        <div class="body">${runs(b.body)}</div></div>`);
      break;
    case "table": {
      const total = b.widths.reduce((a, x) => a + x, 0);
      const cols = b.widths.map((w) =>
        `<col style="width:${((w / total) * 100).toFixed(3)}%">`).join("");
      const head = b.header.map((h) => `<th>${esc(h)}</th>`).join("");
      const body = b.rows.map((r) =>
        `<tr>${r.map((cl) => `<td>${cellHtml(cl)}</td>`).join("")}</tr>`).join("");
      parts.push(`<table><colgroup>${cols}</colgroup>
        <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`);
      break;
    }
    case "pagebreak": parts.push(`<div class="pagebreak"></div>`); break;
    case "hr": parts.push(`<hr>`); break;
    default: throw new Error("unknown block type: " + b.t);
  }
}

const html = `<!doctype html>
<html><head><meta charset="utf-8"><title>${esc(meta.title)}</title>
<style>
  @page { size: Letter; margin: 1in 1in 0.85in 1in; }
  * { box-sizing: border-box; }
  body {
    margin: 0; color: #1a1a1a; background: #fff;
    font: 400 10.5pt/1.46 Calibri, "Carlito", "Segoe UI", system-ui, sans-serif;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  code { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 9.5pt;
         color: #1a3a5a; }
  p { margin: 0 0 6.5pt; }
  p.muted { color: #5f5e5a; font-size: 10pt; }
  h1 { font-size: 15pt; font-weight: 700; margin: 19pt 0 8.5pt; page-break-after: avoid; }
  h2 { font-size: 12pt; font-weight: 700; margin: 15pt 0 6.5pt; page-break-after: avoid; }
  h3 { font-size: 10.5pt; font-weight: 700; color: #5f5e5a; margin: 11pt 0 5.5pt;
       page-break-after: avoid; }
  pre {
    font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 9pt; color: #26323a;
    background: #f2f2ef; padding: 6pt 9.5pt; margin: 5.5pt 0 8.5pt;
    white-space: pre-wrap; word-break: break-word; page-break-inside: avoid;
  }
  table { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt;
          page-break-inside: auto; }
  th, td { text-align: left; vertical-align: top; padding: 4.5pt 6.5pt;
           border-top: 0.5pt solid #d8d7d0; border-bottom: 0.5pt solid #d8d7d0;
           font-size: 9.5pt; }
  th { background: #e9ecf1; color: #5f5e5a; font-weight: 700; }
  td p { margin: 0 0 3.5pt; } td p:last-child { margin: 0; }
  tr { page-break-inside: avoid; }
  thead { display: table-header-group; }
  .callout { background: #f3f5f8; padding: 7pt 10pt; margin: 8.5pt 0 10pt;
             page-break-inside: avoid; }
  .callout .label { font-weight: 700; font-size: 10pt; margin-bottom: 2.5pt; }
  .callout .body { font-size: 10pt; }
  .callout.info { border-left: 3pt solid #1f5fa9; } .callout.info .label { color: #1f5fa9; }
  .callout.warn { border-left: 3pt solid #8a5a00; } .callout.warn .label { color: #8a5a00; }
  .callout.crit { border-left: 3pt solid #a32020; } .callout.crit .label { color: #a32020; }
  hr { border: 0; border-top: 0.5pt solid #d8d7d0; margin: 9pt 0 10pt; }
  .pagebreak { page-break-after: always; }
  .cover { padding-top: 1.05in; }
  .cover .eyebrow { font-size: 11pt; color: #5f5e5a; }
  .cover .title { font-size: 23pt; font-weight: 700; margin: 3pt 0 5pt; }
  .cover .subtitle { font-size: 13pt; color: #1f5fa9; margin-bottom: 13pt; }
  .cover .facts { border-top: 0.5pt solid #d8d7d0; padding-top: 9pt; color: #5f5e5a; }
</style></head><body>${parts.join("\n")}</body></html>`;

const out = process.argv[2] || "guide.html";
fs.writeFileSync(out, html);
console.log("html:", out, html.length, "bytes");
