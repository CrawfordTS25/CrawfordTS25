/**
 * Constructs the `current` wordmark as true vector geometry.
 *
 * Per the brand guide the current line "ripples beneath the word, rises on the
 * right, and flows into the crossbar of the t, cresting in the spark" — and the
 * crossbar and the line must be ONE continuous path.
 *
 * We achieve that literally: the line's terminal segment is laid down at the
 * measured centre line and weight of the font's own t-crossbar, so the two are
 * coincident. Painted with the same gradient in the same user space, the union
 * is a single unbroken stroke — no seam, at any size.
 *
 * Lockup space: font units (1000/em), baseline y = 0, y increases downward.
 */

import opentype, { type Font } from 'opentype.js';
import {
  layout,
  measureCrossbar,
  pathToString,
  ribbon,
  segmentBoundaries,
  smoothSegments,
  straight,
  type Crossbar,
  type Cubic,
  type PlacedGlyph,
  type WidthKey,
} from './geometry.mts';

const round = (v: number, p = 2) => Number(v.toFixed(p));

export type Pt = { x: number; y: number };

/** Point on a cubic Bézier at parameter t. */
export function cubicAt(p0: Pt, c1: Pt, c2: Pt, p3: Pt, t: number): Pt {
  const mt = 1 - t;
  const a = mt ** 3;
  const b = 3 * mt * mt * t;
  const c = 3 * mt * t * t;
  const d = t ** 3;
  return {
    x: a * p0.x + b * c1.x + c * c2.x + d * p3.x,
    y: a * p0.y + b * c1.y + c * c2.y + d * p3.y,
  };
}

/**
 * Smooth cubic path through waypoints (Catmull-Rom → Bézier). Endpoints are
 * duplicated so the curve starts and ends exactly on the first/last waypoint.
 */
export function smoothThrough(points: Pt[], tension = 1): string {
  if (points.length < 2) throw new Error('need at least two waypoints');
  const p = [points[0], ...points, points[points.length - 1]];
  let d = `M${round(points[0].x)} ${round(points[0].y)}`;
  for (let i = 1; i < p.length - 2; i++) {
    const p0 = p[i - 1];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2];
    const c1 = { x: p1.x + ((p2.x - p0.x) / 6) * tension, y: p1.y + ((p2.y - p0.y) / 6) * tension };
    const c2 = { x: p2.x - ((p3.x - p1.x) / 6) * tension, y: p2.y - ((p3.y - p1.y) / 6) * tension };
    d += `C${round(c1.x)} ${round(c1.y)} ${round(c2.x)} ${round(c2.y)} ${round(p2.x)} ${round(p2.y)}`;
  }
  return d;
}

export type WordmarkGeometry = {
  /** Outlined letterforms of "current" (fill). */
  letters: string;
  /**
   * The letters the current line passes BEHIND — "curren", i.e. everything but
   * the t. Dilated by `knockoutWidth` it becomes a mask that opens a hairline
   * of air where the climbing line crosses the n, so it reads as passing behind
   * rather than colliding. The t is excluded: there the line must fuse with the
   * crossbar.
   */
  knockout: string;
  knockoutWidth: number;
  /** The current line as a closed tapered outline (filled, not stroked). */
  currentLine: string;
  /** Stroke weight of the current line == measured t-crossbar thickness. */
  strokeWidth: number;
  /** Centre of the amber spark at the crest of the wave. */
  spark: { x: number; y: number; r: number };
  viewBox: { x: number; y: number; w: number; h: number };
  /** Clearspace unit — the height of the "c", per the guide. */
  clearspace: number;
  metrics: {
    unitsPerEm: number;
    xHeight: number;
    wordAdvance: number;
    crossbar: Crossbar;
    glyphs: Array<{ char: string; x: number; inkLeft: number; inkRight: number }>;
  };
};

export function buildWordmark(fontPath: string, tracking = -0.03): WordmarkGeometry {
  const font: Font = opentype.loadSync(fontPath);
  const upm = font.unitsPerEm;
  const { glyphs, advance } = layout(font, 'current', tracking);

  const t = glyphs[glyphs.length - 1];
  const c = glyphs[0];
  const cb = measureCrossbar(t.contours, { top: t.inkTop, bottom: t.inkBottom });

  const letters = glyphs.map((g: PlacedGlyph) => pathToString(g.path)).join('');

  const weight = cb.thickness;
  const half = weight / 2;
  const inkLeft = Math.min(...glyphs.map((g) => g.inkLeft));
  const inkRight = Math.max(...glyphs.map((g) => g.inkRight));

  // ── The ripple: gentle waves in the descender zone, beneath the whole word.
  //    Kept low enough that it never grazes the knockout around the letters.
  const rippleMid = 150;
  const amp = 42;
  const start = inkLeft - 92;
  const ripple: Pt[] = [
    { x: start, y: rippleMid - 8 },
    { x: inkLeft + 470, y: rippleMid + amp },
    { x: inkLeft + 1010, y: rippleMid - amp },
    { x: inkLeft + 1550, y: rippleMid + amp },
    { x: inkLeft + 2090, y: rippleMid - amp },
    // Last trough, under the n — where the water gathers before it climbs.
    { x: inkLeft + 2458, y: rippleMid + amp * 0.72 },
  ];
  const tail = ripple[ripple.length - 1];

  // ── The rise. The line gathers out of the last trough, thins, and climbs
  //    through the n — slipping behind its right stem — to arrive dead
  //    horizontal on the crossbar's centre line. Because the ribbon TAPERS, the
  //    climb is slim enough to thread the letter cleanly and then swells to
  //    exactly the crossbar's measured weight, so the two become one form.
  const nGlyph = glyphs[5];
  const turn = { x: (nGlyph.inkLeft + nGlyph.inkRight) / 2 - 66, y: 26 };
  const arrive = { x: cb.left, y: cb.centerY };

  // ── The crest. Past the crossbar the line lifts clear of the letter and
  //    terminates in the spark — the one warm accent, top right.
  const apex = { x: cb.right + 150, y: cb.centerY - 104 };

  const rippleSegs = smoothSegments(ripple);
  const centreline: Cubic[] = [
    ...rippleSegs,
    // out of the trough, turning up
    {
      p0: tail,
      c1: { x: tail.x + 86, y: tail.y + 10 },
      c2: { x: turn.x - 44, y: turn.y + 104 },
      p3: turn,
    },
    // the climb; c2 sits on the crossbar's centre line so the arrival tangent
    // is exactly horizontal and there is no kink where it becomes the crossbar
    {
      p0: turn,
      c1: { x: turn.x + 64, y: turn.y - 138 },
      c2: { x: arrive.x - 92, y: arrive.y },
      p3: arrive,
    },
    // …BE the crossbar, coincident with the glyph's own
    straight(arrive, { x: cb.right, y: cb.centerY }),
    // …then crest into the spark
    {
      p0: { x: cb.right, y: cb.centerY },
      c1: { x: cb.right + 62, y: cb.centerY },
      c2: { x: apex.x - 44, y: apex.y + 50 },
      p3: apex,
    },
  ];

  // Weight along the line, as fractions of total arc length. The climb stays
  // slim, then swells to the crossbar's exact weight and holds it.
  const b = segmentBoundaries(centreline);
  const nSeg = centreline.length;
  const climbStart = b[nSeg - 3];
  const climbEnd = b[nSeg - 2];
  const widths: WidthKey[] = [
    { at: 0, w: weight * 0.82 },
    { at: b[3], w: weight * 0.78 },
    { at: b[rippleSegs.length], w: weight * 0.68 },
    { at: climbStart, w: weight * 0.52 },
    { at: climbStart + (climbEnd - climbStart) * 0.72, w: weight * 0.6 },
    { at: climbEnd, w: weight },
    { at: b[nSeg - 1], w: weight },
    { at: 1, w: weight * 0.72 },
  ];

  const currentLine = ribbon(centreline, widths);

  const spark = { x: apex.x, y: apex.y, r: round(weight * 0.6) };

  // "curren" — what the line passes behind. The t is excluded: there the line
  // and the crossbar must stay fused.
  const knockout = glyphs
    .slice(0, -1)
    .map((g) => pathToString(g.path))
    .join('');
  const knockoutWidth = round(weight * 0.34);

  // ── Bounds: letters ink ∪ ribbon ∪ spark.
  const minX = Math.min(inkLeft, start - half, spark.x - spark.r);
  const maxX = Math.max(inkRight, apex.x + half, spark.x + spark.r);
  const minY = Math.min(...glyphs.map((g) => g.inkTop), apex.y - half, spark.y - spark.r);
  const maxY = Math.max(...glyphs.map((g) => g.inkBottom), rippleMid + amp + half);

  return {
    letters,
    knockout,
    knockoutWidth,
    currentLine,
    strokeWidth: round(weight),
    spark: { x: round(spark.x), y: round(spark.y), r: spark.r },
    viewBox: { x: round(minX), y: round(minY), w: round(maxX - minX), h: round(maxY - minY) },
    clearspace: round(c.inkBottom - c.inkTop),
    metrics: {
      unitsPerEm: upm,
      xHeight: font.tables.os2.sxHeight,
      wordAdvance: round(advance),
      crossbar: {
        centerY: round(cb.centerY),
        thickness: round(cb.thickness),
        left: round(cb.left),
        right: round(cb.right),
        stemLeft: round(cb.stemLeft),
        stemRight: round(cb.stemRight),
      },
      glyphs: glyphs.map((g) => ({
        char: g.char,
        x: round(g.x),
        inkLeft: round(g.inkLeft),
        inkRight: round(g.inkRight),
      })),
    },
  };
}

/**
 * The C-current glyph: favicon, app icon, avatar fallback, clip watermark.
 * A lowercase "c" with the current running through its aperture. Below the
 * 24px icon floor the guide says to drop the amber wave and keep the C only,
 * so the wave is emitted as a separate path the consumer can omit.
 */
export function buildGlyphMark(fontPath: string) {
  const font: Font = opentype.loadSync(fontPath);
  const glyph = font.charToGlyph('c');
  const bb = glyph.getBoundingBox();
  const path = pathToString(glyph.getPath(0, 0, font.unitsPerEm));

  const left = bb.x1;
  const right = bb.x2;
  const top = -bb.y2;
  const bottom = -bb.y1;
  const midY = (top + bottom) / 2;
  const w = right - left;

  // A single slim ripple crossing the aperture, cresting just outside on the
  // right. Deliberately light: the spark is the only warm colour in the system
  // and the guide asks for it sparingly.
  const weight = round(w * 0.105);
  const amp = w * 0.05;
  const x0 = left - w * 0.05;
  const x1 = right + w * 0.1;
  const wave = smoothThrough([
    { x: x0, y: midY + amp * 0.5 },
    { x: x0 + (x1 - x0) * 0.32, y: midY - amp },
    { x: x0 + (x1 - x0) * 0.66, y: midY + amp },
    { x: x1, y: midY - amp * 0.85 },
  ]);
  const spark = { x: round(x1), y: round(midY - amp * 0.85), r: round(weight * 0.64) };

  // Bounds of the whole mark, so the icon canvas can fit letter + wave + spark
  // rather than the letter alone.
  const markBox = {
    left: round(Math.min(left, x0 - weight / 2)),
    right: round(Math.max(right, x1 + weight / 2, spark.x + spark.r)),
    top: round(Math.min(top, midY - amp - weight / 2, spark.y - spark.r)),
    bottom: round(Math.max(bottom, midY + amp + weight / 2)),
  };

  const pad = w * 0.04;
  const minX = markBox.left - pad;
  const maxX = markBox.right + pad;
  const minY = markBox.top - pad;
  const maxY = markBox.bottom + pad;

  return {
    letter: path,
    wave,
    strokeWidth: weight,
    spark,
    markBox,
    viewBox: { x: round(minX), y: round(minY), w: round(maxX - minX), h: round(maxY - minY) },
    letterBox: { left: round(left), right: round(right), top: round(top), bottom: round(bottom) },
  };
}

/**
 * The standalone current-line motif: section dividers, progress bars, loading
 * states. Emitted on a 0..100 × -10..10 grid so it tiles and scales cleanly.
 */
export function buildCurrentLineMotif(waves = 4) {
  const span = 100 / waves;
  const pts: Pt[] = [];
  // One extra wave beyond each edge so the motif can scroll horizontally
  // without ever revealing an end.
  for (let i = -1; i <= waves + 1; i++) {
    pts.push({ x: i * span, y: 0 });
    pts.push({ x: i * span + span * 0.25, y: -6.2 });
    pts.push({ x: i * span + span * 0.5, y: 0 });
    pts.push({ x: i * span + span * 0.75, y: 6.2 });
  }
  pts.push({ x: (waves + 2) * span, y: 0 });
  return { d: smoothThrough(pts), viewBox: { x: 0, y: -10, w: 100, h: 20 }, waveSpan: round(span) };
}
