import { Link } from 'react-router-dom';
import { GlyphMark, LiveNow } from '../brand/marks';
import type { Stream } from '../lib/api';
import { compact, elapsedSince, untilStart } from '../lib/format';
import { Avatar, Tags } from './ui';

export function StreamCard({
  stream,
  /**
   * The amber spark is reserved for one element per view, so only the lead card
   * carries it — every other live marker stays cool.
   */
  spark = false,
}: {
  stream: Stream;
  spark?: boolean;
}) {
  const { creator } = stream;
  return (
    <Link
      to={`/live/${stream.slug}`}
      className="card stream-card"
      style={{ '--avatar-hue': creator.hue } as React.CSSProperties}
    >
      <div className="stream-art">
        <div className="stream-art-badges">
          {stream.isLive ? (
            <LiveNow tone={spark ? 'spark' : 'cool'} />
          ) : (
            <span className="tag">
              {stream.scheduledAt ? untilStart(stream.scheduledAt) : 'Soon'}
            </span>
          )}
          {stream.isLive && (
            <span className="tag tnum">{compact(stream.listeners)} listening</span>
          )}
        </div>
        <GlyphMark size={72} wave={false} className="stream-art-mark" title="" />
      </div>

      <div className="stream-body">
        <h3 className="h3 clamp-2">{stream.title}</h3>
        <p className="stream-meta">
          <Avatar name={creator.name} hue={creator.hue} size={22} />
          <span className="truncate">{creator.name}</span>
          <span className="faint dot-sep">{creator.city}</span>
        </p>
        <p className="muted small clamp-2" style={{ margin: 0 }}>
          {stream.blurb}
        </p>
        <div className="spread" style={{ marginTop: 'var(--space-1)' }}>
          <Tags items={stream.tags} max={2} />
          <span className="faint small">
            {stream.isLive
              ? elapsedSince(stream.startedAt)
              : stream.scheduledAt
                ? untilStart(stream.scheduledAt)
                : ''}
          </span>
        </div>
      </div>
    </Link>
  );
}
