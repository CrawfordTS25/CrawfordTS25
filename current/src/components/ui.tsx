/** Small shared pieces: avatars, stats, tags, notices, loading states. */

import type { ReactNode } from 'react';
import { CurrentLine } from '../brand/marks';
import { compact } from '../lib/format';

export function Avatar({
  name,
  hue,
  size = 40,
  ring = false,
}: {
  name: string;
  hue: number;
  size?: number;
  ring?: boolean;
}) {
  const initials = name
    .replace(/[^\p{L}\p{N} .]/gu, '')
    .split(/[\s.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');

  return (
    <span
      className={`avatar${ring ? ' avatar-ring' : ''}`}
      style={
        {
          width: size,
          height: size,
          fontSize: Math.max(10, size * 0.38),
          '--avatar-hue': hue,
        } as React.CSSProperties
      }
      aria-hidden="true"
    >
      {initials || '~'}
    </span>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="stat">
      <span className="stat-value">{value}</span>
      <span className="label faint">{label}</span>
    </span>
  );
}

export function Tags({ items, max = 4 }: { items: string[]; max?: number }) {
  return (
    <span className="tag-row">
      {items.slice(0, max).map((t) => (
        <span key={t} className="tag">
          {t}
        </span>
      ))}
    </span>
  );
}

export function Listeners({ count }: { count: number | null }) {
  if (count === null) return <span className="faint small">counting the room…</span>;
  return (
    <span className="small tnum">
      {compact(count)} {count === 1 ? 'listener' : 'listeners'}
    </span>
  );
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  return (
    <p className="notice" role={tone === 'warn' ? 'alert' : 'status'} style={{ margin: 0 }}>
      {children}
    </p>
  );
}

/** Loading state — the current line, flowing. */
export function Loading({ label = 'Finding the current…' }: { label?: string }) {
  return (
    <div className="stack" style={{ gap: 'var(--space-4)', padding: 'var(--space-7) 0' }} role="status">
      <CurrentLine flowing height={22} />
      <p className="muted small" style={{ margin: 0, textAlign: 'center' }}>
        {label}
      </p>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card card-pad stack" style={{ gap: 'var(--space-2)', textAlign: 'center' }}>
      <p className="h3" style={{ margin: 0 }}>
        {title}
      </p>
      {children && (
        <p className="muted small" style={{ margin: 0 }}>
          {children}
        </p>
      )}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="card card-pad stack" style={{ gap: 'var(--space-4)' }} role="alert">
      <p className="h3" style={{ margin: 0 }}>
        Lost the signal
      </p>
      <p className="muted small" style={{ margin: 0 }}>
        {error}
      </p>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry} style={{ alignSelf: 'start' }}>
          Try again
        </button>
      )}
    </div>
  );
}
