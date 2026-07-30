/**
 * Glyph geometry helpers for the `current` wordmark build.
 *
 * Everything here works in "lockup space": font units (1000/em), baseline at
 * y = 0, y increasing DOWNWARD (SVG convention). Ink above the baseline
 * therefore has negative y — x-height top sits at y = -523.
 */

import type { Font, Path, PathCommand } from 'opentype.js';

export type Pt = { x: number; y: number };
export type Contour = Pt[];

/** Flatten a Path's curves into polyline contours. */
export function flatten(path: Path, steps = 24): Contour[] {
  const contours: Contour[] = [];
  let cur: Contour = [];
  let cx = 0;
  let cy = 0;

  const push = (x: number, y: number) => {
    cur.push({ x, y });
    cx = x;
    cy = y;
  };

  for (const cmd of path.commands as PathCommand[]) {
    switch (cmd.type) {
      case 'M':
        if (cur.length > 1) contours.push(cur);
        cur = [];
        push(cmd.x, cmd.y);
        break;
      case 'L':
        push(cmd.x, cmd.y);
        break;
      case 'Q': {
        const x0 = cx;
        const y0 = cy;
        for (let i = 1; i <= steps; i++) {
          const t = i / steps;
          const mt = 1 - t;
          push(
            mt * mt * x0 + 2 * mt * t * cmd.x1 + t * t * cmd.x,
            mt * mt * y0 + 2 * mt * t * cmd.y1 + t * t * cmd.y,
          );
        }
        break;
      }
      case 'C': {
        const x0 = cx;
        const y0 = cy;
        for (let i = 1; i <= steps; i++) {
          const t = i / steps;
          const mt = 1 - t;
          push(
            mt ** 3 * x0 + 3 * mt * mt * t * cmd.x1 + 3 * mt * t * t * cmd.x2 + t ** 3 * cmd.x,
            mt ** 3 * y0 + 3 * mt * mt * t * cmd.y1 + 3 * mt * t * t * cmd.y2 + t ** 3 * cmd.y,
          );
        }
        break;
      }
      case 'Z':
        if (cur.length > 1) {
          cur.push({ ...cur[0] });
          contours.push(cur);
        }
        cur = [];
        break;
    }
  }
  if (cur.length > 1) contours.push(cur);
  return contours;
}

/**
 * Horizontal ink spans of a set of contours at a given y, using the even-odd
 * rule. Returns disjoint [start, end] pairs sorted left to right.
 */
export function spansAtY(contours: Contour[], y: number): Array<[number, number]> {
  const xs: number[] = [];
  for (const c of contours) {
    for (let i = 0; i < c.length - 1; i++) {
      const a = c[i];
      const b = c[i + 1];
      if (a.y === b.y) continue;
      const lo = Math.min(a.y, b.y);
      const hi = Math.max(a.y, b.y);
      // Half-open interval avoids double-counting shared vertices.
      if (y >= lo && y < hi) {
        xs.push(a.x + ((y - a.y) / (b.y - a.y)) * (b.x - a.x));
      }
    }
  }
  xs.sort((p, q) => p - q);
  const spans: Array<[number, number]> = [];
  for (let i = 0; i + 1 < xs.length; i += 2) spans.push([xs[i], xs[i + 1]]);
  return spans;
}

export function inkWidthAtY(contours: Contour[], y: number): number {
  return spansAtY(contours, y).reduce((sum, [a, b]) => sum + (b - a), 0);
}

export type Crossbar = {
  /** Vertical centre of the crossbar in lockup space (negative = above baseline). */
  centerY: number;
  /** Stroke weight of the crossbar. */
  thickness: number;
  /** Horizontal extents of the crossbar at its centre line. */
  left: number;
  right: number;
  /** The stem span at the crossbar's centre line. */
  stemLeft: number;
  stemRight: number;
};

/**
 * Locate the crossbar of a lowercase `t` by scanning the glyph and finding the
 * contiguous band whose ink is much wider than the stem below it.
 */
export function measureCrossbar(contours: Contour[], opts: { top: number; bottom: number }): Crossbar {
  const { top, bottom } = opts;
  const samples = 400;
  const step = (bottom - top) / samples;

  const rows: Array<{ y: number; width: number }> = [];
  for (let i = 0; i <= samples; i++) {
    const y = top + i * step;
    rows.push({ y, width: inkWidthAtY(contours, y) });
  }

  // The stem is the narrowest sustained width in the lower half of the glyph.
  const lower = rows.filter((r) => r.y > (top + bottom) / 2 && r.width > 0).map((r) => r.width);
  lower.sort((a, b) => a - b);
  const stemWidth = lower[Math.floor(lower.length * 0.25)] ?? 0;

  const threshold = stemWidth * 1.55;
  // Widest contiguous band above the threshold — that is the crossbar.
  let best: { start: number; end: number } | null = null;
  let run: { start: number; end: number } | null = null;
  for (const r of rows) {
    if (r.width >= threshold) {
      run = run ? { start: run.start, end: r.y } : { start: r.y, end: r.y };
    } else if (run) {
      if (!best || run.end - run.start > best.end - best.start) best = run;
      run = null;
    }
  }
  if (run && (!best || run.end - run.start > best.end - best.start)) best = run;
  if (!best) throw new Error('Could not locate the t crossbar — check the font file.');

  const centerY = (best.start + best.end) / 2;
  const spans = spansAtY(contours, centerY);
  const left = Math.min(...spans.map((s) => s[0]));
  const right = Math.max(...spans.map((s) => s[1]));
  // The stem is the span that survives well below the crossbar.
  const belowSpans = spansAtY(contours, Math.min(bottom - 1, best.end + (best.end - best.start)));
  const stem = belowSpans.length ? belowSpans[0] : [left, left + stemWidth];

  return {
    centerY,
    thickness: best.end - best.start,
    left,
    right,
    stemLeft: stem[0],
    stemRight: stem[1],
  };
}

export type PlacedGlyph = {
  char: string;
  /** Pen x at which the glyph was placed. */
  x: number;
  advance: number;
  /** Ink bounds in lockup space. */
  inkLeft: number;
  inkRight: number;
  inkTop: number;
  inkBottom: number;
  contours: Contour[];
  path: Path;
};

/**
 * Set `text` glyph by glyph so we know exactly where every letter sits.
 * `tracking` is in em (the guide specifies -0.03).
 */
export function layout(font: Font, text: string, tracking: number): { glyphs: PlacedGlyph[]; advance: number } {
  const upm = font.unitsPerEm;
  const track = tracking * upm;
  const glyphs: PlacedGlyph[] = [];
  let pen = 0;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const glyph = font.charToGlyph(ch);
    // getPath flips y so the result is already in lockup space.
    const path = glyph.getPath(pen, 0, upm);
    const contours = flatten(path);
    const bb = glyph.getBoundingBox();
    glyphs.push({
      char: ch,
      x: pen,
      advance: glyph.advanceWidth ?? 0,
      inkLeft: pen + bb.x1,
      inkRight: pen + bb.x2,
      inkTop: -bb.y2,
      inkBottom: -bb.y1,
      contours,
      path,
    });
    let kern = 0;
    if (i + 1 < text.length) {
      kern = font.getKerningValue(glyph, font.charToGlyph(text[i + 1])) || 0;
    }
    pen += (glyph.advanceWidth ?? 0) + kern + (i + 1 < text.length ? track : 0);
  }

  return { glyphs, advance: pen };
}

export type Cubic = { p0: Pt; c1: Pt; c2: Pt; p3: Pt };

/** A straight run expressed as a cubic, so it can join a curve list. */
export function straight(p0: Pt, p3: Pt): Cubic {
  return {
    p0,
    c1: { x: p0.x + (p3.x - p0.x) / 3, y: p0.y + (p3.y - p0.y) / 3 },
    c2: { x: p0.x + (2 * (p3.x - p0.x)) / 3, y: p0.y + (2 * (p3.y - p0.y)) / 3 },
    p3,
  };
}

function cubicPoint(s: Cubic, t: number): Pt {
  const mt = 1 - t;
  const a = mt ** 3;
  const b = 3 * mt * mt * t;
  const c = 3 * mt * t * t;
  const d = t ** 3;
  return {
    x: a * s.p0.x + b * s.c1.x + c * s.c2.x + d * s.p3.x,
    y: a * s.p0.y + b * s.c1.y + c * s.c2.y + d * s.p3.y,
  };
}

function cubicTangent(s: Cubic, t: number): Pt {
  const mt = 1 - t;
  const a = 3 * mt * mt;
  const b = 6 * mt * t;
  const c = 3 * t * t;
  return {
    x: a * (s.c1.x - s.p0.x) + b * (s.c2.x - s.c1.x) + c * (s.p3.x - s.c2.x),
    y: a * (s.c1.y - s.p0.y) + b * (s.c2.y - s.c1.y) + c * (s.p3.y - s.c2.y),
  };
}

/** Catmull-Rom through waypoints, as cubic segments. */
export function smoothSegments(points: Pt[], tension = 1): Cubic[] {
  if (points.length < 2) throw new Error('need at least two waypoints');
  const p = [points[0], ...points, points[points.length - 1]];
  const out: Cubic[] = [];
  for (let i = 1; i < p.length - 2; i++) {
    const p0 = p[i - 1];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2];
    out.push({
      p0: p1,
      c1: { x: p1.x + ((p2.x - p0.x) / 6) * tension, y: p1.y + ((p2.y - p0.y) / 6) * tension },
      c2: { x: p2.x - ((p3.x - p1.x) / 6) * tension, y: p2.y - ((p3.y - p1.y) / 6) * tension },
      p3: p2,
    });
  }
  return out;
}

export type WidthKey = { at: number; w: number };

/**
 * Build a closed outline around a centreline whose stroke weight varies along
 * its length — a tapered ribbon. This is what lets the current line thread a
 * narrow gap thinly and then swell to exactly the t-crossbar's weight, so the
 * two fuse into one continuous form.
 *
 * `keys` are stroke weights at normalised arc-length positions (0..1),
 * interpolated with a smoothstep so the swell reads as water, not as a wedge.
 */
export function ribbon(segments: Cubic[], keys: WidthKey[], samplesPerSegment = 26): string {
  // Sample the centreline, keeping arc length so width tracks distance
  // travelled rather than parameter t.
  const pts: Pt[] = [];
  const tans: Pt[] = [];
  for (let i = 0; i < segments.length; i++) {
    const last = i === segments.length - 1;
    const steps = samplesPerSegment;
    for (let j = 0; j <= steps; j++) {
      if (j === 0 && i > 0) continue; // shared vertex
      const t = j / steps;
      pts.push(cubicPoint(segments[i], t));
      tans.push(cubicTangent(segments[i], t));
      if (last && j === steps) break;
    }
  }

  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
  }
  const total = cum[cum.length - 1] || 1;

  const sorted = [...keys].sort((a, b) => a.at - b.at);
  const widthAt = (s: number) => {
    if (s <= sorted[0].at) return sorted[0].w;
    if (s >= sorted[sorted.length - 1].at) return sorted[sorted.length - 1].w;
    for (let i = 0; i < sorted.length - 1; i++) {
      const a = sorted[i];
      const b = sorted[i + 1];
      if (s >= a.at && s <= b.at) {
        const u = (s - a.at) / (b.at - a.at || 1);
        const e = u * u * (3 - 2 * u); // smoothstep
        return a.w + (b.w - a.w) * e;
      }
    }
    return sorted[sorted.length - 1].w;
  };

  const left: Pt[] = [];
  const right: Pt[] = [];
  const halves: number[] = [];
  for (let i = 0; i < pts.length; i++) {
    const t = tans[i];
    const len = Math.hypot(t.x, t.y) || 1;
    // Left-hand normal in a y-down space.
    const nx = -t.y / len;
    const ny = t.x / len;
    const half = widthAt(cum[i] / total) / 2;
    halves.push(half);
    left.push({ x: pts[i].x + nx * half, y: pts[i].y + ny * half });
    right.push({ x: pts[i].x - nx * half, y: pts[i].y - ny * half });
  }

  const n = (v: number) => Number(v.toFixed(1)).toString();

  /** Semicircular cap swept the short way round, through the travel direction. */
  const cap = (center: Pt, from: Pt, tangent: Pt, radius: number, steps = 10) => {
    const a0 = Math.atan2(from.y - center.y, from.x - center.x);
    const af = Math.atan2(tangent.y, tangent.x);
    const norm = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
    // Sweep in whichever direction passes through the tangent.
    const sign = Math.abs(norm(a0 + Math.PI / 2 - af)) < Math.abs(norm(a0 - Math.PI / 2 - af)) ? 1 : -1;
    let d = '';
    for (let k = 1; k <= steps; k++) {
      const a = a0 + sign * (k / steps) * Math.PI;
      d += `L${n(center.x + Math.cos(a) * radius)} ${n(center.y + Math.sin(a) * radius)}`;
    }
    return d;
  };

  const lastIdx = pts.length - 1;
  let d = `M${n(left[0].x)} ${n(left[0].y)}`;
  for (let i = 1; i < left.length; i++) d += `L${n(left[i].x)} ${n(left[i].y)}`;
  d += cap(pts[lastIdx], left[lastIdx], tans[lastIdx], halves[lastIdx]);
  for (let i = right.length - 2; i >= 0; i--) d += `L${n(right[i].x)} ${n(right[i].y)}`;
  d += cap(pts[0], right[0], { x: -tans[0].x, y: -tans[0].y }, halves[0]);
  return `${d}Z`;
}

/** Total arc length of each segment, and the cumulative normalised boundaries. */
export function segmentBoundaries(segments: Cubic[], steps = 40): number[] {
  const lengths = segments.map((s) => {
    let len = 0;
    let prev = cubicPoint(s, 0);
    for (let j = 1; j <= steps; j++) {
      const cur = cubicPoint(s, j / steps);
      len += Math.hypot(cur.x - prev.x, cur.y - prev.y);
      prev = cur;
    }
    return len;
  });
  const total = lengths.reduce((a, b) => a + b, 0) || 1;
  const out = [0];
  let acc = 0;
  for (const l of lengths) {
    acc += l;
    out.push(acc / total);
  }
  return out;
}

/** Round path numbers so generated SVG stays diff-friendly. */
export function pathToString(path: Path, precision = 2): string {
  const n = (v: number) => Number(v.toFixed(precision)).toString();
  return (path.commands as PathCommand[])
    .map((c) => {
      switch (c.type) {
        case 'M':
          return `M${n(c.x)} ${n(c.y)}`;
        case 'L':
          return `L${n(c.x)} ${n(c.y)}`;
        case 'Q':
          return `Q${n(c.x1)} ${n(c.y1)} ${n(c.x)} ${n(c.y)}`;
        case 'C':
          return `C${n(c.x1)} ${n(c.y1)} ${n(c.x2)} ${n(c.y2)} ${n(c.x)} ${n(c.y)}`;
        case 'Z':
          return 'Z';
        default:
          return '';
      }
    })
    .join('');
}
