import { Link, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { Empty } from './components/ui';
import { Brand } from './pages/Brand';
import { Creator } from './pages/Creator';
import { Discover } from './pages/Discover';
import { Home } from './pages/Home';
import { Live } from './pages/Live';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/live/:slug" element={<Live />} />
        <Route path="/c/:handle" element={<Creator />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/brand" element={<Brand />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}

function NotFound() {
  return (
    <div className="wrap page">
      <Empty title="That page drifted off">
        Nothing here. <Link to="/" style={{ color: 'var(--c-aqua)' }}>Head back to what&apos;s flowing</Link>.
      </Empty>
    </div>
  );
}
