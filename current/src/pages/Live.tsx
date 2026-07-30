/**
 * The live room. Everyone here shares one playhead, one listener count and one
 * chat — all driven by the socket in `useLive`.
 *
 * The spark budget for this view goes to the LIVE badge and the spark button
 * (the same warm accent, the same idea: this is happening now).
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CurrentLine, GlyphMark, LiveNow } from '../brand/marks';
import { Chat } from '../components/Chat';
import { Avatar, ErrorState, Loading, Stat, Tags } from '../components/ui';
import { api } from '../lib/api';
import { clock, compact, elapsedSince, untilStart } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { useLive } from '../lib/useLive';

export function Live() {
  const { slug = '' } = useParams();
  const { data, error, loading, reload } = useAsync(() => api.stream(slug), [slug]);

  const stream = data?.stream ?? null;
  const live = useLive({
    // Only open a socket for a room that is actually on air.
    slug: stream?.isLive ? slug : undefined,
    initialMessages: data?.messages ?? [],
    initialListeners: stream?.listeners,
    initialSparks: stream?.sparks ?? 0,
    initialNowPlaying: stream?.nowPlaying ?? null,
  });

  const [following, setFollowing] = useState(false);
  const [followers, setFollowers] = useState(0);
  const [followBusy, setFollowBusy] = useState(false);

  useEffect(() => {
    if (!data) return;
    setFollowing(data.isFollowing);
    setFollowers(data.stream.creator.followers);
  }, [data]);

  if (loading) return <Loading label="Opening the room…" />;
  if (error || !data || !stream) {
    return (
      <div className="wrap page">
        <ErrorState error={error ?? 'That room is not here.'} onRetry={reload} />
      </div>
    );
  }

  const { creator } = stream;
  const np = live.nowPlaying ?? stream.nowPlaying;
  const listeners = live.listeners ?? stream.listeners;

  async function toggleFollow() {
    setFollowBusy(true);
    const next = !following;
    setFollowing(next); // optimistic
    setFollowers((n) => n + (next ? 1 : -1));
    try {
      const res = await api.follow(creator.handle, next);
      setFollowing(res.isFollowing);
      setFollowers(res.creator.followers);
    } catch {
      setFollowing(!next); // put it back
      setFollowers((n) => n + (next ? -1 : 1));
    } finally {
      setFollowBusy(false);
    }
  }

  return (
    <div className="wrap page">
      <div className="live-layout">
        <div className="stack" style={{ gap: 'var(--space-5)' }}>
          <Stage
            hue={creator.hue}
            isLive={stream.isLive}
            bursts={live.bursts}
            status={live.status}
          />

          <section className="card">
            <div className="transport">
              <div className="transport-row">
                <div className="stack" style={{ gap: 2, minWidth: 0, flex: 1 }}>
                  <span className="label faint">
                    {stream.isLive ? 'Now playing' : 'Opens with'}
                  </span>
                  <span className="h3 truncate">{np?.track.title ?? 'Set list to be revealed'}</span>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => live.sendSpark()}
                  disabled={!stream.isLive || live.status !== 'live'}
                  title={stream.isLive ? 'Send a spark' : 'The room is not open yet'}
                >
                  Spark
                  <span className="tnum" style={{ opacity: 0.75 }}>
                    {compact(live.sparks)}
                  </span>
                </button>
              </div>

              <CurrentLine
                progress={np ? np.position / np.track.durationS : 0}
                flowing={stream.isLive && live.status !== 'live'}
                height={18}
                aria-label="Track progress"
              />
              <div className="transport-times tnum">
                <span>{np ? clock(np.position) : '0:00'}</span>
                <span>
                  {np ? `track ${np.index + 1} of ${np.of}` : stream.isLive ? 'buffering' : 'not started'}
                </span>
                <span>{np ? clock(np.track.durationS) : '—'}</span>
              </div>
            </div>
          </section>

          <header className="stack" style={{ gap: 'var(--space-4)' }}>
            <div className="row wrap-row" style={{ gap: 'var(--space-3)' }}>
              {stream.isLive ? (
                <LiveNow />
              ) : (
                <span className="tag">
                  {stream.scheduledAt ? untilStart(stream.scheduledAt) : 'Scheduled'}
                </span>
              )}
              <span className="label faint">
                {stream.isLive ? elapsedSince(stream.startedAt) : 'Doors not open yet'}
              </span>
              {live.status === 'reconnecting' && (
                <span className="label" style={{ color: 'var(--c-aqua)' }}>
                  Reconnecting…
                </span>
              )}
            </div>

            <h1 className="h1">{stream.title}</h1>
            <p className="muted" style={{ margin: 0, maxWidth: '62ch' }}>
              {stream.blurb}
            </p>
            <Tags items={stream.tags} max={6} />

            <div className="spread wrap-row">
              <Link to={`/c/${creator.handle}`} className="row" style={{ gap: 'var(--space-3)' }}>
                <Avatar name={creator.name} hue={creator.hue} size={48} ring={stream.isLive} />
                <span className="stack" style={{ gap: 1 }}>
                  <span className="h3">{creator.name}</span>
                  <span className="faint small tnum">
                    {compact(followers)} in the current · {creator.city}
                  </span>
                </span>
              </Link>
              <button
                type="button"
                className={`btn${following ? '' : ' btn-primary'}`}
                onClick={toggleFollow}
                disabled={followBusy}
                aria-pressed={following}
              >
                {following ? 'Following' : 'Follow'}
              </button>
            </div>

            <div className="stat-row">
              <Stat label="Listening now" value={compact(listeners)} />
              <Stat label="Peak" value={compact(Math.max(stream.peakListeners, listeners))} />
              <Stat label="Sparks" value={compact(live.sparks)} />
            </div>
          </header>

          <SetList tracks={data.tracks} playingId={np?.track.id ?? null} />
        </div>

        <Chat
          slug={slug}
          messages={live.messages}
          status={stream.isLive ? live.status : 'closed'}
          listeners={listeners}
          sendChat={live.sendChat}
          appendMessage={live.appendMessage}
        />
      </div>
    </div>
  );
}

function Stage({
  hue,
  isLive,
  bursts,
  status,
}: {
  hue: number;
  isLive: boolean;
  bursts: Array<{ key: number }>;
  status: string;
}) {
  // Scatter the sparks across the stage so a busy room feels busy.
  const offsets = useMemo(() => bursts.map((b) => ({ ...b, left: 8 + (b.key * 37) % 84 })), [bursts]);

  return (
    <div className="stage" style={{ '--avatar-hue': hue } as React.CSSProperties}>
      <GlyphMark size={132} wave={false} className="stage-mark" title="" />
      <div className="spark-field" aria-hidden="true">
        {offsets.map((b) => (
          <span key={b.key} className="spark-fly" style={{ left: `${b.left}%` }} />
        ))}
      </div>
      {!isLive && (
        <span className="tag" style={{ position: 'absolute', bottom: 'var(--space-4)' }}>
          The room opens when the set starts
        </span>
      )}
      {isLive && status !== 'live' && (
        <span className="tag" style={{ position: 'absolute', bottom: 'var(--space-4)' }}>
          Finding the signal…
        </span>
      )}
    </div>
  );
}

function SetList({
  tracks,
  playingId,
}: {
  tracks: Array<{ id: number; title: string; durationS: number; plays: number }>;
  playingId: number | null;
}) {
  if (tracks.length === 0) return null;
  return (
    <section className="card">
      <div className="panel-head">
        <span className="label">The set</span>
        <span className="faint small">loops while the room is open</span>
      </div>
      <div className="tracklist">
        {tracks.map((t, i) => (
          <div key={t.id} className={`track${t.id === playingId ? ' track-playing' : ''}`}>
            <span className="track-num">{t.id === playingId ? '▍' : i + 1}</span>
            <span className="truncate">{t.title}</span>
            <span className="faint small tnum">{clock(t.durationS)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
