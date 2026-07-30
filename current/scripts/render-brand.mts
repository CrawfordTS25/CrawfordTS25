/**
 * Renders the generated brand lockups to PNG contact sheets so the art can be
 * eyeballed (and diffed) without opening a design tool.
 *
 * Run: npx tsx scripts/render-brand.mts [outDir]
 */

import { launchChromium } from './lib/browser.mts';
import { readFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = resolve(process.argv[2] ?? join(root, 'brand', 'preview'));
mkdirSync(outDir, { recursive: true });

const read = (p: string) => readFileSync(join(root, p), 'utf8');

const sheets: Array<{ name: string; html: string; width: number }> = [
  {
    name: 'wordmark-primary',
    width: 1100,
    html: `<div style="background:#07131F;padding:64px">
      <div style="width:900px">${read('brand/assets/wordmark-primary.svg').replace(/width="\d+" height="\d+"/, 'width="900"')}</div>
      <div style="width:340px;margin-top:56px">${read('brand/assets/wordmark-primary.svg').replace(/width="\d+" height="\d+"/, 'width="340"')}</div>
      <div style="width:96px;margin-top:40px">${read('brand/assets/wordmark-primary.svg').replace(/width="\d+" height="\d+"/, 'width="96"')}</div>
    </div>`,
  },
  {
    name: 'wordmark-light',
    width: 1100,
    html: `<div style="background:#F2F7F8;padding:64px">
      <div style="width:900px">${read('brand/assets/wordmark-light.svg').replace(/width="\d+" height="\d+"/, 'width="900"')}</div>
      <div style="width:340px;margin-top:56px">${read('brand/assets/wordmark-light.svg').replace(/width="\d+" height="\d+"/, 'width="340"')}</div>
    </div>`,
  },
  {
    name: 'wordmark-mono',
    width: 1100,
    html: `<div style="background:#0C2237;padding:64px;color:#EAF6FA">
      <div style="width:900px">${read('brand/assets/wordmark-mono.svg').replace(/width="\d+" height="\d+"/, 'width="900"')}</div>
    </div>`,
  },
  {
    name: 'icons',
    width: 760,
    html: `<div style="background:#1a2b3c;padding:56px;display:flex;gap:40px;align-items:flex-end">
      <div>${read('brand/assets/icon.svg').replace(/width="\d+" height="\d+"/, 'width="256"')}</div>
      <div>${read('brand/assets/icon.svg').replace(/width="\d+" height="\d+"/, 'width="96"')}</div>
      <div>${read('brand/assets/icon.svg').replace(/width="\d+" height="\d+"/, 'width="48"')}</div>
      <div>${read('brand/assets/icon-min.svg').replace(/width="\d+" height="\d+"/, 'width="24"')}</div>
      <div style="color:#EAF6FA;font:12px/1 system-ui;letter-spacing:.14em">256 · 96 · 48 · 24(min)</div>
    </div>`,
  },
  {
    name: 'current-line',
    width: 900,
    html: `<div style="background:#07131F;padding:48px">
      <div style="width:800px">${read('brand/assets/current-line.svg').replace(/width="\d+" height="\d+"/, 'width="800" height="60"')}</div>
    </div>`,
  },
];

const browser = await launchChromium();
const page = await browser.newPage({ deviceScaleFactor: 2 });

for (const sheet of sheets) {
  await page.setViewportSize({ width: sheet.width, height: 600 });
  await page.setContent(
    `<!doctype html><html><body style="margin:0">${sheet.html}</body></html>`,
    { waitUntil: 'load' },
  );
  const el = await page.$('body > div');
  await el!.screenshot({ path: join(outDir, `${sheet.name}.png`) });
  console.log(`  ✓ ${sheet.name}.png`);
}

await browser.close();
console.log(`\n  previews in ${outDir}\n`);
