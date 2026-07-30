import { useEffect, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { CurrentLine, GlyphMark, Wordmark } from '../brand/marks';

const THEME_KEY = 'current.theme';
type Theme = 'dark' | 'light';

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // fall through to the dark default
  }
  return 'dark';
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // preference just won't persist
    }
  }, [theme]);

  function onSearch(event: React.FormEvent) {
    event.preventDefault();
    const q = query.trim();
    navigate(q ? `/discover?q=${encodeURIComponent(q)}` : '/discover');
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wrap topbar-inner">
          <Link to="/" aria-label="current — home" style={{ display: 'flex' }}>
            {/* 96px is the guide's minimum wordmark width. */}
            <Wordmark width={116} />
          </Link>

          <nav className="nav" aria-label="Primary">
            <NavLink to="/" className="nav-link" end>
              What&apos;s flowing
            </NavLink>
            <NavLink to="/discover" className="nav-link">
              Discover
            </NavLink>
            <NavLink to="/brand" className="nav-link">
              Brand
            </NavLink>
          </nav>

          <span className="topbar-spacer" />

          <form className="search-field" onSubmit={onSearch} role="search">
            <label className="sr-only" htmlFor="topbar-search">
              Search creators and sets
            </label>
            <input
              id="topbar-search"
              className="input"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search the current…"
            />
          </form>

          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? 'Shallows' : 'Depths'}
          </button>
        </div>
        {/* The current line as the header's bottom edge. */}
        <CurrentLine height={8} />
      </header>

      <main>{children}</main>

      <footer className="footer">
        <div className="wrap footer-cols">
          <div className="stack" style={{ gap: 'var(--space-3)', maxWidth: '34ch' }}>
            <Wordmark width={128} />
            <p className="muted small" style={{ margin: 0 }}>
              A live platform for music creators and their fans. Tune in, ride the wave, tell them it
              was good.
            </p>
          </div>

          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            <span className="label faint">Listen</span>
            <Link to="/" className="small muted">
              What&apos;s flowing
            </Link>
            <Link to="/discover" className="small muted">
              Discover creators
            </Link>
          </div>

          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            <span className="label faint">Make</span>
            <Link to="/brand" className="small muted">
              Brand system
            </Link>
            <span className="small faint">Creator tools — soon</span>
          </div>

          <GlyphMark size={44} plate />
        </div>
      </footer>
    </div>
  );
}
