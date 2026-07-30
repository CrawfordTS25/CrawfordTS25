/**
 * Room chat. Sends over the socket when it is open and falls back to REST when
 * it is not, so typing never silently fails.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { LiveStatus } from '../lib/useLive';
import type { Message } from '../lib/api';
import { api } from '../lib/api';
import { timeOfDay } from '../lib/format';
import { userId } from '../lib/identity';
import { Avatar } from './ui';

const MAX = 240;

export function Chat({
  slug,
  messages,
  status,
  listeners,
  sendChat,
  appendMessage,
}: {
  slug: string;
  messages: Message[];
  status: LiveStatus;
  listeners: number | null;
  sendChat: (body: string) => boolean;
  appendMessage: (m: Message) => void;
}) {
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const me = userId();

  // Follow the conversation, but stop yanking the view if the reader scrolled up.
  useLayoutEffect(() => {
    const log = logRef.current;
    if (!log || !pinnedRef.current) return;
    log.scrollTop = log.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    const onScroll = () => {
      const gap = log.scrollHeight - log.scrollTop - log.clientHeight;
      pinnedRef.current = gap < 64;
    };
    log.addEventListener('scroll', onScroll, { passive: true });
    return () => log.removeEventListener('scroll', onScroll);
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;

    setFailure(null);
    // The socket is the fast path; the room hears it on the broadcast.
    if (sendChat(body)) {
      setDraft('');
      pinnedRef.current = true;
      return;
    }

    setSending(true);
    try {
      const { message } = await api.postMessage(slug, body);
      appendMessage(message);
      setDraft('');
      pinnedRef.current = true;
    } catch (err) {
      setFailure(err instanceof Error ? err.message : 'could not send that');
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="card chat" aria-label="Room chat">
      <header className="panel-head">
        <span className="label">In the current</span>
        <span className="faint small tnum">
          {status === 'live'
            ? listeners !== null
              ? `${listeners.toLocaleString()} here`
              : 'connecting'
            : status === 'reconnecting'
              ? 'reconnecting…'
              : status === 'connecting'
                ? 'tuning in…'
                : 'offline'}
        </span>
      </header>

      <div className="chat-log" ref={logRef}>
        {messages.length === 0 ? (
          <p className="chat-empty">Nobody has said anything yet. Go on — say the first thing.</p>
        ) : (
          messages.map((m) => (
            <article key={m.id} className={`chat-msg${m.userId === me ? ' chat-mine' : ''}`}>
              <Avatar name={m.author} hue={hueFor(m.author)} size={28} />
              <div>
                <div className="row" style={{ gap: 8, alignItems: 'baseline' }}>
                  <span className="chat-author">{m.userId === me ? 'you' : m.author}</span>
                  <span className="faint" style={{ fontSize: 11 }}>
                    {timeOfDay(m.createdAt)}
                  </span>
                </div>
                <p className="chat-body" style={{ margin: 0 }}>
                  {m.body}
                </p>
              </div>
            </article>
          ))
        )}
      </div>

      <form className="chat-compose" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">
          Say something to the room
        </label>
        <input
          id="chat-input"
          className="input"
          value={draft}
          maxLength={MAX}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Say something…"
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={!draft.trim() || sending}>
          Send
        </button>
      </form>

      {failure && (
        <p className="small" style={{ margin: 0, padding: '0 var(--space-4) var(--space-4)', color: 'var(--c-spark)' }}>
          {failure}
        </p>
      )}
    </section>
  );
}

/** Stable tint per name, so a voice keeps the same colour all session. */
function hueFor(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  // Keep chat avatars in the cool half of the wheel — amber belongs to the spark.
  return 150 + (h % 86);
}
