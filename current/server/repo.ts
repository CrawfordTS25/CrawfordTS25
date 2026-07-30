/**
 * Query layer. Everything the API and the live hub need to read or write,
 * expressed as plain functions over a database handle so they are trivial to
 * test in isolation.
 */

import type { DB } from './db';

export type Creator = {
  id: number;
  handle: string;
  name: string;
  tagline: string;
  bio: string;
  city: string;
  genres: string[];
  hue: number;
  followers: number;
};

export type Track = {
  id: number;
  title: string;
  durationS: number;
  plays: number;
  position: number;
};

export type Stream = {
  id: number;
  slug: string;
  title: string;
  blurb: string;
  tags: string[];
  isLive: boolean;
  startedAt: number;
  scheduledAt: number | null;
  listenerBase: number;
  peakListeners: number;
  creator: Creator;
};

export type Message = {
  id: number;
  streamId: number;
  userId: string;
  author: string;
  body: string;
  createdAt: number;
};

const CREATOR_COLS = `
  c.id, c.handle, c.name, c.tagline, c.bio, c.city, c.genres, c.hue, c.follower_base,
  (SELECT COUNT(*) FROM follows f WHERE f.creator_id = c.id) AS follow_count
`;

type CreatorRow = {
  id: number;
  handle: string;
  name: string;
  tagline: string;
  bio: string;
  city: string;
  genres: string;
  hue: number;
  follower_base: number;
  follow_count: number;
};

function toCreator(r: CreatorRow): Creator {
  return {
    id: r.id,
    handle: r.handle,
    name: r.name,
    tagline: r.tagline,
    bio: r.bio,
    city: r.city,
    genres: JSON.parse(r.genres),
    hue: r.hue,
    followers: r.follower_base + r.follow_count,
  };
}

type StreamRow = CreatorRow & {
  s_id: number;
  slug: string;
  title: string;
  blurb: string;
  tags: string;
  is_live: number;
  started_at: number;
  scheduled_at: number | null;
  listener_base: number;
  peak_listeners: number;
};

function toStream(r: StreamRow): Stream {
  return {
    id: r.s_id,
    slug: r.slug,
    title: r.title,
    blurb: r.blurb,
    tags: JSON.parse(r.tags),
    isLive: !!r.is_live,
    startedAt: r.started_at,
    scheduledAt: r.scheduled_at,
    listenerBase: r.listener_base,
    peakListeners: r.peak_listeners,
    creator: toCreator(r),
  };
}

const STREAM_SELECT = `
  SELECT s.id AS s_id, s.slug, s.title, s.blurb, s.tags, s.is_live, s.started_at,
         s.scheduled_at, s.listener_base, s.peak_listeners, ${CREATOR_COLS}
  FROM streams s JOIN creators c ON c.id = s.creator_id
`;

export function listStreams(db: DB, filter: 'live' | 'upcoming' | 'all' = 'all'): Stream[] {
  const where =
    filter === 'live' ? 'WHERE s.is_live = 1' : filter === 'upcoming' ? 'WHERE s.is_live = 0' : '';
  const order =
    filter === 'upcoming'
      ? 'ORDER BY s.scheduled_at ASC'
      : 'ORDER BY s.is_live DESC, s.listener_base DESC';
  const rows = db.prepare(`${STREAM_SELECT} ${where} ${order}`).all() as StreamRow[];
  return rows.map(toStream);
}

export function getStreamBySlug(db: DB, slug: string): Stream | null {
  const row = db.prepare(`${STREAM_SELECT} WHERE s.slug = ?`).get(slug) as StreamRow | undefined;
  return row ? toStream(row) : null;
}

export function getStreamById(db: DB, id: number): Stream | null {
  const row = db.prepare(`${STREAM_SELECT} WHERE s.id = ?`).get(id) as StreamRow | undefined;
  return row ? toStream(row) : null;
}

export function listCreators(db: DB): Creator[] {
  const rows = db
    .prepare(`SELECT ${CREATOR_COLS} FROM creators c ORDER BY c.follower_base DESC`)
    .all() as CreatorRow[];
  return rows.map(toCreator);
}

export function getCreatorByHandle(db: DB, handle: string): Creator | null {
  const row = db.prepare(`SELECT ${CREATOR_COLS} FROM creators c WHERE c.handle = ?`).get(handle) as
    | CreatorRow
    | undefined;
  return row ? toCreator(row) : null;
}

export function listTracks(db: DB, creatorId: number): Track[] {
  const rows = db
    .prepare(
      `SELECT id, title, duration_s, plays, position FROM tracks
       WHERE creator_id = ? ORDER BY position ASC`,
    )
    .all(creatorId) as Array<{
    id: number;
    title: string;
    duration_s: number;
    plays: number;
    position: number;
  }>;
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    durationS: r.duration_s,
    plays: r.plays,
    position: r.position,
  }));
}

export function listStreamsByCreator(db: DB, creatorId: number): Stream[] {
  const rows = db
    .prepare(`${STREAM_SELECT} WHERE s.creator_id = ? ORDER BY s.is_live DESC`)
    .all(creatorId) as StreamRow[];
  return rows.map(toStream);
}

/* ────────────────────────────────────────────────────────────────── users ── */

export function upsertUser(db: DB, id: string, displayName?: string) {
  const now = Date.now();
  const existing = db.prepare('SELECT id, display_name FROM users WHERE id = ?').get(id) as
    | { id: string; display_name: string }
    | undefined;
  if (!existing) {
    const name = displayName?.trim() || `listener_${id.slice(0, 4)}`;
    db.prepare('INSERT INTO users (id, display_name, created_at) VALUES (?, ?, ?)').run(id, name, now);
    return { id, displayName: name };
  }
  if (displayName && displayName.trim() && displayName.trim() !== existing.display_name) {
    db.prepare('UPDATE users SET display_name = ? WHERE id = ?').run(displayName.trim(), id);
    return { id, displayName: displayName.trim() };
  }
  return { id, displayName: existing.display_name };
}

export function getUser(db: DB, id: string) {
  const row = db.prepare('SELECT id, display_name FROM users WHERE id = ?').get(id) as
    | { id: string; display_name: string }
    | undefined;
  return row ? { id: row.id, displayName: row.display_name } : null;
}

/* ──────────────────────────────────────────────────────────────── follows ── */

export function isFollowing(db: DB, userId: string, creatorId: number): boolean {
  const row = db
    .prepare('SELECT 1 AS x FROM follows WHERE user_id = ? AND creator_id = ?')
    .get(userId, creatorId) as { x: number } | undefined;
  return !!row;
}

export function setFollow(db: DB, userId: string, creatorId: number, following: boolean) {
  if (following) {
    db.prepare(
      'INSERT OR IGNORE INTO follows (user_id, creator_id, created_at) VALUES (?, ?, ?)',
    ).run(userId, creatorId, Date.now());
  } else {
    db.prepare('DELETE FROM follows WHERE user_id = ? AND creator_id = ?').run(userId, creatorId);
  }
}

export function listFollowedCreatorIds(db: DB, userId: string): number[] {
  const rows = db.prepare('SELECT creator_id FROM follows WHERE user_id = ?').all(userId) as Array<{
    creator_id: number;
  }>;
  return rows.map((r) => r.creator_id);
}

/* ─────────────────────────────────────────────────────────────── messages ── */

export function listMessages(db: DB, streamId: number, limit = 80): Message[] {
  const rows = db
    .prepare(
      `SELECT id, stream_id, user_id, author, body, created_at FROM messages
       WHERE stream_id = ? ORDER BY id DESC LIMIT ?`,
    )
    .all(streamId, limit) as Array<{
    id: number;
    stream_id: number;
    user_id: string;
    author: string;
    body: string;
    created_at: number;
  }>;
  return rows
    .map((r) => ({
      id: r.id,
      streamId: r.stream_id,
      userId: r.user_id,
      author: r.author,
      body: r.body,
      createdAt: r.created_at,
    }))
    .reverse();
}

export function addMessage(
  db: DB,
  input: { streamId: number; userId: string; author: string; body: string },
): Message {
  const now = Date.now();
  const info = db
    .prepare(
      'INSERT INTO messages (stream_id, user_id, author, body, created_at) VALUES (?, ?, ?, ?, ?)',
    )
    .run(input.streamId, input.userId, input.author, input.body, now);
  return {
    id: Number(info.lastInsertRowid),
    streamId: input.streamId,
    userId: input.userId,
    author: input.author,
    body: input.body,
    createdAt: now,
  };
}

/* ───────────────────────────────────────────────────────────────── sparks ── */

export function addSpark(db: DB, streamId: number, userId: string) {
  db.prepare('INSERT INTO sparks (stream_id, user_id, created_at) VALUES (?, ?, ?)').run(
    streamId,
    userId,
    Date.now(),
  );
}

export function countSparks(db: DB, streamId: number): number {
  const row = db.prepare('SELECT COUNT(*) AS c FROM sparks WHERE stream_id = ?').get(streamId) as {
    c: number;
  };
  return row.c;
}

export function updatePeak(db: DB, streamId: number, listeners: number) {
  db.prepare('UPDATE streams SET peak_listeners = MAX(peak_listeners, ?) WHERE id = ?').run(
    listeners,
    streamId,
  );
}

/* ───────────────────────────────────────────────────────────────── search ── */

/**
 * Escape LIKE metacharacters so a query of "%" looks for a literal percent sign
 * instead of matching the entire catalogue.
 */
function likePattern(q: string): string {
  const escaped = q.toLowerCase().replace(/[\\%_]/g, (ch) => `\\${ch}`);
  return `%${escaped}%`;
}

export function search(db: DB, q: string) {
  const like = likePattern(q);
  const creators = (
    db
      .prepare(
        `SELECT ${CREATOR_COLS} FROM creators c
         WHERE lower(c.name) LIKE ? ESCAPE '\\' OR lower(c.handle) LIKE ? ESCAPE '\\'
            OR lower(c.genres) LIKE ? ESCAPE '\\' OR lower(c.city) LIKE ? ESCAPE '\\'
            OR lower(c.tagline) LIKE ? ESCAPE '\\'
         ORDER BY c.follower_base DESC LIMIT 12`,
      )
      .all(like, like, like, like, like) as CreatorRow[]
  ).map(toCreator);

  const streams = (
    db
      .prepare(
        `${STREAM_SELECT} WHERE lower(s.title) LIKE ? ESCAPE '\\'
            OR lower(s.tags) LIKE ? ESCAPE '\\' OR lower(s.blurb) LIKE ? ESCAPE '\\'
         ORDER BY s.is_live DESC, s.listener_base DESC LIMIT 12`,
      )
      .all(like, like, like) as StreamRow[]
  ).map(toStream);

  return { creators, streams };
}

/* ──────────────────────────────────────────────────────────── now playing ── */

export type NowPlaying = {
  track: Track;
  /** Seconds into the current track. */
  position: number;
  index: number;
  of: number;
};

/**
 * Where a live stream's playhead sits right now. The set loops, so a stream
 * that has been up for hours always has something playing — derived from
 * `started_at` rather than stored, so every client agrees without syncing.
 */
export function nowPlaying(db: DB, stream: Stream, at = Date.now()): NowPlaying | null {
  if (!stream.isLive) return null;
  const tracks = listTracks(db, stream.creator.id);
  if (tracks.length === 0) return null;

  const total = tracks.reduce((sum, t) => sum + t.durationS, 0);
  if (total <= 0) return null;

  const elapsed = Math.max(0, Math.floor((at - stream.startedAt) / 1000));
  let offset = elapsed % total;
  for (let i = 0; i < tracks.length; i++) {
    if (offset < tracks[i].durationS) {
      return { track: tracks[i], position: offset, index: i, of: tracks.length };
    }
    offset -= tracks[i].durationS;
  }
  return { track: tracks[0], position: 0, index: 0, of: tracks.length };
}
