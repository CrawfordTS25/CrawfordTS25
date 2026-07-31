# Guide source

`content.js` is the single source of truth for the .pbit → .pbix conversion guide.
Two renderers consume it, so the Word and PDF versions cannot drift apart:

```bash
npm install docx
node docs/guide-src/render_docx.js dist/UPS_2025_PBIT_to_PBIX_Guide.docx
node docs/guide-src/render_html.js /tmp/guide.html
# then print /tmp/guide.html to PDF (Chromium headless, Letter, 1in margins)
```

The PDF is produced through headless Chromium rather than LibreOffice: `soffice` in
the build environment fails to load even a minimal .docx, so it cannot be trusted as
a converter here. Both outputs are verified equivalent by extracting the text from
each and diffing — they match to 99.9%, the remainder being the HTML `<title>`
element, which is document metadata in the .docx rather than body text.
