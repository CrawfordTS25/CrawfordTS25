import { beforeEach, describe, expect, it } from 'vitest';
import { openDb, seed, type DB } from '../db';
import * as repo from '../repo';

let db: DB;

beforeEach(() => {
  db = openDb(':memory:');
  seed(db, Date.now());
});

describe('seed', () => {
  it('creates creators, tracks and streams', () => {
    expect(repo.listCreators(db).length).toBeGreaterThan(0);
    const nrissa = repo.getCreatorByHandle(db, 'nrissa');
    expect(nrissa).not.toBeNull();
    expect(repo.listTracks(db, nrissa!.id).length).toBeGreaterThan(0);
  });

  it('is idempotent — seeding twice does not duplicate', () => {
    const before = repo.listCreators(db).length;
    seed(db, Date.now());
    expect(repo.listCreators(db).length).toBe(before);
  });

  it('keeps every creator tint inside the brand’s cool water band', () => {
    // The guide forbids recolouring outside the palette; tinted artwork is
    // derived from these hues, so they must stay between Aqua and Deep.
    for (const c of repo.listCreators(db)) {
      expect(c.hue, `@${c.handle}`).toBeGreaterThanOrEqual(140);
      expect(c.hue, `@${c.handle}`).toBeLessThanOrEqual(238);
    }
  });
});

describe('listStreams', () => {
  it('filters live and upcoming', () => {
    const live = repo.listStreams(db, 'live');
    const upcoming = repo.listStreams(db, 'upcoming');
    expect(live.length).toBeGreaterThan(0);
    expect(upcoming.length).toBeGreaterThan(0);
    expect(live.every((s) => s.isLive)).toBe(true);
    expect(upcoming.every((s) => !s.isLive)).toBe(true);
    expect(live.length + upcoming.length).toBe(repo.listStreams(db, 'all').length);
  });

  it('orders the biggest live room first', () => {
    const live = repo.listStreams(db, 'live');
    for (let i = 1; i < live.length; i++) {
      expect(live[i - 1].listenerBase).toBeGreaterThanOrEqual(live[i].listenerBase);
    }
  });

  it('parses JSON columns into arrays', () => {
    const [first] = repo.listStreams(db, 'live');
    expect(Array.isArray(first.tags)).toBe(true);
    expect(Array.isArray(first.creator.genres)).toBe(true);
  });
});

describe('nowPlaying', () => {
  it('is null for a stream that is not live', () => {
    const upcoming = repo.listStreams(db, 'upcoming')[0];
    expect(repo.nowPlaying(db, upcoming)).toBeNull();
  });

  it('picks the track the playhead is sitting in', () => {
    const stream = repo.getStreamBySlug(db, 'nrissa-undertow-session')!;
    const tracks = repo.listTracks(db, stream.creator.id);

    // 10 seconds after the set began we are in the first track.
    const early = repo.nowPlaying(db, stream, stream.startedAt + 10_000)!;
    expect(early.track.id).toBe(tracks[0].id);
    expect(early.position).toBe(10);
    expect(early.index).toBe(0);
    expect(early.of).toBe(tracks.length);

    // Five seconds into the second track.
    const at = stream.startedAt + (tracks[0].durationS + 5) * 1000;
    const second = repo.nowPlaying(db, stream, at)!;
    expect(second.track.id).toBe(tracks[1].id);
    expect(second.position).toBe(5);
    expect(second.index).toBe(1);
  });

  it('loops the set so a long-running room always has something playing', () => {
    const stream = repo.getStreamBySlug(db, 'nrissa-undertow-session')!;
    const tracks = repo.listTracks(db, stream.creator.id);
    const total = tracks.reduce((sum, t) => sum + t.durationS, 0);

    // Exactly one full pass later we are back at the top.
    const wrapped = repo.nowPlaying(db, stream, stream.startedAt + total * 1000)!;
    expect(wrapped.track.id).toBe(tracks[0].id);
    expect(wrapped.position).toBe(0);

    // And still valid a hundred passes in.
    const late = repo.nowPlaying(db, stream, stream.startedAt + total * 100 * 1000 + 3_000)!;
    expect(late.track.id).toBe(tracks[0].id);
    expect(late.position).toBe(3);
  });

  it('never reports a position past the track length', () => {
    const stream = repo.getStreamBySlug(db, 'amaris-vigil-listening')!;
    const total = repo
      .listTracks(db, stream.creator.id)
      .reduce((sum, t) => sum + t.durationS, 0);
    for (let offset = 0; offset < total; offset += 37) {
      const np = repo.nowPlaying(db, stream, stream.startedAt + offset * 1000)!;
      expect(np.position).toBeGreaterThanOrEqual(0);
      expect(np.position).toBeLessThan(np.track.durationS);
    }
  });
});

describe('follows', () => {
  it('toggles and moves the follower count', () => {
    const creator = repo.getCreatorByHandle(db, 'brk')!;
    const base = creator.followers;
    repo.upsertUser(db, 'user-aaaaaa');

    expect(repo.isFollowing(db, 'user-aaaaaa', creator.id)).toBe(false);

    repo.setFollow(db, 'user-aaaaaa', creator.id, true);
    expect(repo.isFollowing(db, 'user-aaaaaa', creator.id)).toBe(true);
    expect(repo.getCreatorByHandle(db, 'brk')!.followers).toBe(base + 1);

    // Following twice must not double-count.
    repo.setFollow(db, 'user-aaaaaa', creator.id, true);
    expect(repo.getCreatorByHandle(db, 'brk')!.followers).toBe(base + 1);

    repo.setFollow(db, 'user-aaaaaa', creator.id, false);
    expect(repo.isFollowing(db, 'user-aaaaaa', creator.id)).toBe(false);
    expect(repo.getCreatorByHandle(db, 'brk')!.followers).toBe(base);
  });
});

describe('messages', () => {
  it('returns the backlog oldest-first and caps it', () => {
    const stream = repo.getStreamBySlug(db, 'nrissa-undertow-session')!;
    for (let i = 0; i < 12; i++) {
      repo.addMessage(db, {
        streamId: stream.id,
        userId: 'user-bbbbbb',
        author: 'tester',
        body: `line ${i}`,
      });
    }
    const all = repo.listMessages(db, stream.id, 5);
    expect(all).toHaveLength(5);
    // Oldest first within the window, and the window is the most recent five.
    expect(all[0].body).toBe('line 7');
    expect(all[4].body).toBe('line 11');
    for (let i = 1; i < all.length; i++) {
      expect(all[i].id).toBeGreaterThan(all[i - 1].id);
    }
  });
});

describe('search', () => {
  it('matches a creator by genre', () => {
    const { creators } = repo.search(db, 'choral');
    expect(creators.map((c) => c.handle)).toContain('amaris');
  });

  it('matches a creator by city, case-insensitively', () => {
    const { creators } = repo.search(db, 'LISBON');
    expect(creators.map((c) => c.handle)).toContain('nrissa');
  });

  it('matches a stream by tag', () => {
    const { streams } = repo.search(db, 'vinyl only');
    expect(streams.map((s) => s.slug)).toContain('brk-crate-depth');
  });

  it('returns nothing for nonsense', () => {
    const { creators, streams } = repo.search(db, 'zzzznope');
    expect(creators).toHaveLength(0);
    expect(streams).toHaveLength(0);
  });

  it('treats % and _ as literal text rather than wildcards', () => {
    // A naive LIKE build would make "%" match everything.
    const { creators, streams } = repo.search(db, '%');
    expect(creators.length + streams.length).toBe(0);
  });
});

describe('sparks and peak', () => {
  it('counts sparks per stream', () => {
    const a = repo.getStreamBySlug(db, 'nrissa-undertow-session')!;
    const b = repo.getStreamBySlug(db, 'kito-blue-hour')!;
    repo.addSpark(db, a.id, 'user-cccccc');
    repo.addSpark(db, a.id, 'user-cccccc');
    repo.addSpark(db, b.id, 'user-cccccc');
    expect(repo.countSparks(db, a.id)).toBe(2);
    expect(repo.countSparks(db, b.id)).toBe(1);
  });

  it('only ever raises the peak', () => {
    const stream = repo.getStreamBySlug(db, 'kito-blue-hour')!;
    const start = stream.peakListeners;
    repo.updatePeak(db, stream.id, start + 500);
    expect(repo.getStreamById(db, stream.id)!.peakListeners).toBe(start + 500);
    repo.updatePeak(db, stream.id, 1);
    expect(repo.getStreamById(db, stream.id)!.peakListeners).toBe(start + 500);
  });
});

describe('users', () => {
  it('mints a name on first sight and renames on request', () => {
    const first = repo.upsertUser(db, 'abcdef123456');
    expect(first.displayName).toMatch(/^listener_/);
    const renamed = repo.upsertUser(db, 'abcdef123456', '  Tide  ');
    expect(renamed.displayName).toBe('Tide');
    expect(repo.getUser(db, 'abcdef123456')!.displayName).toBe('Tide');
  });

  it('keeps the existing name when none is supplied', () => {
    repo.upsertUser(db, 'ghijkl123456', 'Foam');
    expect(repo.upsertUser(db, 'ghijkl123456').displayName).toBe('Foam');
  });
});
