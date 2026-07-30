import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CurrentLine, GlyphMark, LiveNow } from '../brand/marks';
import { StreamCard } from '../components/StreamCard';
import { Avatar, ErrorState, Loading, Stat, Tags } from '../components/ui';
import { api } from '../lib/api';
import { clock, compact } from '../lib/format';
import { useAsync } from '../lib/useAsync';

export function Creator() {
  const { handle = '' } = useParams();
  const { data, error, loading, reload } = useAsync(() => api.creator(handle), [handle]);

  const [following, setFollowing] = useState(false);
  const [followers, setFollowers] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!data) return;
    setFollowing(data.isFollowing);
    setFollowers(data.creator.followers);
  }, [data]);

  if (loading) return <Loading label="Pulling up the profile…" />;
  if (error || !data) {
    return (
      <div className="wrap page">
        <ErrorState error={error ?? 'No creator by that name.'} onRetry={reload} />
      </div>
    );
  }

  const { creator, tracks, streams } = data;
  const liveNow = streams.find((s) => s.isLive);
  const totalPlays = tracks.reduce((sum, t) => sum + t.plays, 0);

  async function toggleFollow() {
    setBusy(true);
    const next = !following;
    setFollowing(next);
    setFollowers((n) => n + (next ? 1 : -1));
    try {
      const res = await api.follow(creator.handle, next);
      setFollowing(res.isFollowing);
      setFollowers(res.creator.followers);
    } catch {
      setFollowing(!next);
      setFollowers((n) => n + (next ? -1 : 1));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap page">
      <section className="hero" style={{ '--avatar-hue': creator.hue } as React.CSSProperties}>
        <GlyphMark size={300} wave={false} className="hero-mark" title="" />
        <div className="hero-inner">
          <div className="stack" style={{ gap: 'var(--space-4)' }}>
            {/* The single spark on this view, and only when they are on air. */}
            {liveNow && <LiveNow label="On air now" />}
            <div className="row" style={{ gap: 'var(--space-4)' }}>
              <Avatar name={creator.name} hue={creator.hue} size={72} ring={!!liveNow} />
              <div className="stack" style={{ gap: 2 }}>
                <h1 className="h1">{creator.name}</h1>
                <span className="muted small">
                  @{creator.handle} · {creator.city}
                </span>
              </div>
            </div>
            <p className="muted" style={{ margin: 0, maxWidth: '58ch' }}>
              {creator.bio}
            </p>
            <div className="row wrap-row" style={{ gap: 'var(--space-3)' }}>
              <button
                type="button"
                className={`btn${following ? '' : ' btn-primary'}`}
                onClick={toggleFollow}
                disabled={busy}
                aria-pressed={following}
              >
                {following ? 'Following' : 'Follow'}
              </button>
              <Tags items={creator.genres} max={4} />
            </div>
          </div>

          <div className="stat-row">
            <Stat label="In the current" value={compact(followers)} />
            <Stat label="Plays" value={compact(totalPlays)} />
            <Stat label="Tracks" value={tracks.length} />
          </div>
        </div>
      </section>

      {streams.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2 className="h2">{liveNow ? 'Live and upcoming' : 'Upcoming'}</h2>
          </div>
          <div className="grid grid-streams">
            {streams.map((s) => (
              <StreamCard key={s.id} stream={s} />
            ))}
          </div>
        </section>
      )}

      <CurrentLine className="divider" height={14} />

      <section className="section" style={{ marginTop: 0 }}>
        <div className="section-head">
          <h2 className="h2">Tracks</h2>
          <span className="label faint">{compact(totalPlays)} plays all in</span>
        </div>
        <div className="card tracklist">
          {tracks.map((t, i) => (
            <div key={t.id} className="track">
              <span className="track-num">{i + 1}</span>
              <span className="truncate">{t.title}</span>
              <span className="faint small tnum">
                {compact(t.plays)} plays · {clock(t.durationS)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
