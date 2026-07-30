/** Small formatters. The voice is direct and warm — never "0 listeners online". */

export function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  if (n < 1_000_000) return `${Math.round(n / 1000)}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}m`;
}

export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return `${m}:${String(rem).padStart(2, '0')}`;
  const h = Math.floor(m / 60);
  return `${h}:${String(m % 60).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

/** "47 min in" / "3 hr 12 min in" — how deep into a live set we are. */
export function elapsedSince(startedAt: number, now = Date.now()): string {
  const mins = Math.max(0, Math.floor((now - startedAt) / 60_000));
  if (mins < 1) return 'just started';
  if (mins < 60) return `${mins} min in`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h} hr in` : `${h} hr ${m} min in`;
}

/** "in 2 hr" / "tomorrow" — when an upcoming set opens its doors. */
export function untilStart(scheduledAt: number, now = Date.now()): string {
  const mins = Math.round((scheduledAt - now) / 60_000);
  if (mins <= 0) return 'starting now';
  if (mins < 60) return `in ${mins} min`;
  const h = Math.round(mins / 60);
  if (h < 24) return `in ${h} hr`;
  const d = Math.round(h / 24);
  return d === 1 ? 'tomorrow' : `in ${d} days`;
}

export function timeOfDay(ts: number): string {
  return new Date(ts).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}
