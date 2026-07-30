/**
 * SQLite schema and seed for `current`.
 *
 * The database is created on demand. Pass ':memory:' (the default under test)
 * for an isolated instance, or a path to persist between restarts.
 */

import Database from 'better-sqlite3';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export type DB = Database.Database;

export function openDb(file = process.env.CURRENT_DB ?? ':memory:'): DB {
  if (file !== ':memory:') mkdirSync(dirname(file), { recursive: true });
  const db = new Database(file);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  migrate(db);
  return db;
}

export function migrate(db: DB) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id            TEXT PRIMARY KEY,
      display_name  TEXT NOT NULL,
      created_at    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS creators (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      handle        TEXT NOT NULL UNIQUE,
      name          TEXT NOT NULL,
      tagline       TEXT NOT NULL,
      bio           TEXT NOT NULL,
      city          TEXT NOT NULL,
      genres        TEXT NOT NULL,          -- JSON array
      hue           INTEGER NOT NULL,       -- avatar fallback tint, 0..360
      follower_base INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS tracks (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      creator_id  INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
      title       TEXT NOT NULL,
      duration_s  INTEGER NOT NULL,
      plays       INTEGER NOT NULL DEFAULT 0,
      position    INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS streams (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      creator_id    INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
      slug          TEXT NOT NULL UNIQUE,
      title         TEXT NOT NULL,
      blurb         TEXT NOT NULL,
      tags          TEXT NOT NULL,          -- JSON array
      is_live       INTEGER NOT NULL DEFAULT 0,
      started_at    INTEGER NOT NULL,
      scheduled_at  INTEGER,
      listener_base INTEGER NOT NULL DEFAULT 0,
      peak_listeners INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS follows (
      user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      creator_id INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
      created_at INTEGER NOT NULL,
      PRIMARY KEY (user_id, creator_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      stream_id  INTEGER NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
      user_id    TEXT NOT NULL,
      author     TEXT NOT NULL,
      body       TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sparks (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      stream_id  INTEGER NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
      user_id    TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_messages_stream ON messages(stream_id, id);
    CREATE INDEX IF NOT EXISTS idx_sparks_stream   ON sparks(stream_id);
    CREATE INDEX IF NOT EXISTS idx_tracks_creator  ON tracks(creator_id, position);
    CREATE INDEX IF NOT EXISTS idx_streams_creator ON streams(creator_id);
  `);
}

/* ───────────────────────────────────────────────────────────────────── seed ── */

type SeedCreator = {
  handle: string;
  name: string;
  tagline: string;
  bio: string;
  city: string;
  genres: string[];
  hue: number;
  followers: number;
  tracks: Array<[title: string, duration: number, plays: number]>;
  stream?: {
    slug: string;
    title: string;
    blurb: string;
    tags: string[];
    live: boolean;
    listeners: number;
    /** Minutes from now; negative means it started that long ago. */
    offsetMin: number;
  };
};

const SEED: SeedCreator[] = [
  {
    handle: 'nrissa',
    name: 'Nrissa',
    tagline: 'Late-night bass and long reverbs',
    bio: 'Producer and selector working out of a converted garage. Builds sets the way a river builds a bank — slowly, then all at once.',
    city: 'Lisbon',
    genres: ['bass', 'dub', 'ambient'],
    hue: 168,
    followers: 24800,
    tracks: [
      ['Undertow', 254, 412_000],
      ['Slack Water', 318, 288_400],
      ['Ferry at 4am', 221, 194_100],
      ['Salt Print', 276, 121_700],
    ],
    stream: {
      slug: 'nrissa-undertow-session',
      title: 'Undertow — live from the garage',
      blurb: 'Four decks, no plan. Taking requests in the chat.',
      tags: ['bass', 'improvised', 'requests open'],
      live: true,
      listeners: 1284,
      offsetMin: -47,
    },
  },
  {
    handle: 'kito.wav',
    name: 'Kito',
    tagline: 'Guitar loops that never quite resolve',
    bio: 'One guitar, three pedals, and a stubborn refusal to use a click track.',
    city: 'Osaka',
    genres: ['shoegaze', 'loop', 'post-rock'],
    hue: 196,
    followers: 9120,
    tracks: [
      ['Tidewrack', 402, 88_200],
      ['Blue Hour Practice', 351, 61_900],
      ['Feedback Garden', 289, 44_300],
    ],
    stream: {
      slug: 'kito-blue-hour',
      title: 'Blue hour practice, unedited',
      blurb: 'Just me and the loop pedal working something out.',
      tags: ['live take', 'guitar', 'quiet'],
      live: true,
      listeners: 342,
      offsetMin: -12,
    },
  },
  {
    handle: 'amaris',
    name: 'Amaris Vale',
    tagline: 'Choral electronics, one take at a time',
    bio: 'Trained as a choral conductor, now stacks her own voice forty layers deep and calls it a choir.',
    city: 'Reykjavík',
    genres: ['choral', 'electronic', 'drone'],
    hue: 232,
    followers: 51_400,
    tracks: [
      ['Forty Throats', 367, 902_000],
      ['Vigil', 445, 613_500],
      ['Antiphon', 298, 402_800],
      ['Bell Tower Demo', 187, 175_200],
    ],
    stream: {
      slug: 'amaris-vigil-listening',
      title: 'Vigil — first listen with the choir',
      blurb: 'Playing the new record start to finish, then answering everything.',
      tags: ['listening party', 'new record', 'q&a'],
      live: true,
      listeners: 5910,
      offsetMin: -103,
    },
  },
  {
    handle: 'brk',
    name: 'BRK',
    tagline: 'Breakbeat archaeology',
    bio: 'Digs through boot sales for drum records nobody wanted, then makes them unavoidable.',
    city: 'Manchester',
    genres: ['breakbeat', 'jungle', 'sample'],
    hue: 148,
    followers: 33_600,
    tracks: [
      ['Boot Sale Break', 198, 511_000],
      ['Two Quid Amen', 176, 388_700],
      ['Crate Depth', 243, 246_400],
    ],
    stream: {
      slug: 'brk-crate-depth',
      title: 'Crate depth: 90 minutes of unreleased breaks',
      blurb: 'Everything here came off vinyl this week.',
      tags: ['breaks', 'vinyl only', 'unreleased'],
      live: false,
      listeners: 0,
      offsetMin: 96,
    },
  },
  {
    handle: 'lowtide.collective',
    name: 'Low Tide Collective',
    tagline: 'Six players, one room, no overdubs',
    bio: 'A rotating ensemble that records everything live to tape in a boat shed on the estuary.',
    city: 'Cork',
    genres: ['jazz', 'ensemble', 'live'],
    hue: 210,
    followers: 14_200,
    tracks: [
      ['Estuary, First Pass', 512, 96_400],
      ['Boat Shed Blues', 388, 71_800],
      ['Six Up', 297, 52_100],
    ],
    stream: {
      slug: 'lowtide-estuary-set',
      title: 'Estuary set — live to tape',
      blurb: 'Doors at eight, tape rolls at half past.',
      tags: ['jazz', 'live to tape', 'ensemble'],
      live: false,
      listeners: 0,
      offsetMin: 1_440,
    },
  },
  {
    handle: 'sunn.circuit',
    name: 'Sunn Circuit',
    tagline: 'Modular patches, built in front of you',
    bio: 'Patches from nothing every single show. If it falls apart, that is the show too.',
    city: 'Detroit',
    genres: ['modular', 'techno', 'generative'],
    hue: 234,
    followers: 41_900,
    tracks: [
      ['Patch 61', 604, 233_900],
      ['No Undo', 421, 188_600],
      ['Voltage Bloom', 355, 142_700],
    ],
    stream: {
      slug: 'sunn-patch-from-zero',
      title: 'Patch from zero: an empty rack at midnight',
      blurb: 'Starting with nothing plugged in. Ending wherever we end.',
      tags: ['modular', 'from scratch', 'techno'],
      live: true,
      listeners: 2470,
      offsetMin: -28,
    },
  },
];

const CHAT_SEED: Record<string, Array<[author: string, body: string]>> = {
  'nrissa-undertow-session': [
    ['mila_k', 'that transition was filthy'],
    ['dorian', 'first time catching this live, been waiting months'],
    ['sef', 'is Slack Water in the set tonight?'],
    ['nrissa', 'sef: it is now'],
    ['tavi', 'the low end in this room is unreal'],
    ['june.b', 'came for one track, staying for all of it'],
  ],
  'kito-blue-hour': [
    ['harun', 'the loop drifting out of time is the best part'],
    ['ellis', 'please never quantise this'],
    ['kito', 'no click track, no mercy'],
    ['wren', 'this is my whole evening sorted'],
  ],
  'amaris-vigil-listening': [
    ['orla', 'forty layers and it still sounds like one person'],
    ['pim', 'track three broke me a little'],
    ['amaris', 'that one took nine months, so, fair'],
    ['dc.hall', 'listening on headphones in a stairwell, correct choice'],
    ['nadia', 'the room mic on Vigil, what was it?'],
    ['amaris', 'nadia: one ribbon, twelve feet up, pointed at the ceiling'],
    ['tomas', 'chills, genuinely'],
  ],
  'sunn-patch-from-zero': [
    ['reyes', 'empty rack gang'],
    ['iggy', 'watching someone find the kick in real time is so good'],
    ['sunn', 'if this collapses we all saw it together'],
    ['bex', 'the self-patching bit at 20 min, what was that module'],
    ['reyes', 'it broke and got better, incredible'],
  ],
};

export function seed(db: DB, now = Date.now()) {
  const existing = db.prepare('SELECT COUNT(*) AS c FROM creators').get() as { c: number };
  if (existing.c > 0) return;

  const insCreator = db.prepare(
    `INSERT INTO creators (handle, name, tagline, bio, city, genres, hue, follower_base)
     VALUES (@handle, @name, @tagline, @bio, @city, @genres, @hue, @followers)`,
  );
  const insTrack = db.prepare(
    `INSERT INTO tracks (creator_id, title, duration_s, plays, position)
     VALUES (?, ?, ?, ?, ?)`,
  );
  const insStream = db.prepare(
    `INSERT INTO streams (creator_id, slug, title, blurb, tags, is_live, started_at, scheduled_at, listener_base, peak_listeners)
     VALUES (@creator_id, @slug, @title, @blurb, @tags, @is_live, @started_at, @scheduled_at, @listener_base, @peak)`,
  );
  const insMessage = db.prepare(
    `INSERT INTO messages (stream_id, user_id, author, body, created_at) VALUES (?, ?, ?, ?, ?)`,
  );

  db.transaction(() => {
    for (const c of SEED) {
      const info = insCreator.run({
        handle: c.handle,
        name: c.name,
        tagline: c.tagline,
        bio: c.bio,
        city: c.city,
        genres: JSON.stringify(c.genres),
        hue: c.hue,
        followers: c.followers,
      });
      const creatorId = Number(info.lastInsertRowid);

      c.tracks.forEach(([title, duration, plays], i) => {
        insTrack.run(creatorId, title, duration, plays, i);
      });

      if (!c.stream) continue;
      const s = c.stream;
      const at = now + s.offsetMin * 60_000;
      const streamInfo = insStream.run({
        creator_id: creatorId,
        slug: s.slug,
        title: s.title,
        blurb: s.blurb,
        tags: JSON.stringify(s.tags),
        is_live: s.live ? 1 : 0,
        started_at: s.live ? at : now,
        scheduled_at: s.live ? null : at,
        listener_base: s.listeners,
        peak: Math.round(s.listeners * 1.18),
      });
      const streamId = Number(streamInfo.lastInsertRowid);

      const chat = CHAT_SEED[s.slug] ?? [];
      chat.forEach(([author, body], i) => {
        // Spread the backlog over the minutes before now.
        const ts = now - (chat.length - i) * 74_000;
        insMessage.run(streamId, `seed:${author}`, author, body, ts);
      });
    }
  })();
}
