/**
 * REST surface. Identity is a client-generated id carried in `x-current-user`
 * — enough to follow creators and own your chat messages, with no signup wall
 * in front of a live room.
 */

import express, { type Request, type Response, type Router } from 'express';
import { z } from 'zod';
import type { DB } from './db';
import type { LiveHub } from './live';
import * as repo from './repo';

const USER_HEADER = 'x-current-user';

function userIdFrom(req: Request): string | null {
  const raw = req.header(USER_HEADER);
  if (!raw) return null;
  const id = raw.trim();
  return /^[A-Za-z0-9_-]{6,64}$/.test(id) ? id : null;
}

/** Resolves the caller, creating the row on first sight. */
function requireUser(db: DB, req: Request, res: Response) {
  const id = userIdFrom(req);
  if (!id) {
    res.status(400).json({ error: `a ${USER_HEADER} header is required` });
    return null;
  }
  return repo.upsertUser(db, id);
}

function streamPayload(db: DB, hub: LiveHub, stream: repo.Stream) {
  return {
    ...stream,
    listeners: hub.listeners(stream.id),
    nowPlaying: repo.nowPlaying(db, stream),
    sparks: repo.countSparks(db, stream.id),
  };
}

export function createApi(db: DB, hub: LiveHub): Router {
  const api = express.Router();
  api.use(express.json({ limit: '32kb' }));

  api.get('/health', (_req, res) => {
    const counts = db
      .prepare(
        `SELECT (SELECT COUNT(*) FROM creators) AS creators,
                (SELECT COUNT(*) FROM streams WHERE is_live = 1) AS live,
                (SELECT COUNT(*) FROM messages) AS messages`,
      )
      .get();
    res.json({ ok: true, ...(counts as object) });
  });

  /* ── identity ──────────────────────────────────────────────────────────── */

  api.get('/me', (req, res) => {
    const user = requireUser(db, req, res);
    if (!user) return;
    res.json({ ...user, following: repo.listFollowedCreatorIds(db, user.id) });
  });

  const PatchMe = z.object({ displayName: z.string().min(1).max(32) });

  api.patch('/me', (req, res) => {
    const id = userIdFrom(req);
    if (!id) return res.status(400).json({ error: `a ${USER_HEADER} header is required` });
    const parsed = PatchMe.safeParse(req.body);
    if (!parsed.success) return res.status(422).json({ error: 'displayName must be 1–32 characters' });
    const user = repo.upsertUser(db, id, parsed.data.displayName);
    res.json({ ...user, following: repo.listFollowedCreatorIds(db, user.id) });
  });

  /* ── streams ───────────────────────────────────────────────────────────── */

  api.get('/streams', (req, res) => {
    const filter = req.query.filter;
    const which = filter === 'live' || filter === 'upcoming' ? filter : 'all';
    const streams = repo.listStreams(db, which).map((s) => streamPayload(db, hub, s));
    res.json({ streams });
  });

  api.get('/streams/:slug', (req, res) => {
    const stream = repo.getStreamBySlug(db, req.params.slug);
    if (!stream) return res.status(404).json({ error: 'no such stream' });
    const userId = userIdFrom(req);
    res.json({
      stream: streamPayload(db, hub, stream),
      tracks: repo.listTracks(db, stream.creator.id),
      messages: repo.listMessages(db, stream.id),
      isFollowing: userId ? repo.isFollowing(db, userId, stream.creator.id) : false,
    });
  });

  api.get('/streams/:slug/messages', (req, res) => {
    const stream = repo.getStreamBySlug(db, req.params.slug);
    if (!stream) return res.status(404).json({ error: 'no such stream' });
    res.json({ messages: repo.listMessages(db, stream.id) });
  });

  const PostMessage = z.object({ body: z.string().min(1).max(240) });

  /** REST fallback for chat, so posting works without a socket. */
  api.post('/streams/:slug/messages', (req, res) => {
    const user = requireUser(db, req, res);
    if (!user) return;
    const stream = repo.getStreamBySlug(db, req.params.slug);
    if (!stream) return res.status(404).json({ error: 'no such stream' });
    const parsed = PostMessage.safeParse(req.body);
    if (!parsed.success) return res.status(422).json({ error: 'body must be 1–240 characters' });

    const message = repo.addMessage(db, {
      streamId: stream.id,
      userId: user.id,
      author: user.displayName,
      body: parsed.data.body.trim(),
    });
    hub.broadcast(stream.id, { type: 'chat', message });
    res.status(201).json({ message });
  });

  api.post('/streams/:slug/sparks', (req, res) => {
    const user = requireUser(db, req, res);
    if (!user) return;
    const stream = repo.getStreamBySlug(db, req.params.slug);
    if (!stream) return res.status(404).json({ error: 'no such stream' });
    repo.addSpark(db, stream.id, user.id);
    const total = repo.countSparks(db, stream.id);
    hub.broadcast(stream.id, { type: 'spark', from: user.id, total });
    res.status(201).json({ sparks: total });
  });

  /* ── creators ──────────────────────────────────────────────────────────── */

  api.get('/creators', (_req, res) => {
    res.json({ creators: repo.listCreators(db) });
  });

  api.get('/creators/:handle', (req, res) => {
    const creator = repo.getCreatorByHandle(db, req.params.handle);
    if (!creator) return res.status(404).json({ error: 'no such creator' });
    const userId = userIdFrom(req);
    res.json({
      creator,
      tracks: repo.listTracks(db, creator.id),
      streams: repo.listStreamsByCreator(db, creator.id).map((s) => streamPayload(db, hub, s)),
      isFollowing: userId ? repo.isFollowing(db, userId, creator.id) : false,
    });
  });

  const Follow = z.object({ following: z.boolean() });

  api.put('/creators/:handle/follow', (req, res) => {
    const user = requireUser(db, req, res);
    if (!user) return;
    const creator = repo.getCreatorByHandle(db, req.params.handle);
    if (!creator) return res.status(404).json({ error: 'no such creator' });
    const parsed = Follow.safeParse(req.body);
    if (!parsed.success) return res.status(422).json({ error: 'following must be a boolean' });

    repo.setFollow(db, user.id, creator.id, parsed.data.following);
    const updated = repo.getCreatorByHandle(db, req.params.handle)!;
    res.json({ creator: updated, isFollowing: parsed.data.following });
  });

  /* ── discovery ─────────────────────────────────────────────────────────── */

  api.get('/search', (req, res) => {
    const q = String(req.query.q ?? '').trim();
    if (!q) return res.json({ creators: [], streams: [], query: '' });
    const { creators, streams } = repo.search(db, q);
    res.json({ query: q, creators, streams: streams.map((s) => streamPayload(db, hub, s)) });
  });

  api.use((_req, res) => res.status(404).json({ error: 'no such endpoint' }));

  return api;
}
