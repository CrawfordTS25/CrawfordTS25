import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CurrentLine } from '../brand/marks';
import { CreatorCard } from '../components/CreatorCard';
import { StreamCard } from '../components/StreamCard';
import { Empty, ErrorState, Loading } from '../components/ui';
import { api, type Creator, type Stream } from '../lib/api';

export function Discover() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const [draft, setDraft] = useState(q);

  const [creators, setCreators] = useState<Creator[]>([]);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setDraft(q), [q]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);

    const load = q
      ? api.search(q).then((r) => ({ creators: r.creators, streams: r.streams }))
      : Promise.all([api.creators(), api.streams('all')]).then(([c, s]) => ({
          creators: c.creators,
          streams: s.streams,
        }));

    load
      .then((r) => {
        if (!live) return;
        setCreators(r.creators);
        setStreams(r.streams);
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(err instanceof Error ? err.message : 'search went sideways');
      })
      .finally(() => {
        if (live) setLoading(false);
      });

    return () => {
      live = false;
    };
  }, [q]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    setParams(next ? { q: next } : {}, { replace: true });
  }

  const nothing = !loading && !error && creators.length === 0 && streams.length === 0;

  return (
    <div className="wrap page">
      <header className="stack" style={{ gap: 'var(--space-4)', maxWidth: '60ch' }}>
        <h1 className="h1">Find your current</h1>
        <p className="muted" style={{ margin: 0 }}>
          Search by name, genre, city or the mood you are after. Everything here is made by people who
          are usually in the chat too.
        </p>
        <form onSubmit={submit} role="search" className="row" style={{ gap: 'var(--space-2)' }}>
          <label className="sr-only" htmlFor="discover-search">
            Search creators and sets
          </label>
          <input
            id="discover-search"
            className="input"
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="bass, Lisbon, choral, breaks…"
          />
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>
      </header>

      <CurrentLine className="divider" height={14} />

      {loading && <Loading label={q ? `Looking for “${q}”…` : 'Loading the roster…'} />}
      {error && <ErrorState error={error} onRetry={() => setParams(q ? { q } : {})} />}

      {nothing && (
        <Empty title={`Nothing matches “${q}”`}>
          Try a genre, a city, or a single word. The catalogue is small and opinionated.
        </Empty>
      )}

      {!loading && !error && streams.length > 0 && (
        <section className="section" style={{ marginTop: 0 }}>
          <div className="section-head">
            <h2 className="h2">{q ? 'Matching sets' : 'Every set'}</h2>
            <span className="label faint">
              {streams.filter((s) => s.isLive).length} live right now
            </span>
          </div>
          <div className="grid grid-streams">
            {streams.map((s) => (
              <StreamCard key={s.id} stream={s} />
            ))}
          </div>
        </section>
      )}

      {!loading && !error && creators.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2 className="h2">{q ? 'Matching creators' : 'Creators'}</h2>
          </div>
          <div className="grid grid-creators">
            {creators.map((c) => (
              <CreatorCard key={c.id} creator={c} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
