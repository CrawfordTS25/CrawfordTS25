/** Typed client for the `current` API. */

import { userId } from './identity';

export type Creator = {
  id: number;
  handle: string;
  name: string;
  tagline: string;
  bio: string;
  city: string;
  genres: string[];
  hue: number;
  followers: number;
};

export type Track = {
  id: number;
  title: string;
  durationS: number;
  plays: number;
  position: number;
};

export type NowPlaying = {
  track: Track;
  position: number;
  index: number;
  of: number;
};

export type Stream = {
  id: number;
  slug: string;
  title: string;
  blurb: string;
  tags: string[];
  isLive: boolean;
  startedAt: number;
  scheduledAt: number | null;
  peakListeners: number;
  creator: Creator;
  listeners: number;
  nowPlaying: NowPlaying | null;
  sparks: number;
};

export type Message = {
  id: number;
  streamId: number;
  userId: string;
  author: string;
  body: string;
  createdAt: number;
};

export type Me = { id: string; displayName: string; following: number[] };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'x-current-user': userId(),
      ...(init.body ? { 'content-type': 'application/json' } : {}),
      ...init.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) detail = body.error;
    } catch {
      // keep the status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  me: () => request<Me>('/me'),

  rename: (displayName: string) =>
    request<Me>('/me', { method: 'PATCH', body: JSON.stringify({ displayName }) }),

  streams: (filter: 'live' | 'upcoming' | 'all' = 'all') =>
    request<{ streams: Stream[] }>(`/streams?filter=${filter}`),

  stream: (slug: string) =>
    request<{ stream: Stream; tracks: Track[]; messages: Message[]; isFollowing: boolean }>(
      `/streams/${encodeURIComponent(slug)}`,
    ),

  postMessage: (slug: string, body: string) =>
    request<{ message: Message }>(`/streams/${encodeURIComponent(slug)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  spark: (slug: string) =>
    request<{ sparks: number }>(`/streams/${encodeURIComponent(slug)}/sparks`, { method: 'POST' }),

  creators: () => request<{ creators: Creator[] }>('/creators'),

  creator: (handle: string) =>
    request<{ creator: Creator; tracks: Track[]; streams: Stream[]; isFollowing: boolean }>(
      `/creators/${encodeURIComponent(handle)}`,
    ),

  follow: (handle: string, following: boolean) =>
    request<{ creator: Creator; isFollowing: boolean }>(
      `/creators/${encodeURIComponent(handle)}/follow`,
      { method: 'PUT', body: JSON.stringify({ following }) },
    ),

  search: (q: string) =>
    request<{ query: string; creators: Creator[]; streams: Stream[] }>(
      `/search?q=${encodeURIComponent(q)}`,
    ),
};
