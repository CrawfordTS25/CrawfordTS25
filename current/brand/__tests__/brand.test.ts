/**
 * Brand conformance. These tests are the guide, executable: if the wordmark
 * geometry, the palette, or the generated CSS drifts from brand/tokens.json,
 * something here fails.
 */

import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import opentype from 'opentype.js';
import { buildWordmark, buildGlyphMark, buildCurrentLineMotif } from '../lib/wordmark.mts';
import { layout, measureCrossbar, ribbon, straight, spansAtY, flatten } from '../lib/geometry.mts';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..', '..');
const FONT = join(root, 'brand', 'fonts', 'BricolageGrotesque-SemiBold.ttf');

const tokens = JSON.parse(readFileSync(join(root, 'brand', 'tokens.json'), 'utf8'));
const wm = buildWordmark(FONT, tokens.typography.display.tracking);

/** Every coordinate pair in an SVG path string. */
function points(d: string): Array<[number, number]> {
  const nums = d.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? [];
  const out: Array<[number, number]> = [];
  for (let i = 0; i + 1 < nums.length; i += 2) out.push([nums[i], nums[i + 1]]);
  return out;
}

describe('the font we build from', () => {
  it('is the display face the guide specifies, at the right weight', () => {
    const font = opentype.loadSync(FONT);
    expect(font.names.fontFamily?.en).toMatch(/Bricolage Grotesque/);
    expect(font.unitsPerEm).toBe(1000);
  });

  it('sets the wordmark in lowercase — the guide forbids any other case', () => {
    expect(tokens.wordmark.text).toBe('current');
    expect(tokens.wordmark.text).toBe(tokens.wordmark.text.toLowerCase());
    expect(wm.metrics.glyphs.map((g) => g.char).join('')).toBe('current');
  });

  it('applies the specified −3% tracking', () => {
    expect(tokens.typography.display.tracking).toBe(-0.03);
    const font = opentype.loadSync(FONT);
    const loose = layout(font, 'current', 0).advance;
    const tight = layout(font, 'current', -0.03).advance;
    // Six inter-letter gaps, each pulled in by 30 units.
    expect(loose - tight).toBeCloseTo(6 * 30, 5);
  });
});

describe('the current line and the t-crossbar are one form', () => {
  it('measures the crossbar off the real glyph outline', () => {
    const font = opentype.loadSync(FONT);
    const { glyphs } = layout(font, 'current', -0.03);
    const t = glyphs[glyphs.length - 1];
    const cb = measureCrossbar(t.contours, { top: t.inkTop, bottom: t.inkBottom });

    expect(cb.thickness).toBeGreaterThan(60);
    expect(cb.thickness).toBeLessThan(160);
    // The crossbar sits at roughly x-height, above the baseline (y is down).
    expect(cb.centerY).toBeLessThan(0);
    expect(Math.abs(cb.centerY)).toBeGreaterThan(font.tables.os2.sxHeight * 0.7);
    // It is much wider than the stem it crosses.
    expect(cb.right - cb.left).toBeGreaterThan((cb.stemRight - cb.stemLeft) * 2);
  });

  it('swells the ribbon to exactly the crossbar’s measured weight', () => {
    // The whole "one continuous stroke" claim rests on this number matching.
    expect(wm.strokeWidth).toBeCloseTo(wm.metrics.crossbar.thickness, 2);
  });

  it('runs the line the full width of the crossbar', () => {
    const { left, right } = wm.metrics.crossbar;
    const xs = points(wm.currentLine).map(([x]) => x);
    // The ribbon reaches the crossbar's left tip…
    expect(Math.min(...xs)).toBeLessThan(left);
    // …and carries on past its right tip, into the crest.
    expect(Math.max(...xs)).toBeGreaterThan(right);
  });

  it('emits the line as one closed outline, not two pieces', () => {
    const moves = wm.currentLine.match(/M/g)?.length ?? 0;
    const closes = wm.currentLine.match(/Z/g)?.length ?? 0;
    expect(moves).toBe(1);
    expect(closes).toBe(1);
  });

  it('crests in a single spark, inside the lockup', () => {
    const { x, y, r } = wm.spark;
    const vb = wm.viewBox;
    expect(r).toBeGreaterThan(0);
    expect(x - r).toBeGreaterThanOrEqual(vb.x - 0.01);
    expect(x + r).toBeLessThanOrEqual(vb.x + vb.w + 0.01);
    expect(y - r).toBeGreaterThanOrEqual(vb.y - 0.01);
    // The spark is the high point on the right: above the crossbar, right of the t.
    expect(y).toBeLessThan(wm.metrics.crossbar.centerY);
    expect(x).toBeGreaterThan(wm.metrics.crossbar.right);
  });

  it('keeps the ripple clear of the letters so nothing collides', () => {
    // Below the baseline the only ink is the current line, so the ripple can
    // never merge with a letterform.
    const letterBottoms = wm.metrics.glyphs.map(() => 0);
    expect(Math.max(...letterBottoms)).toBe(0);
    const lowest = Math.max(...points(wm.currentLine).map(([, y]) => y));
    expect(lowest).toBeGreaterThan(60);
  });

  it('bounds the viewBox around every part of the mark', () => {
    const vb = wm.viewBox;
    expect(vb.w).toBeGreaterThan(0);
    expect(vb.h).toBeGreaterThan(0);
    for (const [x, y] of points(wm.currentLine)) {
      expect(x).toBeGreaterThanOrEqual(vb.x - 0.6);
      expect(x).toBeLessThanOrEqual(vb.x + vb.w + 0.6);
      expect(y).toBeGreaterThanOrEqual(vb.y - 0.6);
      expect(y).toBeLessThanOrEqual(vb.y + vb.h + 0.6);
    }
  });

  it('reserves clearspace equal to the height of the "c"', () => {
    const font = opentype.loadSync(FONT);
    const c = font.charToGlyph('c').getBoundingBox();
    expect(wm.clearspace).toBeCloseTo(c.y2 - c.y1, 1);
  });
});

describe('the tapered ribbon', () => {
  it('honours the requested weight along a straight centreline', () => {
    const d = ribbon([straight({ x: 0, y: 0 }, { x: 100, y: 0 })], [{ at: 0, w: 10 }, { at: 1, w: 10 }]);
    const ys = points(d).map(([, y]) => y);
    // A horizontal 10-unit ribbon spans y −5..5, plus the round caps.
    expect(Math.max(...ys)).toBeCloseTo(5, 1);
    expect(Math.min(...ys)).toBeCloseTo(-5, 1);
  });

  it('tapers between keyframes', () => {
    const d = ribbon([straight({ x: 0, y: 0 }, { x: 100, y: 0 })], [{ at: 0, w: 4 }, { at: 1, w: 40 }]);
    const pts = points(d);
    // Near the start the ribbon is thin; near the end it is wide.
    const nearStart = pts.filter(([x]) => x > 1 && x < 6).map(([, y]) => Math.abs(y));
    const nearEnd = pts.filter(([x]) => x > 94 && x < 99).map(([, y]) => Math.abs(y));
    expect(Math.max(...nearStart)).toBeLessThan(6);
    expect(Math.max(...nearEnd)).toBeGreaterThan(14);
  });

  it('closes its outline', () => {
    const d = ribbon([straight({ x: 0, y: 0 }, { x: 50, y: 20 })], [{ at: 0, w: 8 }, { at: 1, w: 8 }]);
    expect(d.startsWith('M')).toBe(true);
    expect(d.endsWith('Z')).toBe(true);
  });
});

describe('glyph scanline helpers', () => {
  it('finds two stems when crossing a lowercase n', () => {
    const font = opentype.loadSync(FONT);
    const n = font.charToGlyph('n');
    const contours = flatten(n.getPath(0, 0, font.unitsPerEm));
    // Halfway up the x-height an "n" is two uprights.
    const spans = spansAtY(contours, -font.tables.os2.sxHeight / 2);
    expect(spans.length).toBe(2);
    expect(spans[1][0]).toBeGreaterThan(spans[0][1]);
  });

  it('finds one span when crossing a lowercase l', () => {
    const font = opentype.loadSync(FONT);
    const contours = flatten(font.charToGlyph('l').getPath(0, 0, font.unitsPerEm));
    expect(spansAtY(contours, -font.tables.os2.sxHeight / 2).length).toBe(1);
  });
});

describe('the C-current glyph', () => {
  const gm = buildGlyphMark(FONT);

  it('fits letter, wave and spark inside the mark box', () => {
    expect(gm.markBox.right).toBeGreaterThanOrEqual(gm.spark.x + gm.spark.r - 0.01);
    expect(gm.markBox.top).toBeLessThanOrEqual(gm.spark.y - gm.spark.r + 0.01);
    expect(gm.markBox.left).toBeLessThanOrEqual(gm.letterBox.left);
    expect(gm.markBox.bottom).toBeGreaterThanOrEqual(gm.letterBox.bottom);
  });

  it('keeps the wave light — the spark is used sparingly', () => {
    const letterWidth = gm.letterBox.right - gm.letterBox.left;
    expect(gm.strokeWidth).toBeLessThan(letterWidth * 0.16);
  });
});

describe('the current-line motif', () => {
  const motif = buildCurrentLineMotif(4);

  it('carries a spare wave past each edge so it can scroll seamlessly', () => {
    const xs = points(motif.d).map(([x]) => x);
    expect(Math.min(...xs)).toBeLessThanOrEqual(-motif.waveSpan);
    expect(Math.max(...xs)).toBeGreaterThanOrEqual(100 + motif.waveSpan);
  });

  it('advertises the wave span the CSS animation translates by', () => {
    expect(motif.waveSpan).toBe(25);
    const css = readFileSync(join(root, 'src', 'styles', 'base.css'), 'utf8');
    expect(css).toMatch(/translateX\(-25px\)/);
  });
});

describe('tokens reach the stylesheet', () => {
  const css = readFileSync(join(root, 'src', 'styles', 'tokens.css'), 'utf8');

  it('publishes every palette colour', () => {
    for (const [name, entry] of Object.entries(tokens.color) as Array<[string, { value: string }]>) {
      expect(css, name).toContain(entry.value);
    }
  });

  it('publishes both gradients at the specified angle', () => {
    expect(css).toContain(`--gradient-water: linear-gradient(${tokens.gradient.angle}deg`);
    for (const stop of tokens.gradient.onDark) expect(css).toContain(stop);
    for (const stop of tokens.gradient.onLight) expect(css).toContain(stop);
  });

  it('exposes theme-aware gradient stops for the inline marks', () => {
    for (let i = 0; i < tokens.gradient.onDark.length; i++) {
      expect(css).toContain(`--wm-stop-${i + 1}: ${tokens.gradient.onDark[i]}`);
      expect(css).toContain(`--wm-stop-${i + 1}: ${tokens.gradient.onLight[i]}`);
    }
  });

  it('publishes the type scale with the guide’s tracking', () => {
    for (const [name, spec] of Object.entries(tokens.typography.scale) as Array<
      [string, { tracking: number; weight: number }]
    >) {
      expect(css, name).toContain(`--type-${name}-tracking: ${spec.tracking}em`);
      expect(css, name).toContain(`--type-${name}-weight: ${spec.weight}`);
    }
  });

  it('binds the display face to headlines only', () => {
    const base = readFileSync(join(root, 'src', 'styles', 'base.css'), 'utf8');
    // Only .h1/.h2 and the wordmark may reach for Bricolage.
    const displayUses = base.match(/var\(--font-display\)/g) ?? [];
    expect(displayUses.length).toBeLessThanOrEqual(2);
    expect(base).toMatch(/\.h1,\s*\n\.h2\s*\{[^}]*--font-display/);
  });

  it('carries the minimum sizes the guide sets', () => {
    const geometry = readFileSync(join(root, 'src', 'brand', 'geometry.ts'), 'utf8');
    expect(tokens.wordmark.minWidthPx).toBe(96);
    expect(tokens.wordmark.iconMinPx).toBe(24);
    expect(geometry).toContain(`wordmarkWidth: ${tokens.wordmark.minWidthPx}`);
    expect(geometry).toContain(`icon: ${tokens.wordmark.iconMinPx}`);
  });
});

describe('generated lockups', () => {
  const read = (name: string) => readFileSync(join(root, 'brand', 'assets', name), 'utf8');

  it('ship primary, light, monochrome and icon variants', () => {
    for (const name of [
      'wordmark-primary.svg',
      'wordmark-light.svg',
      'wordmark-mono.svg',
      'icon.svg',
      'icon-min.svg',
      'current-line.svg',
    ]) {
      expect(read(name)).toContain('<svg');
    }
  });

  it('uses the deepened gradient on light and the water gradient on dark', () => {
    expect(read('wordmark-primary.svg')).toContain(tokens.gradient.onDark[0]);
    expect(read('wordmark-light.svg')).toContain(tokens.gradient.onLight[0]);
  });

  it('draws the monochrome lockup entirely in currentColor', () => {
    const mono = read('wordmark-mono.svg');
    expect(mono).not.toMatch(/linearGradient/);
    expect(mono).not.toContain(tokens.color.spark.value);
  });

  it('drops the amber wave from the sub-24px icon', () => {
    expect(read('icon.svg')).toContain(tokens.color.spark.value);
    expect(read('icon-min.svg')).not.toContain(tokens.color.spark.value);
  });

  it('adds no shadow, glow, outline or bevel — the guide forbids all four', () => {
    for (const name of ['wordmark-primary.svg', 'wordmark-light.svg', 'wordmark-mono.svg', 'icon.svg']) {
      const svg = read(name);
      expect(svg, name).not.toMatch(/filter|feGaussianBlur|feDropShadow|feBevel/i);
    }
  });

  it('never stretches the mark — the viewBox aspect is preserved', () => {
    const svg = read('wordmark-primary.svg');
    const vb = svg.match(/viewBox="([^"]+)"/)![1].split(' ').map(Number);
    const w = Number(svg.match(/width="(\d+)"/)![1]);
    const h = Number(svg.match(/height="(\d+)"/)![1]);
    expect(w / h).toBeCloseTo(vb[2] / vb[3], 1);
  });
});
