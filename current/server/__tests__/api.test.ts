import { beforeEach, describe, expect, it } from 'vitest';
import request from 'supertest';
import type { Express } from 'express';
import { openDb, seed, type DB } from '../db';
import { createApi } from '../api';
import { LiveHub } from '../live';
import express from 'express';

const USER = 'testuser000001';

let app: Express;
let db: DB;

beforeEach(() => {
  db = openDb(':memory:');
  seed(db, Date.now());
  const hub = new LiveHub(db);
  app = express();
  app.use('/api', createApi(db, hub));
});

describe('GET /api/health', () => {
  it('reports the catalogue', async () => {
    const res = await request(app).get('/api/health').expect(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.creators).toBeGreaterThan(0);
    expect(res.body.live).toBeGreaterThan(0);
  });
});

describe('GET /api/streams', () => {
  it('returns every stream with a listener count and creator embedded', async () => {
    const res = await request(app).get('/api/streams').expect(200);
    expect(res.body.streams.length).toBeGreaterThan(0);
    const [first] = res.body.streams;
    expect(typeof first.listeners).toBe('number');
    expect(first.creator.handle).toBeTruthy();
    expect(Array.isArray(first.tags)).toBe(true);
  });

  it('honours the live filter', async () => {
    const res = await request(app).get('/api/streams?filter=live').expect(200);
    expect(res.body.streams.every((s: { isLive: boolean }) => s.isLive)).toBe(true);
  });

  it('falls back to all for a bogus filter', async () => {
    const all = await request(app).get('/api/streams').expect(200);
    const bogus = await request(app).get('/api/streams?filter=nonsense').expect(200);
    expect(bogus.body.streams).toHaveLength(all.body.streams.length);
  });

  it('gives live streams a now-playing track', async () => {
    const res = await request(app).get('/api/streams?filter=live').expect(200);
    for (const s of res.body.streams) {
      expect(s.nowPlaying, s.slug).not.toBeNull();
      expect(s.nowPlaying.track.title).toBeTruthy();
    }
  });

  it('leaves upcoming streams without a playhead', async () => {
    const res = await request(app).get('/api/streams?filter=upcoming').expect(200);
    for (const s of res.body.streams) expect(s.nowPlaying).toBeNull();
  });
});

describe('GET /api/streams/:slug', () => {
  it('returns the room, its set list and the chat backlog', async () => {
    const res = await request(app).get('/api/streams/nrissa-undertow-session').expect(200);
    expect(res.body.stream.slug).toBe('nrissa-undertow-session');
    expect(res.body.tracks.length).toBeGreaterThan(0);
    expect(res.body.messages.length).toBeGreaterThan(0);
    expect(res.body.isFollowing).toBe(false);
  });

  it('404s for an unknown slug', async () => {
    const res = await request(app).get('/api/streams/not-a-real-room').expect(404);
    expect(res.body.error).toMatch(/no such stream/);
  });
});

describe('identity', () => {
  it('requires the user header', async () => {
    const res = await request(app).get('/api/me').expect(400);
    expect(res.body.error).toMatch(/x-current-user/);
  });

  it('rejects a malformed user id', async () => {
    await request(app).get('/api/me').set('x-current-user', 'no spaces!').expect(400);
    await request(app).get('/api/me').set('x-current-user', 'short').expect(400);
  });

  it('creates the user on first sight', async () => {
    const res = await request(app).get('/api/me').set('x-current-user', USER).expect(200);
    expect(res.body.id).toBe(USER);
    expect(res.body.displayName).toMatch(/^listener_/);
    expect(res.body.following).toEqual([]);
  });

  it('renames on PATCH and validates the length', async () => {
    const res = await request(app)
      .patch('/api/me')
      .set('x-current-user', USER)
      .send({ displayName: 'Tidewrack' })
      .expect(200);
    expect(res.body.displayName).toBe('Tidewrack');

    await request(app)
      .patch('/api/me')
      .set('x-current-user', USER)
      .send({ displayName: '' })
      .expect(422);

    await request(app)
      .patch('/api/me')
      .set('x-current-user', USER)
      .send({ displayName: 'x'.repeat(33) })
      .expect(422);
  });
});

describe('chat over REST', () => {
  it('posts a message and reads it back', async () => {
    const post = await request(app)
      .post('/api/streams/nrissa-undertow-session/messages')
      .set('x-current-user', USER)
      .send({ body: '  hello the room  ' })
      .expect(201);
    expect(post.body.message.body).toBe('hello the room');
    expect(post.body.message.userId).toBe(USER);

    const list = await request(app)
      .get('/api/streams/nrissa-undertow-session/messages')
      .expect(200);
    expect(list.body.messages.at(-1).body).toBe('hello the room');
  });

  it('rejects an empty or oversized body', async () => {
    await request(app)
      .post('/api/streams/nrissa-undertow-session/messages')
      .set('x-current-user', USER)
      .send({ body: '' })
      .expect(422);

    await request(app)
      .post('/api/streams/nrissa-undertow-session/messages')
      .set('x-current-user', USER)
      .send({ body: 'x'.repeat(241) })
      .expect(422);
  });

  it('requires identity to speak', async () => {
    await request(app)
      .post('/api/streams/nrissa-undertow-session/messages')
      .send({ body: 'anonymous' })
      .expect(400);
  });

  it('404s when the room does not exist', async () => {
    await request(app)
      .post('/api/streams/nope/messages')
      .set('x-current-user', USER)
      .send({ body: 'hi' })
      .expect(404);
  });
});

describe('sparks', () => {
  it('accumulates', async () => {
    const first = await request(app)
      .post('/api/streams/kito-blue-hour/sparks')
      .set('x-current-user', USER)
      .expect(201);
    const second = await request(app)
      .post('/api/streams/kito-blue-hour/sparks')
      .set('x-current-user', USER)
      .expect(201);
    expect(second.body.sparks).toBe(first.body.sparks + 1);
  });
});

describe('creators', () => {
  it('lists and fetches', async () => {
    const list = await request(app).get('/api/creators').expect(200);
    expect(list.body.creators.length).toBeGreaterThan(0);

    const one = await request(app).get('/api/creators/amaris').expect(200);
    expect(one.body.creator.name).toBe('Amaris Vale');
    expect(one.body.tracks.length).toBeGreaterThan(0);
    expect(one.body.streams.length).toBeGreaterThan(0);
  });

  it('404s for an unknown handle', async () => {
    await request(app).get('/api/creators/nobody').expect(404);
  });

  it('follows and unfollows, and reports it back on the next read', async () => {
    const before = await request(app).get('/api/creators/brk').expect(200);
    const base = before.body.creator.followers;

    const followed = await request(app)
      .put('/api/creators/brk/follow')
      .set('x-current-user', USER)
      .send({ following: true })
      .expect(200);
    expect(followed.body.isFollowing).toBe(true);
    expect(followed.body.creator.followers).toBe(base + 1);

    const read = await request(app).get('/api/creators/brk').set('x-current-user', USER).expect(200);
    expect(read.body.isFollowing).toBe(true);

    const unfollowed = await request(app)
      .put('/api/creators/brk/follow')
      .set('x-current-user', USER)
      .send({ following: false })
      .expect(200);
    expect(unfollowed.body.isFollowing).toBe(false);
    expect(unfollowed.body.creator.followers).toBe(base);
  });

  it('validates the follow payload', async () => {
    await request(app)
      .put('/api/creators/brk/follow')
      .set('x-current-user', USER)
      .send({ following: 'yes' })
      .expect(422);
  });

  it('does not leak one user’s follows to another', async () => {
    await request(app)
      .put('/api/creators/brk/follow')
      .set('x-current-user', USER)
      .send({ following: true })
      .expect(200);

    const other = await request(app)
      .get('/api/creators/brk')
      .set('x-current-user', 'otheruser00002')
      .expect(200);
    expect(other.body.isFollowing).toBe(false);
  });
});

describe('search', () => {
  it('finds creators and streams', async () => {
    const res = await request(app).get('/api/search?q=breaks').expect(200);
    expect(res.body.query).toBe('breaks');
    expect(res.body.streams.length + res.body.creators.length).toBeGreaterThan(0);
  });

  it('returns empty for a blank query rather than everything', async () => {
    const res = await request(app).get('/api/search?q=%20').expect(200);
    expect(res.body.creators).toEqual([]);
    expect(res.body.streams).toEqual([]);
  });
});

describe('unknown endpoints', () => {
  it('404 as JSON', async () => {
    const res = await request(app).get('/api/nothing-here').expect(404);
    expect(res.body.error).toBeTruthy();
  });
});
