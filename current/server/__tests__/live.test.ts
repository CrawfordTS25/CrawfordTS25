/**
 * Live hub tests over a real WebSocket server — presence, chat fan-out, sparks
 * and rate limiting, exercised the same way a browser exercises them.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createServer, type Server } from 'node:http';
import { AddressInfo } from 'node:net';
import { WebSocket, WebSocketServer } from 'ws';
import { openDb, seed, type DB } from '../db';
import { LiveHub } from '../live';
import * as repo from '../repo';

let db: DB;
let hub: LiveHub;
let server: Server;
let wss: WebSocketServer;
let port: number;

beforeEach(async () => {
  db = openDb(':memory:');
  seed(db, Date.now());
  hub = new LiveHub(db);
  server = createServer();
  wss = new WebSocketServer({ server, path: '/ws' });
  hub.attach(wss);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  port = (server.address() as AddressInfo).port;
});

afterEach(async () => {
  hub.stop();
  wss.close();
  await new Promise<void>((resolve) => server.close(() => resolve()));
  db.close();
});

type Frame = Record<string, unknown>;

/** A test client that records every frame and can await a specific type. */
function connect(slug: string, userId: string) {
  const socket = new WebSocket(`ws://localhost:${port}/ws?stream=${slug}&userId=${userId}`);
  const frames: Frame[] = [];
  socket.on('message', (raw) => frames.push(JSON.parse(raw.toString())));

  const opened = new Promise<void>((resolve, reject) => {
    socket.once('open', () => resolve());
    socket.once('error', reject);
  });

  const closed = new Promise<number>((resolve) => socket.once('close', (code) => resolve(code)));

  async function waitFor(type: string, timeout = 5_000): Promise<Frame> {
    const deadline = Date.now() + timeout;
    for (;;) {
      const found = frames.find((f) => f.type === type);
      if (found) return found;
      if (Date.now() > deadline) {
        throw new Error(`timed out waiting for "${type}"; saw ${frames.map((f) => f.type).join(', ')}`);
      }
      await new Promise((r) => setTimeout(r, 25));
    }
  }

  function forget(type: string) {
    for (let i = frames.length - 1; i >= 0; i--) if (frames[i].type === type) frames.splice(i, 1);
  }

  return { socket, frames, opened, closed, waitFor, forget };
}

const LIVE = 'nrissa-undertow-session';

describe('joining a room', () => {
  it('sends a hello with the backlog, listeners and the playhead', async () => {
    const a = connect(LIVE, 'aaaaaa000001');
    await a.opened;
    const hello = await a.waitFor('hello');

    expect((hello.you as { id: string }).id).toBe('aaaaaa000001');
    expect((hello.stream as { slug: string }).slug).toBe(LIVE);
    expect(hello.listeners as number).toBeGreaterThan(0);
    expect(Array.isArray(hello.messages)).toBe(true);
    expect((hello.messages as unknown[]).length).toBeGreaterThan(0);
    expect(hello.nowPlaying).not.toBeNull();

    a.socket.close();
    await a.closed;
  });

  it('refuses a connection without a valid stream', async () => {
    const bad = connect('no-such-stream', 'aaaaaa000002');
    const code = await bad.closed;
    expect(code).toBe(1008);
  });

  it('refuses a connection without a user id', async () => {
    const socket = new WebSocket(`ws://localhost:${port}/ws?stream=${LIVE}`);
    const code = await new Promise<number>((resolve) => socket.once('close', (c) => resolve(c)));
    expect(code).toBe(1008);
  });

  it('counts a real listener on top of the simulated audience', async () => {
    const stream = repo.getStreamBySlug(db, LIVE)!;
    expect(hub.roomSize(stream.id)).toBe(0);

    const a = connect(LIVE, 'aaaaaa000003');
    await a.opened;
    await a.waitFor('hello');
    expect(hub.roomSize(stream.id)).toBe(1);

    const b = connect(LIVE, 'aaaaaa000004');
    await b.opened;
    await b.waitFor('hello');
    expect(hub.roomSize(stream.id)).toBe(2);

    // The room shrinks again when someone leaves.
    b.socket.close();
    await b.closed;
    await new Promise((r) => setTimeout(r, 100));
    expect(hub.roomSize(stream.id)).toBe(1);

    a.socket.close();
    await a.closed;
  });

  it('tells the room when someone else arrives', async () => {
    const a = connect(LIVE, 'aaaaaa000005');
    await a.opened;
    await a.waitFor('hello');
    a.forget('presence');

    const b = connect(LIVE, 'aaaaaa000006');
    await b.opened;
    await b.waitFor('hello');

    const presence = await a.waitFor('presence');
    expect(presence.listeners as number).toBeGreaterThan(0);

    a.socket.close();
    b.socket.close();
  });
});

describe('chat', () => {
  it('broadcasts a message to everyone including the sender, and persists it', async () => {
    const a = connect(LIVE, 'aaaaaa000007');
    const b = connect(LIVE, 'aaaaaa000008');
    await Promise.all([a.opened, b.opened]);
    await Promise.all([a.waitFor('hello'), b.waitFor('hello')]);

    a.socket.send(JSON.stringify({ type: 'chat', body: 'ride the wave' }));

    const seenByA = await a.waitFor('chat');
    const seenByB = await b.waitFor('chat');
    expect((seenByA.message as { body: string }).body).toBe('ride the wave');
    expect((seenByB.message as { body: string }).body).toBe('ride the wave');
    expect((seenByB.message as { userId: string }).userId).toBe('aaaaaa000007');

    const stream = repo.getStreamBySlug(db, LIVE)!;
    const stored = repo.listMessages(db, stream.id);
    expect(stored.at(-1)!.body).toBe('ride the wave');

    a.socket.close();
    b.socket.close();
  });

  it('does not leak chat into a different room', async () => {
    const a = connect(LIVE, 'aaaaaa000009');
    const other = connect('kito-blue-hour', 'aaaaaa000010');
    await Promise.all([a.opened, other.opened]);
    await Promise.all([a.waitFor('hello'), other.waitFor('hello')]);

    a.socket.send(JSON.stringify({ type: 'chat', body: 'only for this room' }));
    await a.waitFor('chat');

    await new Promise((r) => setTimeout(r, 200));
    expect(other.frames.some((f) => f.type === 'chat')).toBe(false);

    a.socket.close();
    other.socket.close();
  });

  it('rate limits a flood and says so', async () => {
    const a = connect(LIVE, 'aaaaaa000011');
    await a.opened;
    await a.waitFor('hello');

    a.socket.send(JSON.stringify({ type: 'chat', body: 'one' }));
    await a.waitFor('chat');
    a.socket.send(JSON.stringify({ type: 'chat', body: 'two, immediately' }));

    const err = await a.waitFor('error');
    expect(String(err.error)).toMatch(/one message at a time/);
    // The rejected message must not have been stored.
    const stream = repo.getStreamBySlug(db, LIVE)!;
    expect(repo.listMessages(db, stream.id).some((m) => m.body === 'two, immediately')).toBe(false);

    a.socket.close();
  });

  it('rejects malformed and unknown frames without dropping the socket', async () => {
    const a = connect(LIVE, 'aaaaaa000012');
    await a.opened;
    await a.waitFor('hello');

    a.socket.send('not json at all');
    expect(String((await a.waitFor('error')).error)).toMatch(/malformed/);
    a.forget('error');

    a.socket.send(JSON.stringify({ type: 'launch-missiles' }));
    expect(String((await a.waitFor('error')).error)).toMatch(/unrecognised/);

    // Still usable afterwards.
    a.socket.send(JSON.stringify({ type: 'ping' }));
    await a.waitFor('pong');

    a.socket.close();
  });

  it('truncates an over-long body at the schema boundary', async () => {
    const a = connect(LIVE, 'aaaaaa000013');
    await a.opened;
    await a.waitFor('hello');

    a.socket.send(JSON.stringify({ type: 'chat', body: 'x'.repeat(241) }));
    expect(String((await a.waitFor('error')).error)).toMatch(/unrecognised/);

    a.socket.close();
  });
});

describe('sparks', () => {
  it('fans out with a running total', async () => {
    const a = connect(LIVE, 'aaaaaa000014');
    const b = connect(LIVE, 'aaaaaa000015');
    await Promise.all([a.opened, b.opened]);
    await Promise.all([a.waitFor('hello'), b.waitFor('hello')]);

    a.socket.send(JSON.stringify({ type: 'spark' }));
    const burst = await b.waitFor('spark');
    expect(burst.from).toBe('aaaaaa000014');
    expect(burst.total as number).toBeGreaterThanOrEqual(1);

    a.socket.close();
    b.socket.close();
  });
});
