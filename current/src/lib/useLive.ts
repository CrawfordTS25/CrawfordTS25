/**
 * The live socket. Owns presence, the shared playhead, chat and sparks for one
 * stream, and reconnects with backoff if the connection drops.
 *
 * Between server ticks the playhead is advanced locally so the progress bar
 * moves at one second per second instead of stepping every two seconds.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Message, NowPlaying } from './api';
import { userId } from './identity';

export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'closed';

export type SparkBurst = { key: number; from: string };

export type LiveState = {
  status: LiveStatus;
  listeners: number | null;
  sparks: number;
  nowPlaying: NowPlaying | null;
  messages: Message[];
  /** Transient spark animations to render, newest last. */
  bursts: SparkBurst[];
  displayName: string | null;
  error: string | null;
};

type Options = {
  /** Omit to stay disconnected — used for upcoming (not yet live) streams. */
  slug?: string;
  initialMessages?: Message[];
  initialListeners?: number;
  initialSparks?: number;
  initialNowPlaying?: NowPlaying | null;
};

const MAX_MESSAGES = 200;
const BURST_TTL_MS = 1_400;

export function useLive({
  slug,
  initialMessages = [],
  initialListeners,
  initialSparks = 0,
  initialNowPlaying = null,
}: Options) {
  const [status, setStatus] = useState<LiveStatus>(slug ? 'connecting' : 'closed');
  const [listeners, setListeners] = useState<number | null>(initialListeners ?? null);
  const [sparks, setSparks] = useState(initialSparks);
  const [nowPlaying, setNowPlaying] = useState<NowPlaying | null>(initialNowPlaying);
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [bursts, setBursts] = useState<SparkBurst[]>([]);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const retryRef = useRef<number | null>(null);
  const burstSeq = useRef(0);
  const closedByUs = useRef(false);

  useEffect(() => {
    if (!slug) {
      setStatus('closed');
      return;
    }
    closedByUs.current = false;

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const url = `${proto}://${location.host}/ws?stream=${encodeURIComponent(slug)}&userId=${userId()}`;
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        attemptRef.current = 0;
        setStatus('live');
        setError(null);
      };

      socket.onmessage = (event) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return;
        }

        switch (msg.type) {
          case 'hello': {
            setListeners(msg.listeners as number);
            setSparks(msg.sparks as number);
            setNowPlaying((msg.nowPlaying as NowPlaying | null) ?? null);
            setMessages((msg.messages as Message[]) ?? []);
            const you = msg.you as { displayName?: string } | undefined;
            if (you?.displayName) setDisplayName(you.displayName);
            break;
          }
          case 'presence':
            setListeners(msg.listeners as number);
            break;
          case 'nowplaying':
            setNowPlaying(msg.nowPlaying as NowPlaying);
            break;
          case 'progress':
            setNowPlaying((prev) =>
              prev && prev.track.id === msg.trackId
                ? { ...prev, position: msg.position as number }
                : prev,
            );
            break;
          case 'chat': {
            const message = msg.message as Message;
            setMessages((prev) =>
              prev.some((m) => m.id === message.id)
                ? prev
                : [...prev, message].slice(-MAX_MESSAGES),
            );
            break;
          }
          case 'spark': {
            setSparks(msg.total as number);
            const key = ++burstSeq.current;
            setBursts((prev) => [...prev, { key, from: String(msg.from ?? '') }]);
            window.setTimeout(
              () => setBursts((prev) => prev.filter((b) => b.key !== key)),
              BURST_TTL_MS,
            );
            break;
          }
          case 'error':
            setError(String(msg.error ?? 'something went sideways'));
            break;
        }
      };

      socket.onclose = () => {
        socketRef.current = null;
        if (closedByUs.current) return;
        setStatus('reconnecting');
        // Back off, but keep trying — a dropped set is worth rejoining.
        const delay = Math.min(8_000, 500 * 2 ** attemptRef.current);
        attemptRef.current += 1;
        retryRef.current = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        // onclose always follows; reconnection is handled there.
      };
    };

    connect();

    return () => {
      closedByUs.current = true;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [slug]);

  // Advance the playhead locally between server ticks.
  useEffect(() => {
    if (!nowPlaying || status !== 'live') return;
    const timer = window.setInterval(() => {
      setNowPlaying((prev) => {
        if (!prev) return prev;
        if (prev.position >= prev.track.durationS) return prev;
        return { ...prev, position: prev.position + 1 };
      });
    }, 1_000);
    return () => window.clearInterval(timer);
    // Re-seat the ticker when the track changes; position updates come from it.
  }, [nowPlaying?.track.id, status]);

  const send = useCallback((payload: unknown) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendChat = useCallback((body: string) => send({ type: 'chat', body }), [send]);
  const sendSpark = useCallback(() => send({ type: 'spark' }), [send]);

  /** Optimistically append a message posted over REST. */
  const appendMessage = useCallback((message: Message) => {
    setMessages((prev) =>
      prev.some((m) => m.id === message.id) ? prev : [...prev, message].slice(-MAX_MESSAGES),
    );
  }, []);

  const state: LiveState = useMemo(
    () => ({ status, listeners, sparks, nowPlaying, messages, bursts, displayName, error }),
    [status, listeners, sparks, nowPlaying, messages, bursts, displayName, error],
  );

  return { ...state, sendChat, sendSpark, appendMessage, setDisplayName };
}
