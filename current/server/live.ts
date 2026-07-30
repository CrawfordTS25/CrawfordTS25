/**
 * The live hub — what makes `current` current.
 *
 * One WebSocket per listener, joined to a stream room. The hub owns three
 * things: presence (who is in the room), the shared playhead (everyone hears
 * the same second of the same track), and the chat + spark firehose.
 *
 * Listener counts are the room's real socket count plus a drifting simulated
 * audience, so the number moves the way a live room does — and your own arrival
 * visibly bumps it.
 */

import type { WebSocket, WebSocketServer } from 'ws';
import { z } from 'zod';
import type { DB } from './db';
import * as repo from './repo';

export const TICK_MS = 2_000;
const MAX_BODY = 240;
const CHAT_MIN_INTERVAL_MS = 700;
const SPARK_MIN_INTERVAL_MS = 250;

const Inbound = z.discriminatedUnion('type', [
  z.object({ type: z.literal('chat'), body: z.string().min(1).max(MAX_BODY) }),
  z.object({ type: z.literal('spark') }),
  z.object({ type: z.literal('ping') }),
]);

type Client = {
  socket: WebSocket;
  streamId: number;
  userId: string;
  author: string;
  lastChatAt: number;
  lastSparkAt: number;
};

/** Deterministic drift so the simulated audience wanders instead of jumping. */
function drift(seed: number, step: number): number {
  const x = Math.sin(seed * 12.9898 + step * 78.233) * 43758.5453;
  return x - Math.floor(x); // 0..1
}

export class LiveHub {
  private clients = new Map<WebSocket, Client>();
  private rooms = new Map<number, Set<WebSocket>>();
  private lastTrackId = new Map<number, number>();
  private step = 0;
  private timer: NodeJS.Timeout | null = null;
  private stopped = false;

  constructor(private db: DB) {}

  /**
   * Sockets close asynchronously, so a disconnect can land after shutdown has
   * already closed the database. Anything that touches the db goes through here.
   */
  private usable(): boolean {
    return !this.stopped && this.db.open;
  }

  /** Real sockets plus the drifting simulated audience. */
  listeners(streamId: number): number {
    if (!this.usable()) return this.rooms.get(streamId)?.size ?? 0;
    const stream = repo.getStreamById(this.db, streamId);
    if (!stream) return 0;
    const real = this.rooms.get(streamId)?.size ?? 0;
    if (!stream.isLive) return real;
    // ±6% wander around the base, refreshed every tick.
    const swing = Math.round(stream.listenerBase * 0.06 * (drift(streamId, this.step) * 2 - 1));
    return Math.max(0, stream.listenerBase + swing) + real;
  }

  start() {
    this.stopped = false;
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), TICK_MS);
    // Don't hold the process open just for the heartbeat.
    this.timer.unref?.();
  }

  stop() {
    this.stopped = true;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  attach(wss: WebSocketServer) {
    wss.on('connection', (socket, req) => {
      if (!this.usable()) {
        socket.close(1001, 'server is shutting down');
        return;
      }
      const url = new URL(req.url ?? '/', 'http://localhost');
      const slug = url.searchParams.get('stream') ?? '';
      const userId = url.searchParams.get('userId') ?? '';

      const stream = repo.getStreamBySlug(this.db, slug);
      if (!stream || !userId) {
        socket.close(1008, 'stream and userId are required');
        return;
      }

      const user = repo.upsertUser(this.db, userId);
      const client: Client = {
        socket,
        streamId: stream.id,
        userId,
        author: user.displayName,
        lastChatAt: 0,
        lastSparkAt: 0,
      };
      this.clients.set(socket, client);
      let room = this.rooms.get(stream.id);
      if (!room) {
        room = new Set();
        this.rooms.set(stream.id, room);
      }
      room.add(socket);

      const listeners = this.listeners(stream.id);
      repo.updatePeak(this.db, stream.id, listeners);

      this.send(socket, {
        type: 'hello',
        you: { id: userId, displayName: user.displayName },
        stream: { id: stream.id, slug: stream.slug, title: stream.title },
        listeners,
        sparks: repo.countSparks(this.db, stream.id),
        nowPlaying: repo.nowPlaying(this.db, stream),
        messages: repo.listMessages(this.db, stream.id),
      });

      // Everyone else sees the room grow.
      this.broadcast(stream.id, { type: 'presence', listeners }, socket);

      socket.on('message', (raw) => this.onMessage(client, raw.toString()));
      socket.on('close', () => this.onClose(socket));
      socket.on('error', () => this.onClose(socket));
    });
  }

  private onClose(socket: WebSocket) {
    const client = this.clients.get(socket);
    this.clients.delete(socket);
    if (!client) return;
    const room = this.rooms.get(client.streamId);
    room?.delete(socket);
    if (room && room.size === 0) this.rooms.delete(client.streamId);
    // During shutdown there is nobody left to tell, and no database to ask.
    if (!this.usable()) return;
    this.broadcast(client.streamId, { type: 'presence', listeners: this.listeners(client.streamId) });
  }

  private onMessage(client: Client, raw: string) {
    if (!this.usable()) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return this.send(client.socket, { type: 'error', error: 'malformed message' });
    }
    const result = Inbound.safeParse(parsed);
    if (!result.success) {
      return this.send(client.socket, { type: 'error', error: 'unrecognised message' });
    }
    const msg = result.data;
    const now = Date.now();

    if (msg.type === 'ping') {
      return this.send(client.socket, { type: 'pong', at: now });
    }

    if (msg.type === 'chat') {
      if (now - client.lastChatAt < CHAT_MIN_INTERVAL_MS) {
        return this.send(client.socket, { type: 'error', error: 'easy — one message at a time' });
      }
      const body = msg.body.trim().slice(0, MAX_BODY);
      if (!body) return;
      client.lastChatAt = now;
      // Pick up a rename made over the REST API since this socket opened.
      const user = repo.getUser(this.db, client.userId);
      if (user) client.author = user.displayName;
      const stored = repo.addMessage(this.db, {
        streamId: client.streamId,
        userId: client.userId,
        author: client.author,
        body,
      });
      return this.broadcast(client.streamId, { type: 'chat', message: stored });
    }

    if (msg.type === 'spark') {
      if (now - client.lastSparkAt < SPARK_MIN_INTERVAL_MS) return;
      client.lastSparkAt = now;
      repo.addSpark(this.db, client.streamId, client.userId);
      return this.broadcast(client.streamId, {
        type: 'spark',
        from: client.userId,
        total: repo.countSparks(this.db, client.streamId),
      });
    }
  }

  /** Heartbeat: presence drift and the shared playhead. */
  private tick() {
    if (!this.usable()) return;
    this.step += 1;
    for (const [streamId, room] of this.rooms) {
      if (room.size === 0) continue;
      const stream = repo.getStreamById(this.db, streamId);
      if (!stream) continue;

      const listeners = this.listeners(streamId);
      repo.updatePeak(this.db, streamId, listeners);
      this.broadcast(streamId, { type: 'presence', listeners });

      const np = repo.nowPlaying(this.db, stream);
      if (!np) continue;
      const previous = this.lastTrackId.get(streamId);
      if (previous !== np.track.id) {
        this.lastTrackId.set(streamId, np.track.id);
        this.broadcast(streamId, { type: 'nowplaying', nowPlaying: np });
      } else {
        this.broadcast(streamId, {
          type: 'progress',
          trackId: np.track.id,
          position: np.position,
          duration: np.track.durationS,
        });
      }
    }
  }

  private send(socket: WebSocket, payload: unknown) {
    if (socket.readyState !== socket.OPEN) return;
    socket.send(JSON.stringify(payload));
  }

  broadcast(streamId: number, payload: unknown, except?: WebSocket) {
    const room = this.rooms.get(streamId);
    if (!room) return;
    const data = JSON.stringify(payload);
    for (const socket of room) {
      if (socket === except) continue;
      if (socket.readyState === socket.OPEN) socket.send(data);
    }
  }

  /** Test/introspection helper. */
  roomSize(streamId: number) {
    return this.rooms.get(streamId)?.size ?? 0;
  }
}
