/**
 * Server entry. In development Vite serves the client and proxies /api and /ws
 * here. In production this process serves the built client too, so `npm start`
 * is the whole app on one port.
 */

import express from 'express';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocketServer } from 'ws';
import { openDb, seed } from './db';
import { createApi } from './api';
import { LiveHub } from './live';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

export function createApp(options: { dbFile?: string } = {}) {
  const db = openDb(options.dbFile);
  seed(db);

  const hub = new LiveHub(db);
  const app = express();
  app.disable('x-powered-by');

  app.use('/api', createApi(db, hub));

  const dist = join(root, 'dist');
  if (existsSync(dist)) {
    app.use(
      express.static(dist, {
        setHeaders(res, path) {
          // Hashed bundles are immutable; the shell must never be cached.
          if (path.endsWith('index.html')) res.setHeader('Cache-Control', 'no-cache');
          else if (/\.[0-9a-f]{8,}\./.test(path)) {
            res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
          }
        },
      }),
    );
    // Client-side routing: anything not an API call gets the shell.
    app.get(/^(?!\/api\/).*/, (_req, res) => res.sendFile(join(dist, 'index.html')));
  }

  return { app, db, hub };
}

export function startServer(port = Number(process.env.PORT ?? 8787)) {
  const { app, db, hub } = createApp({ dbFile: process.env.CURRENT_DB ?? ':memory:' });
  const server = createServer(app);
  const wss = new WebSocketServer({ server, path: '/ws' });
  hub.attach(wss);
  hub.start();

  server.listen(port, () => {
    console.log(`\n  current · listening on http://localhost:${port}\n`);
  });

  const shutdown = () => {
    hub.stop();
    wss.close();
    server.close(() => {
      db.close();
      process.exit(0);
    });
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  return { server, wss, hub, db };
}

// Only auto-start when run directly, so tests can import createApp freely.
const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]).startsWith(resolve(here, 'index'));
if (invokedDirectly) startServer();
