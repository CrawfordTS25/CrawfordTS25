/**
 * The brand system, rendered from the same tokens and geometry the product uses.
 * If something drifts here, it has drifted in the app too — that is the point of
 * having this page.
 */

import { CurrentLine, GlyphMark, LiveNow, Wordmark } from '../brand/marks';
import { metrics, minSize } from '../brand/geometry';
import { tokens } from '../brand/tokens';

export function Brand() {
  const colors = Object.entries(tokens.color);
  const scale = Object.entries(tokens.typography.scale);

  return (
    <div className="wrap page stack" style={{ gap: 'var(--space-7)' }}>
      <header className="stack" style={{ gap: 'var(--space-4)', maxWidth: '62ch' }}>
        <span className="label faint">Brand guide v{tokens.$meta.version} · identity spec</span>
        <h1 className="h1">The identity, as built</h1>
        <p className="muted" style={{ margin: 0 }}>
          Three meanings at once: a river current, the current moment, electric current. Every value on
          this page is read from <code>brand/tokens.json</code>, and every mark is drawn from the
          measured font outlines — so this is the product, not a picture of it.
        </p>
      </header>

      {/* ── Wordmark ─────────────────────────────────────────────────────── */}
      <section className="stack" style={{ gap: 'var(--space-5)' }}>
        <h2 className="h2">Wordmark</h2>
        <p className="muted small" style={{ margin: 0, maxWidth: '62ch' }}>
          Always lowercase. The current line ripples beneath the word, rises on the right, and flows
          into the crossbar of the t, cresting in the spark. The line and the crossbar are one
          continuous tapered form — the line thins to slip behind the n, then swells to exactly the
          crossbar&apos;s measured weight of {metrics.crossbar.thickness} units.
        </p>

        <div className="card card-pad" style={{ background: 'var(--c-abyss)' }}>
          <span className="label faint">Primary · on dark</span>
          <div style={{ marginTop: 'var(--space-4)' }}>
            <Wordmark width={420} />
          </div>
        </div>

        <div className="card card-pad" style={{ background: 'var(--c-foam)' }}>
          <span className="label" style={{ color: 'var(--c-ink-on-light)', opacity: 0.6 }}>
            On light
          </span>
          <div style={{ marginTop: 'var(--space-4)' }} data-theme="light">
            <Wordmark width={420} />
          </div>
        </div>

        <div className="card card-pad" style={{ background: 'var(--c-tide)', color: 'var(--c-ink)' }}>
          <span className="label faint">Monochrome</span>
          <div style={{ marginTop: 'var(--space-4)' }}>
            <Wordmark width={420} mono />
          </div>
        </div>

        <div className="card card-pad stack" style={{ gap: 'var(--space-4)' }}>
          <span className="label faint">Clearspace &amp; minimum size</span>
          <p className="muted small" style={{ margin: 0 }}>
            Keep clear area equal to the height of the “c” on all four sides. The wordmark never goes
            below {minSize.wordmarkWidth}px wide on screen; the icon floor is {minSize.icon}px, and
            below that the amber wave is dropped and the C stands alone.
          </p>
          <div
            className="row wrap-row"
            style={{ gap: 'var(--space-5)', alignItems: 'flex-end' }}
          >
            <span style={{ outline: '1px dashed var(--hairline-strong)' }}>
              <Wordmark width={240} clearspace />
            </span>
            <span style={{ outline: '1px dashed var(--hairline-strong)' }}>
              <Wordmark width={minSize.wordmarkWidth} />
            </span>
          </div>
        </div>
      </section>

      {/* ── Colour ───────────────────────────────────────────────────────── */}
      <section className="stack" style={{ gap: 'var(--space-4)' }}>
        <h2 className="h2">Colour</h2>
        <p className="muted small" style={{ margin: 0, maxWidth: '62ch' }}>
          The cool water gradient carries the brand. Spark amber is the only warm colour and appears
          sparingly — the live indicator, the wave crest, key calls to action. One spark per view.
        </p>
        <div className="swatches">
          {colors.map(([name, c]) => (
            <div key={name} className="swatch">
              <div className="swatch-chip" style={{ background: c.value }} />
              <div className="swatch-meta stack" style={{ gap: 2 }}>
                <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                  {name.replace(/([A-Z])/g, ' $1')}
                </span>
                <span className="faint tnum">{c.value}</span>
                <span className="faint">{c.role}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ height: 84, background: 'var(--gradient-water)' }} />
          <div className="swatch-meta faint">
            {`linear-gradient(${tokens.gradient.angle}deg, ${tokens.gradient.onDark.join(' → ')})`}
          </div>
          <div style={{ height: 84, background: 'var(--gradient-water-light)' }} />
          <div className="swatch-meta faint">
            {`on light: ${tokens.gradient.onLight.join(' → ')}`}
          </div>
        </div>
      </section>

      {/* ── Typography ───────────────────────────────────────────────────── */}
      <section className="stack" style={{ gap: 'var(--space-4)' }}>
        <h2 className="h2">Typography</h2>
        <p className="muted small" style={{ margin: 0, maxWidth: '62ch' }}>
          {tokens.typography.display.family} for the wordmark and headlines only;{' '}
          {tokens.typography.ui.family} for everything else. One rule keeps it calm — the characterful
          face stays rare so it always feels intentional.
        </p>
        <div className="card card-pad stack">
          {scale.map(([name, s]) => (
            <div key={name} className="spec">
              <span className="label faint">
                {name} · {s.font === 'display' ? tokens.typography.display.family : tokens.typography.ui.family} ·{' '}
                {s.weight} · {s.min === s.max ? `${s.min}px` : `${s.min}–${s.max}px`} ·{' '}
                {s.tracking > 0 ? `+${s.tracking * 100}%` : `${s.tracking * 100}%`}
              </span>
              <span
                className={name === 'h1' || name === 'h2' ? `h${name[1]}` : name === 'label' ? 'label' : ''}
                style={{
                  fontFamily: s.font === 'display' ? 'var(--font-display)' : 'var(--font-ui)',
                  fontSize: `var(--type-${name}-size)`,
                  fontWeight: s.weight,
                  letterSpacing: `${s.tracking}em`,
                  lineHeight: s.leading,
                }}
              >
                {name === 'label' ? 'Eyebrow / label' : 'Catch the current'}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Motifs ───────────────────────────────────────────────────────── */}
      <section className="stack" style={{ gap: 'var(--space-4)' }}>
        <h2 className="h2">The signature motif</h2>
        <div className="card card-pad stack" style={{ gap: 'var(--space-6)' }}>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <span className="label faint">Current line · dividers</span>
            <CurrentLine height={20} />
          </div>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <span className="label faint">Current line · progress</span>
            <CurrentLine progress={0.42} height={20} aria-label="Example progress" />
          </div>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <span className="label faint">Current line · loading, flowing</span>
            <CurrentLine flowing height={20} />
          </div>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <span className="label faint">The spark · on air</span>
            <span className="row wrap-row" style={{ gap: 'var(--space-3)' }}>
              <LiveNow />
              <LiveNow tone="cool" label="Also live" />
            </span>
          </div>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <span className="label faint">C-current glyph · favicon, app icon, avatar, watermark</span>
            <span className="row" style={{ gap: 'var(--space-4)', alignItems: 'flex-end' }}>
              <GlyphMark size={96} plate />
              <GlyphMark size={48} plate />
              <GlyphMark size={32} plate />
              <GlyphMark size={20} plate />
              <span className="faint small">96 · 48 · 32 · 20 (wave dropped)</span>
            </span>
          </div>
        </div>
      </section>

      {/* ── Voice, do & don't ────────────────────────────────────────────── */}
      <section className="stack" style={{ gap: 'var(--space-4)' }}>
        <h2 className="h2">Voice &amp; language</h2>
        <p className="muted" style={{ margin: 0, maxWidth: '62ch' }}>
          {tokens.voice.tone}
        </p>
        <div className="row wrap-row" style={{ gap: 'var(--space-2)' }}>
          {tokens.voice.vocabulary.map((v) => (
            <span key={v} className="tag">
              {v}
            </span>
          ))}
        </div>
      </section>

      <section className="rules">
        <div className="card card-pad stack" style={{ gap: 'var(--space-3)' }}>
          <span className="label" style={{ color: 'var(--c-aqua)' }}>
            Do
          </span>
          <ul className="rule-list">
            {tokens.rules.slice(0, 5).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <div className="card card-pad stack" style={{ gap: 'var(--space-3)' }}>
          <span className="label muted">Don&apos;t</span>
          <ul className="rule-list">
            {tokens.rules.slice(5).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
