import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Session } from '../../lib/auth';
import type { FetchLike } from './localAuth';

/** Hoisted so the vi.mock factories below (which run before imports) can close over them. */
const mocks = vi.hoisted(() => ({
  setAuthToken: vi.fn<(token: string | null) => void>(),
  entries: new Map<string, string>(),
  kv: { throws: false },
}));

// api/client and lib/storage are leaf modules: mocking them isolates the glue from the
// real bearer header and from localStorage, which does not exist in the node test env.
vi.mock('../../api/client', () => ({
  setAuthToken: mocks.setAuthToken,
  api: { login: vi.fn(), signup: vi.fn() },
}));

vi.mock('../../lib/storage', () => ({
  browserKV: () => {
    if (mocks.kv.throws) throw new Error('localStorage unavailable');
    return {
      getItem: (k: string) => mocks.entries.get(k) ?? null,
      setItem: (k: string, v: string) => void mocks.entries.set(k, v),
      removeItem: (k: string) => void mocks.entries.delete(k),
    };
  },
}));

const { useAuthStore } = await import('../../store/authStore');
const { adoptLocalSession, loginAndAdopt, createAndAdopt } = await import('./localSession');

const SESSION_KEY = 'stitchiq:session';

const LOCAL: Session = {
  accessToken: 'tok-1',
  userId: 'local-abc',
  username: 'Dana',
  provider: 'local',
};

/** Minimal Response stand-in: the helpers only read ok/status/statusText/json. */
function stub(body: unknown): FetchLike {
  return vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  })) as unknown as FetchLike;
}

beforeEach(() => {
  mocks.setAuthToken.mockClear();
  mocks.entries.clear();
  mocks.kv.throws = false;
});

afterEach(() => {
  useAuthStore.setState({ session: null });
});

describe('adoptLocalSession', () => {
  it('sets the bearer token, persists the session, and fills the auth store', () => {
    adoptLocalSession(LOCAL);
    expect(mocks.setAuthToken).toHaveBeenCalledWith('tok-1');
    expect(JSON.parse(mocks.entries.get(SESSION_KEY) as string)).toEqual(LOCAL);
    expect(useAuthStore.getState().session).toEqual(LOCAL);
  });

  it('still sets token and store state when localStorage is unavailable', () => {
    mocks.kv.throws = true;
    expect(() => adoptLocalSession(LOCAL)).not.toThrow();
    expect(mocks.setAuthToken).toHaveBeenCalledWith('tok-1');
    expect(mocks.entries.size).toBe(0);
    expect(useAuthStore.getState().session).toEqual(LOCAL);
  });
});

describe('loginAndAdopt / createAndAdopt', () => {
  it('adopts the session returned by a local login', async () => {
    const fetchFn = stub({ accessToken: 'tok-2', userId: 'local-def', username: 'Rae', hasPin: true });
    const session = await loginAndAdopt('Rae', '1234', fetchFn);
    expect(session.provider).toBe('local');
    expect(mocks.setAuthToken).toHaveBeenCalledWith('tok-2');
    expect(useAuthStore.getState().session).toEqual(session);
    expect(fetchFn).toHaveBeenCalledWith('/api/auth/local/login', expect.anything());
  });

  it('adopts the session returned by a profile creation', async () => {
    const fetchFn = stub({ accessToken: 'tok-3', userId: 'local-ghi', username: 'Sam', hasPin: false });
    const session = await createAndAdopt('Sam', undefined, fetchFn);
    expect(useAuthStore.getState().session).toEqual({
      accessToken: 'tok-3',
      userId: 'local-ghi',
      username: 'Sam',
      provider: 'local',
    });
    expect(JSON.parse(mocks.entries.get(SESSION_KEY) as string)).toEqual(session);
    expect(fetchFn).toHaveBeenCalledWith('/api/auth/local/profiles', expect.anything());
  });

  it('leaves the store untouched when the login request fails', async () => {
    const failing = vi.fn(async () => ({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'invalid username or PIN' }),
    })) as unknown as FetchLike;
    await expect(loginAndAdopt('Dana', 'wrong', failing)).rejects.toThrow('invalid username or PIN');
    expect(useAuthStore.getState().session).toBeNull();
    expect(mocks.setAuthToken).not.toHaveBeenCalled();
  });
});
