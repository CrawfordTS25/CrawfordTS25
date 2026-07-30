/**
 * Identity without a signup wall. A live room should not ask you to make an
 * account before you can hear anything, so we mint a local id on first visit
 * and let you name yourself whenever you feel like it.
 */

const KEY = 'current.userId';

function mint(): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export function userId(): string {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing && /^[A-Za-z0-9_-]{6,64}$/.test(existing)) return existing;
    const id = mint();
    localStorage.setItem(KEY, id);
    return id;
  } catch {
    // Private mode with storage blocked: stay usable for this session only.
    return mint();
  }
}
