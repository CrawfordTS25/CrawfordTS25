/**
 * The brand marks, drawn from the measured geometry in `./geometry.ts` (which
 * `npm run brand:build` regenerates from the font outlines). Rendering them
 * inline rather than as <img> means they inherit the theme's gradient stops and
 * can animate.
 *
 * Guide rules enforced here, not left to the caller:
 *   · the wordmark is lowercase, never restyled, never skewed;
 *   · clearspace equals the height of the "c" on all four sides;
 *   · below the 24px icon floor the amber wave is dropped and the C stands alone;
 *   · nothing gets a shadow, outline, glow or bevel.
 */

import { useId } from 'react';
import { clearspaceRatio, currentLineMotif, glyphMark, minSize, wordmark } from './geometry';

const ANGLE = 100; // the guide's gradient angle

type Box = { x: number; y: number; w: number; h: number };

/** CSS gradient angles run clockwise from "to top"; SVG needs endpoints. */
function gradientEnds(box: Box, angleDeg = ANGLE) {
  const rad = (angleDeg * Math.PI) / 180;
  const dx = Math.sin(rad);
  const dy = -Math.cos(rad);
  const len = Math.abs(box.w * dx) + Math.abs(box.h * dy);
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  return {
    x1: cx - (dx * len) / 2,
    y1: cy - (dy * len) / 2,
    x2: cx + (dx * len) / 2,
    y2: cy + (dy * len) / 2,
  };
}

/**
 * The water gradient in user space, so a shape's colour depends only on where
 * it sits — which is what lets the current line and the t-crossbar meet with no
 * visible seam.
 */
function WaterGradient({ id, box }: { id: string; box: Box }) {
  const { x1, y1, x2, y2 } = gradientEnds(box);
  return (
    <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x2} y2={y2}>
      <stop offset="0%" stopColor="var(--wm-stop-1)" />
      <stop offset="52%" stopColor="var(--wm-stop-2)" />
      <stop offset="100%" stopColor="var(--wm-stop-3)" />
    </linearGradient>
  );
}

/* ──────────────────────────────────────────────────────────────── wordmark ── */

export type WordmarkProps = {
  /** Rendered width in px. Clamped to the 96px minimum from the guide. */
  width?: number;
  /** Monochrome lockup — inherits currentColor. */
  mono?: boolean;
  /** Reserve the guide's clearspace (the height of the "c") around the mark. */
  clearspace?: boolean;
  title?: string;
  className?: string;
};

export function Wordmark({
  width = 168,
  mono = false,
  clearspace = false,
  title = 'current',
  className,
}: WordmarkProps) {
  const id = useId();
  const gradId = `water${id}`;
  const maskId = `behind${id}`;
  const vb = wordmark.viewBox;

  const w = Math.max(width, minSize.wordmarkWidth);
  const pad = clearspace ? clearspaceRatio * vb.h : 0;
  const box: Box = {
    x: vb.x - pad,
    y: vb.y - pad,
    w: vb.w + pad * 2,
    h: vb.h + pad * 2,
  };
  const paint = mono ? 'currentColor' : `url(#${gradId})`;

  return (
    <svg
      className={className}
      viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`}
      width={w}
      height={(w * box.h) / box.w}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        {!mono && <WaterGradient id={gradId} box={vb} />}
        {/* Opens a hairline of air where the climbing line crosses the n. */}
        <mask id={maskId} maskUnits="userSpaceOnUse" x={box.x} y={box.y} width={box.w} height={box.h}>
          <rect x={box.x} y={box.y} width={box.w} height={box.h} fill="#fff" />
          <path
            d={wordmark.knockout}
            fill="#000"
            stroke="#000"
            strokeWidth={wordmark.knockoutWidth}
            strokeLinejoin="round"
          />
        </mask>
      </defs>
      <path d={wordmark.currentLine} fill={paint} mask={`url(#${maskId})`} />
      <path d={wordmark.letters} fill={paint} />
      <circle
        cx={wordmark.spark.x}
        cy={wordmark.spark.y}
        r={wordmark.spark.r}
        fill={mono ? 'currentColor' : 'var(--c-spark)'}
      />
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────── C-current mark ── */

export type GlyphMarkProps = {
  size?: number;
  /** Draw the Abyss rounded-square plate behind the mark. */
  plate?: boolean;
  /**
   * Force the amber wave off. Watermarks are drawn at low opacity, where amber
   * muddies into olive — and the guide's warm accent is meant to be spent on the
   * live indicator, not on decoration.
   */
  wave?: boolean;
  className?: string;
  title?: string;
};

/**
 * The C-current glyph — favicon, avatar fallback, watermark. Under the 24px
 * floor the amber wave is dropped automatically and the C stands alone, exactly
 * as the guide requires.
 */
export function GlyphMark({
  size = 32,
  plate = false,
  wave,
  className,
  title = 'current',
}: GlyphMarkProps) {
  const id = useId();
  const gradId = `glyph${id}`;
  const withWave = wave ?? size >= minSize.icon;
  const box: Box = { x: 0, y: 0, w: 100, h: 100 };

  const fit = withWave ? glyphMark.markBox : glyphMark.letterBox;
  const inset = withWave ? 17 : 24;
  const avail = 100 - inset * 2;
  const lw = fit.right - fit.left;
  const lh = fit.bottom - fit.top;
  const scale = avail / Math.max(lw, lh);
  const tx = inset + (avail - lw * scale) / 2 - fit.left * scale;
  const ty = inset + (avail - lh * scale) / 2 - fit.top * scale;

  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <WaterGradient id={gradId} box={box} />
      </defs>
      {plate && <rect x="0" y="0" width="100" height="100" rx="24" fill="var(--c-abyss)" />}
      <g transform={`translate(${tx} ${ty}) scale(${scale})`}>
        <path d={glyphMark.letter} fill={`url(#${gradId})`} />
        {withWave && (
          <>
            <path
              d={glyphMark.wave}
              fill="none"
              stroke="var(--c-spark)"
              strokeWidth={glyphMark.strokeWidth}
              strokeLinecap="round"
            />
            <circle
              cx={glyphMark.spark.x}
              cy={glyphMark.spark.y}
              r={glyphMark.spark.r}
              fill="var(--c-spark)"
            />
          </>
        )}
      </g>
    </svg>
  );
}

/* ────────────────────────────────────────────────── the current-line motif ── */

export type CurrentLineProps = {
  /** 0..1. When omitted the line is a full-width divider. */
  progress?: number;
  /** Animate the wave sideways — loading and buffering states. */
  flowing?: boolean;
  height?: number;
  className?: string;
  'aria-label'?: string;
};

/**
 * Section dividers, progress bars, loading states — the guide's signature
 * motif. With `progress` it becomes a scrub bar whose filled portion is the
 * water gradient and whose remainder is a hairline.
 */
export function CurrentLine({
  progress,
  flowing = false,
  height = 18,
  className,
  ...rest
}: CurrentLineProps) {
  const id = useId();
  const gradId = `line${id}`;
  const clipId = `clip${id}`;
  const box = currentLineMotif.viewBox;
  const isBar = typeof progress === 'number';
  const pct = isBar ? Math.min(1, Math.max(0, progress)) : 1;

  return (
    <svg
      className={className}
      viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`}
      height={height}
      width="100%"
      preserveAspectRatio="none"
      role={isBar ? 'progressbar' : 'presentation'}
      aria-valuenow={isBar ? Math.round(pct * 100) : undefined}
      aria-valuemin={isBar ? 0 : undefined}
      aria-valuemax={isBar ? 100 : undefined}
      {...rest}
    >
      <defs>
        <WaterGradient id={gradId} box={box} />
        <clipPath id={clipId}>
          <rect x={box.x} y={box.y} width={box.w * pct} height={box.h} />
        </clipPath>
      </defs>
      {isBar && (
        <path
          d={currentLineMotif.d}
          fill="none"
          stroke="var(--hairline-strong)"
          strokeWidth={2.4}
          strokeLinecap="round"
        />
      )}
      <g clipPath={`url(#${clipId})`}>
        <path
          d={currentLineMotif.d}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth={isBar ? 3 : 2.2}
          strokeLinecap="round"
          className={flowing ? 'current-line-flow' : undefined}
        />
      </g>
    </svg>
  );
}

/* ───────────────────────────────────────────────────────────────── the spark ── */

export type LiveNowProps = {
  /**
   * The amber spark is the live indicator — and the guide allows one warm
   * accent per view. Secondary live markers pass `tone="cool"`.
   */
  tone?: 'spark' | 'cool';
  label?: string;
  className?: string;
};

export function LiveNow({ tone = 'spark', label = 'Live now', className }: LiveNowProps) {
  return (
    <span className={`live live-${tone} ${className ?? ''}`}>
      <span className="live-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
