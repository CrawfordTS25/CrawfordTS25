# Guide source

`content.js` is the single source of truth for the .pbit → .pbix conversion guide.
Two renderers consume it, so the Word and PDF versions cannot drift apart:

```bash
npm install docx
node docs/guide-src/render_docx.js dist/UPS_2025_PBIT_to_PBIX_Guide.docx
node docs/guide-src/render_html.js /tmp/guide.html
# then print /tmp/guide.html to PDF (Chromium headless, Letter, 1in margins)
```

`build_page_map.py` is separate and has no hand-written layout of its own. It
imports `build_pbit.build_sections()` and renders what is actually there, so
the page map cannot describe a report the generator does not build:

```bash
python3 docs/guide-src/build_page_map.py /tmp/page_map.html
chromium --headless --no-pdf-header-footer \
  --print-to-pdf=dist/UPS_2025_Page_Map.pdf file:///tmp/page_map.html
```

Sheets are 15 × 9 in so the 1280 × 720 report canvas draws at 1:1 — a box in
the PDF is the size of the visual it represents. Wireframe sheets are fixed
height and clip by design; every other sheet carries `flow` so a table
paginates instead of silently losing its last row off the bottom edge.

The PDF is produced through headless Chromium rather than LibreOffice: `soffice` in
the build environment fails to load even a minimal .docx, so it cannot be trusted as
a converter here. Both outputs are verified equivalent by extracting the text from
each and diffing — they match to 99.9%, the remainder being the HTML `<title>`
element, which is document metadata in the .docx rather than body text.
