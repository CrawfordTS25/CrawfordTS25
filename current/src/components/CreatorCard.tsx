import { Link } from 'react-router-dom';
import type { Creator } from '../lib/api';
import { compact } from '../lib/format';
import { Avatar, Tags } from './ui';

export function CreatorCard({ creator }: { creator: Creator }) {
  return (
    <Link to={`/c/${creator.handle}`} className="card creator-card">
      <Avatar name={creator.name} hue={creator.hue} size={52} />
      <div className="stack" style={{ gap: 2 }}>
        <span className="h3">{creator.name}</span>
        <span className="faint small">@{creator.handle}</span>
      </div>
      <p className="muted small clamp-2" style={{ margin: 0 }}>
        {creator.tagline}
      </p>
      <div className="spread" style={{ width: '100%', marginTop: 'auto' }}>
        <Tags items={creator.genres} max={2} />
        <span className="faint small tnum">{compact(creator.followers)} in the current</span>
      </div>
    </Link>
  );
}
