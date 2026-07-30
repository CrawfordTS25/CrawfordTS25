# current

A live platform for music creators and their fans, built to **Brand Guide v1.0**.

The identity holds all three meanings of the word at once — a river current
(flow), the current moment (now), and electric current (energy). That is not
just a tagline here: the water gradient carries every surface, the amber spark
means *live*, and the current line does the work of dividers, progress bars and
loading states.

```sh
npm install
npm run dev     # client on :5173, API + sockets on :8787
```

Or run the whole thing on one port:

```sh
npm run preview # build, then serve at http://localhost:8787
```

## What it does

- **What's flowing** — the front page leads with the biggest room that is live
  right now, then everything else on air, then what is coming up.
- **Live rooms** — every listener in a room shares one playhead (the same second
  of the same track), one listener count, and one chat. Sparks fly up the stage
  when the room reacts.
- **Creators** — profile, catalogue, play counts, and a follow that sticks.
- **Discover** — search by name, genre, city or mood.
- **Brand** — the identity as built, rendered from the same tokens and geometry
  the product uses. If it drifts there, it has drifted in the app.

No signup wall. A local id is minted on first visit so you can chat, spark and
follow immediately; name yourself whenever you feel like it.

## How it is put together

```
brand/            the identity, as code
  tokens.json       single source of truth — colour, type, space, motion, rules
  lib/geometry.mts  glyph scanlines, tapered-ribbon outlines, smooth curves
  lib/wordmark.mts  constructs the wordmark from real font outlines
  build-assets.mts  emits every derived artefact (see below)
  assets/           locked SVG lockups: primary, light, mono, icon, motif

server/
  db.ts             SQLite schema + seed
  repo.ts           queries, including the derived playhead
  live.ts           the WebSocket hub: presence, playhead, chat, sparks
  api.ts            REST surface
  index.ts          wiring; serves the built client in production

src/
  brand/            React marks (generated geometry + tokens)
  lib/              API client, live socket hook, formatters
  components/       shell, cards, chat, shared UI
  pages/            Home, Live, Creator, Discover, Brand
```

`npm run brand:build` regenerates everything downstream of `brand/tokens.json`:

| Generated | What it is |
| --- | --- |
| `src/styles/tokens.css` | tokens as CSS custom properties, light + dark |
| `src/brand/geometry.ts` | measured wordmark, glyph mark and motif geometry |
| `src/brand/tokens.ts` | tokens for the brand page |
| `brand/assets/*.svg` | locked lockups at every variant |
| `public/favicon.svg`, `public/icon-512.svg`, `public/manifest.webmanifest` | app icons |

Edit `brand/tokens.json`, never the generated files.

## The wordmark

The guide asks for the current line and the t-crossbar to be **one continuous
path**, and flags rebuilding the wordmark as true vector art as pre-production
work. That is what `brand/build-assets.mts` does, at build time:

1. It reads the real Bricolage Grotesque SemiBold outlines and sets `current`
   glyph by glyph at the specified −3% tracking, so every letter position is
   known rather than guessed.
2. It **measures** the lowercase `t` by scanlining the glyph — finding the band
   whose ink is much wider than the stem below it. That yields the crossbar's
   centre line (y = −470.55), its weight (102.53 units) and its extents.
3. It builds the current line as a **tapered ribbon**: a closed outline around a
   centreline whose weight varies along its length. The line ripples beneath the
   word, thins to slip behind the n, then swells to *exactly* the measured
   crossbar weight and runs the crossbar's full width — so the two are one form,
   not two shapes that happen to touch. Past the crossbar it lifts clear of the
   letter and crests in the spark.

A uniform stroke cannot do this. Reaching a crossbar 530 units above the ripple
at nearly the same x forces the line either to collide with the letterforms or
to close a bowl that reads as a parenthesis. Tapering is what a designer would
reach for — water thins and swells — and it resolves both.

Everything about the mark is therefore derived, so the tests can check it:
`brand/__tests__/brand.test.ts` asserts the ribbon's swell equals the measured
crossbar, that it is a single closed outline, that the spark sits above and
right of the crossbar inside the lockup, that clearspace equals the height of
the `c`, and that no lockup carries a shadow, glow, outline or bevel.

### Brand rules the code enforces

- **One spark per view.** The amber accent is reserved for the live indicator.
  Feeds mark only the lead room with it; every other live badge uses
  `tone="cool"`. Low-opacity watermarks drop the amber wave entirely — at 14%
  it muddies to olive, and it is not an accent's job to decorate.
- **Bricolage for headlines only.** `--font-display` appears in exactly two
  places in `base.css`, both bound to `.h1`/`.h2`. A test counts them.
- **Minimum sizes.** `<Wordmark>` clamps to 96px wide. `<GlyphMark>` drops the
  wave below the 24px icon floor on its own.
- **Palette discipline.** Creator artwork is tinted, so creator hues are held
  inside the water band (Aqua ≈ 166° → Deep ≈ 230°) — a test guards it.
- **Always lowercase, never stretched.** The mark is geometry, not text, so it
  cannot be re-cased; lockups preserve their viewBox aspect.

## Testing

```sh
npm test        # 89 unit/integration tests: API, live hub, repo, brand conformance
npm run smoke   # 17 end-to-end checks in a real browser, with screenshots
```

`npm test` covers the REST surface, the playhead maths (including looping a set
for a hundred passes), follow accounting, LIKE-injection in search, the live hub
over real WebSockets (fan-out, room isolation, rate limiting, malformed frames),
and brand conformance.

`npm run smoke` drives the built app in Chromium against a running server: it
tunes in, watches the playhead advance, sends a spark and a chat message, then
opens a **second browser** in the same room and checks each one sees the other's
messages and the presence bump. It also checks the light theme swaps the
gradient and keeps text readable on the dark artwork plates, that the live room
does not scroll sideways at 390px, and that no console errors appeared anywhere.

Start the server first:

```sh
npm run build && npm start   # then, in another shell:
npm run smoke
```

Screenshots land in `screenshots/`. Brand contact sheets:

```sh
npx tsx scripts/render-brand.mts   # → brand/preview/
```

## Notes

- **Storage.** SQLite, in memory by default. Set `CURRENT_DB=./data/current.db`
  to persist across restarts.
- **Playhead.** Derived from each stream's `started_at` against its set list
  rather than stored, so every client agrees on the current second without any
  synchronisation, and a room that has been up for hours always has something
  playing.
- **Listener counts.** The room's real socket count plus a drifting simulated
  audience, so the number moves like a live room does — and your own arrival
  visibly bumps it.
- **Offline.** Webfonts are bundled via `@fontsource-variable`, so the app needs
  no network at runtime. The `.ttf` in `brand/fonts/` is build-time only.
