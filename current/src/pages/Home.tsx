/**
 * "What's flowing" — the front page. Leads with the biggest room that is live
 * right now, then everything else on air, then what is coming up.
 *
 * The amber spark appears exactly once on this view: on the hero's live badge.
 */

import { Link } from 'react-router-dom';
import { CurrentLine, GlyphMark, LiveNow } from '../brand/marks';
import { StreamCard } from '../components/StreamCard';
import { Avatar, ErrorState, Loading, Stat, Tags, Empty } from '../components/ui';
import { api, type Stream } from '../lib/api';
import { compact, elapsedSince } from '../lib/format';
import { useAsync } from '../lib/useAsync';

export function Home() {
  const { data, error, loading, reload } = useAsync(() => api.streams('all'), []);

  if (loading) return <Loading label="Seeing what's flowing…" />;
  if (error) return <div className="wrap page"><ErrorState error={error} onRetry={reload} /></div>;

  const streams = data?.streams ?? [];
  const live = streams.filter((s) => s.isLive);
  const upcoming = streams.filter((s) => !s.isLive);
  const [hero, ...rest] = live;

  return (
    <div className="wrap page">
      {hero ? <Hero stream={hero} /> : <NothingLive />}

      {rest.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2 className="h2">Also on air</h2>
            <Link to="/discover" className="small muted">
              Browse everything →
            </Link>
          </div>
          <div className="grid grid-streams">
            {rest.map((s) => (
              <StreamCard key={s.id} stream={s} />
            ))}
          </div>
        </section>
      )}

      {upcoming.length > 0 && (
        <>
          <CurrentLine className="divider" height={14} />
          <section className="section" style={{ marginTop: 0 }}>
            <div className="section-head">
              <h2 className="h2">Coming up</h2>
              <span className="label faint">Set a reminder, catch the current</span>
            </div>
            <div className="grid grid-streams">
              {upcoming.map((s) => (
                <StreamCard key={s.id} stream={s} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Hero({ stream }: { stream: Stream }) {
  const { creator } = stream;
  return (
    <section className="hero" style={{ '--avatar-hue': creator.hue } as React.CSSProperties}>
      <GlyphMark size={340} wave={false} className="hero-mark" title="" />
      <div className="hero-inner">
        <div className="stack" style={{ gap: 'var(--space-4)' }}>
          {/* The one spark on this page. */}
          <div className="row wrap-row" style={{ gap: 'var(--space-3)' }}>
            <LiveNow />
            <span className="label faint">{elapsedSince(stream.startedAt)}</span>
          </div>

          <h1 className="h1">{stream.title}</h1>
          <p className="muted" style={{ margin: 0, maxWidth: '52ch' }}>
            {stream.blurb}
          </p>

          <Link to={`/c/${creator.handle}`} className="row" style={{ gap: 'var(--space-3)' }}>
            <Avatar name={creator.name} hue={creator.hue} size={44} ring />
            <span className="stack" style={{ gap: 1 }}>
              <span className="h3">{creator.name}</span>
              <span className="faint small">
                @{creator.handle} · {creator.city}
              </span>
            </span>
          </Link>

          <div className="row wrap-row" style={{ gap: 'var(--space-3)' }}>
            <Link to={`/live/${stream.slug}`} className="btn btn-primary">
              Tune in
            </Link>
            <Tags items={stream.tags} max={3} />
          </div>
        </div>

        <div className="stack" style={{ gap: 'var(--space-4)' }}>
          <div className="stat-row">
            <Stat label="Listening now" value={compact(stream.listeners)} />
            <Stat label="Peak" value={compact(stream.peakListeners)} />
            <Stat label="Sparks" value={compact(stream.sparks)} />
          </div>
          {stream.nowPlaying && (
            <div className="stack" style={{ gap: 'var(--space-2)' }}>
              <span className="label faint">Now playing</span>
              <span className="h3 truncate">{stream.nowPlaying.track.title}</span>
              <CurrentLine
                progress={stream.nowPlaying.position / stream.nowPlaying.track.durationS}
                height={16}
                aria-label="Set progress"
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function NothingLive() {
  return (
    <Empty title="Nothing live this second">
      The water is still. Check what&apos;s coming up, or follow a few creators so you hear the moment
      they go on.
    </Empty>
  );
}
