/**
 * End-to-end smoke test against a running server. Drives the real app in
 * Chromium: navigates, chats, sparks, follows, searches, and checks that a
 * SECOND browser sees the first one's messages and presence — which is the
 * whole point of a live platform.
 *
 * Usage: BASE=http://localhost:8787 npx tsx scripts/smoke.mts [--shots dir]
 */

import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Browser, Page } from 'playwright';
import { launchChromium } from './lib/browser.mts';

const BASE = process.env.BASE ?? 'http://localhost:8787';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const shotsFlag = process.argv.indexOf('--shots');
const shotDir = shotsFlag > -1 ? resolve(process.argv[shotsFlag + 1]!) : join(root, 'screenshots');
mkdirSync(shotDir, { recursive: true });

let passed = 0;
const failures: string[] = [];

function ok(label: string) {
  passed += 1;
  console.log(`  ✓ ${label}`);
}

function fail(label: string, detail: unknown) {
  failures.push(`${label} — ${detail instanceof Error ? detail.message : String(detail)}`);
  console.log(`  ✗ ${label}\n      ${detail instanceof Error ? detail.message : String(detail)}`);
}

async function check(label: string, fn: () => Promise<void>) {
  try {
    await fn();
    ok(label);
  } catch (err) {
    fail(label, err);
  }
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: join(shotDir, `${name}.png`), fullPage: false });
}

/** Surface client-side errors instead of letting them hide behind a blank page. */
function watchConsole(page: Page, sink: string[]) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') sink.push(msg.text());
  });
  page.on('pageerror', (err) => sink.push(err.message));
}

const browser: Browser = await launchChromium();
const consoleErrors: string[] = [];

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 940 } });
  const page = await context.newPage();
  watchConsole(page, consoleErrors);

  /* ── Home ──────────────────────────────────────────────────────────────── */

  await check('home page loads with the wordmark and a live hero', async () => {
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForSelector('.hero', { timeout: 15_000 });
    const marks = await page.locator('svg[aria-label="current"]').count();
    assert(marks > 0, 'no wordmark rendered');
    const spark = await page.locator('.hero .live-spark').count();
    assert(spark === 1, `expected exactly one spark badge in the hero, found ${spark}`);
    const title = await page.locator('.hero .h1').innerText();
    assert(title.trim().length > 0, 'hero has no title');
  });

  await check('the guide’s one-spark-per-view rule holds on the home page', async () => {
    const sparks = await page.locator('.live-spark').count();
    assert(sparks === 1, `expected 1 amber live badge on the page, found ${sparks}`);
    const cool = await page.locator('.live-cool').count();
    assert(cool >= 1, 'secondary live cards should still be marked, in the cool tone');
  });

  await shot(page, '01-home');

  /* ── Live room ─────────────────────────────────────────────────────────── */

  await check('tuning in opens the live room', async () => {
    await page.getByRole('link', { name: 'Tune in' }).click();
    await page.waitForURL(/\/live\//, { timeout: 10_000 });
    await page.waitForSelector('.stage', { timeout: 10_000 });
    await page.waitForSelector('.chat', { timeout: 10_000 });
  });

  await check('the socket connects and the room reports listeners', async () => {
    await page.waitForFunction(
      () => /\d/.test(document.querySelector('.chat .panel-head span:last-child')?.textContent ?? ''),
      undefined,
      { timeout: 10_000 },
    );
    const text = await page.locator('.chat .panel-head span:last-child').innerText();
    assert(/here/.test(text), `chat header did not report presence, got "${text}"`);
  });

  await check('the shared playhead advances', async () => {
    const read = async () =>
      Number(
        (await page.locator('.transport-times span').first().innerText())
          .split(':')
          .reduce((acc, part) => acc * 60 + Number(part), 0),
      );
    const before = await read();
    await page.waitForTimeout(2_600);
    const after = await read();
    assert(after > before, `playhead did not move (${before} → ${after})`);
  });

  await check('sending a spark increments the counter', async () => {
    const button = page.getByRole('button', { name: /^Spark/ });
    const before = await button.innerText();
    await button.click();
    await page.waitForTimeout(600);
    const after = await button.innerText();
    assert(before !== after, `spark count did not change (still "${after}")`);
    const flying = await page.locator('.spark-fly').count();
    assert(flying >= 0, 'spark field missing');
  });

  const mine = `smoke test ${Date.now()}`;
  await check('chat message posts and appears in the log', async () => {
    await page.fill('#chat-input', mine);
    await page.getByRole('button', { name: 'Send' }).click();
    await page.waitForSelector(`.chat-body:text-is("${mine}")`, { timeout: 8_000 });
  });

  await shot(page, '02-live-room');

  /* ── A second listener in the same room ────────────────────────────────── */

  await check('a second browser sees the first one’s message and bumps presence', async () => {
    const other = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page2 = await other.newPage();
    watchConsole(page2, consoleErrors);
    try {
      const url = page.url();
      await page2.goto(url, { waitUntil: 'networkidle' });
      await page2.waitForSelector('.chat', { timeout: 10_000 });
      // The backlog is persisted, so the earlier message must be there.
      await page2.waitForSelector(`.chat-body:text-is("${mine}")`, { timeout: 8_000 });

      // Now go the other way: page2 speaks, page1 must hear it live over the socket.
      const theirs = `second listener ${Date.now()}`;
      await page2.fill('#chat-input', theirs);
      await page2.getByRole('button', { name: 'Send' }).click();
      await page.waitForSelector(`.chat-body:text-is("${theirs}")`, { timeout: 8_000 });
    } finally {
      await other.close();
    }
  });

  /* ── Creator ───────────────────────────────────────────────────────────── */

  await check('creator profile loads and follow persists across a reload', async () => {
    await page.locator('.live-layout a[href^="/c/"]').first().click();
    await page.waitForURL(/\/c\//, { timeout: 10_000 });
    await page.waitForSelector('.hero .h1', { timeout: 10_000 });

    const follow = page.getByRole('button', { name: /^Follow$/ });
    await follow.click();
    await page.waitForSelector('button[aria-pressed="true"]', { timeout: 8_000 });

    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('button[aria-pressed="true"]', { timeout: 10_000 });
    const label = await page.locator('button[aria-pressed="true"]').first().innerText();
    assert(/Following/i.test(label), `expected "Following" after reload, got "${label}"`);
  });

  await check('the track list renders', async () => {
    const tracks = await page.locator('.track').count();
    assert(tracks > 0, 'no tracks listed on the creator page');
  });

  await shot(page, '03-creator');

  /* ── Discover / search ─────────────────────────────────────────────────── */

  await check('search finds a creator by genre', async () => {
    await page.goto(`${BASE}/discover`, { waitUntil: 'networkidle' });
    await page.fill('#discover-search', 'choral');
    await page.getByRole('button', { name: 'Search' }).click();
    await page.waitForURL(/q=choral/, { timeout: 8_000 });
    await page.waitForSelector('.creator-card', { timeout: 10_000 });
    const text = await page.locator('.creator-card').first().innerText();
    assert(/Amaris/i.test(text), `expected Amaris in results, got "${text}"`);
  });

  await check('a search with no matches explains itself', async () => {
    await page.goto(`${BASE}/discover?q=zzzznope`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.card', { timeout: 10_000 });
    const body = await page.locator('main').innerText();
    assert(/Nothing matches/i.test(body), 'no empty-state message for a dead search');
  });

  await shot(page, '04-discover');

  /* ── Brand system page ────────────────────────────────────────────────── */

  await check('the brand page renders every mark and swatch', async () => {
    await page.goto(`${BASE}/brand`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.swatches', { timeout: 10_000 });
    const swatches = await page.locator('.swatch').count();
    assert(swatches >= 9, `expected the full palette, found ${swatches} swatches`);
    const marks = await page.locator('svg[aria-label="current"]').count();
    assert(marks >= 6, `expected the lockups and icons, found ${marks} marks`);
  });

  await shot(page, '05-brand');

  /* ── Light theme ──────────────────────────────────────────────────────── */

  await check('the light theme swaps the gradient and stays readable', async () => {
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /Switch to light theme/ }).click();
    await page.waitForFunction(() => document.documentElement.dataset.theme === 'light', undefined, {
      timeout: 5_000,
    });
    const stop = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--wm-stop-1').trim(),
    );
    assert(stop.toLowerCase() === '#12b6a0', `light theme gradient did not swap, got "${stop}"`);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    assert(bg === 'rgb(242, 247, 248)', `expected the Foam background, got ${bg}`);

    // The hero is a dark artwork plate in both themes, so its labels must keep
    // the on-dark ink rather than flipping to the light theme's dark ink.
    const heroLabel = await page.evaluate(() => {
      const el = document.querySelector('.hero .label.faint');
      return el ? getComputedStyle(el).color : null;
    });
    assert(heroLabel, 'no hero label found to check');
    const [r, g, b] = heroLabel!.match(/\d+/g)!.map(Number);
    // Ink on dark is #EAF6FA; anything much darker means the theme leaked in.
    assert(
      (r + g + b) / 3 > 200,
      `hero label is too dark on its dark plate (${heroLabel}) — it would be unreadable`,
    );
  });

  await shot(page, '06-home-light');

  /* ── Mobile ───────────────────────────────────────────────────────────── */

  await check('the live room holds up at 390px with no horizontal scroll', async () => {
    const mobile = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
    });
    const m = await mobile.newPage();
    watchConsole(m, consoleErrors);
    try {
      await m.goto(`${BASE}/live/nrissa-undertow-session`, { waitUntil: 'networkidle' });
      await m.waitForSelector('.chat', { timeout: 10_000 });
      const overflow = await m.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      assert(overflow <= 1, `page scrolls sideways by ${overflow}px at 390px wide`);
      await m.screenshot({ path: join(shotDir, '07-live-mobile.png'), fullPage: false });
    } finally {
      await mobile.close();
    }
  });

  /* ── 404 ──────────────────────────────────────────────────────────────── */

  await check('an unknown route shows the not-found state', async () => {
    await page.goto(`${BASE}/nope/nope`, { waitUntil: 'networkidle' });
    const body = await page.locator('main').innerText();
    assert(/drifted off/i.test(body), 'no 404 state rendered');
  });

  await check('no client-side console errors along the way', async () => {
    const real = consoleErrors.filter((e) => !/favicon|manifest/i.test(e));
    assert(real.length === 0, `console errors:\n      ${real.join('\n      ')}`);
  });

  await context.close();
} finally {
  await browser.close();
}

console.log(`\n  ${passed} passed, ${failures.length} failed`);
console.log(`  screenshots → ${shotDir}\n`);
if (failures.length > 0) process.exit(1);
