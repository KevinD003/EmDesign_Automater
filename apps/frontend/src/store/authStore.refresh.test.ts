/**
 * CTO A15/N5 — the 401 recovery handler the auth store registers.
 *
 * The defect: GoTrue access tokens live ~an hour, the stored refreshToken was
 * never used, no 401 handler existed, and the session was never cleared — so
 * cloud save silently broke mid-session while AuthBar kept showing
 * "signed in". These pin the three handler outcomes: refresh succeeds (new
 * token adopted + returned), refresh fails (session cleared, null), and
 * local-profile sessions (no refresh grant — clear immediately).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Session } from '../lib/auth';

const mocks = vi.hoisted(() => ({
  setAuthToken: vi.fn<(t: string | null) => void>(),
  refresh: vi.fn<(t: string) => Promise<Session>>(),
  handler: { current: null as (() => Promise<string | null>) | null },
  entries: new Map<string, string>(),
}));

vi.mock('../api/client', () => ({
  setAuthToken: mocks.setAuthToken,
  setUnauthorizedHandler: (fn: (() => Promise<string | null>) | null) => {
    mocks.handler.current = fn;
  },
  api: { login: vi.fn(), signup: vi.fn(), refresh: mocks.refresh },
}));

vi.mock('../lib/storage', () => ({
  browserKV: () => ({
    getItem: (k: string) => mocks.entries.get(k) ?? null,
    setItem: (k: string, v: string) => void mocks.entries.set(k, v),
    removeItem: (k: string) => void mocks.entries.delete(k),
  }),
}));

import { useAuthStore } from './authStore';

const SUPA: Session = {
  accessToken: 'old-access', refreshToken: 'old-refresh', userId: 'u1',
  email: 'a@b.co', provider: 'supabase',
};

beforeEach(() => {
  mocks.entries.clear();
  mocks.refresh.mockReset();
  useAuthStore.setState({ session: null });
  useAuthStore.getState().init();
});

describe('401 recovery handler', () => {
  it('refreshes once and adopts the renewed session', async () => {
    useAuthStore.setState({ session: SUPA });
    mocks.refresh.mockResolvedValue({ ...SUPA, accessToken: 'new-access', refreshToken: 'new-refresh' });
    const token = await mocks.handler.current!();
    expect(token).toBe('new-access');
    expect(useAuthStore.getState().session?.accessToken).toBe('new-access');
    expect(mocks.setAuthToken).toHaveBeenCalledWith('new-access');
  });

  it('clears the session when the refresh grant fails', async () => {
    useAuthStore.setState({ session: SUPA });
    mocks.refresh.mockRejectedValue(new Error('401 revoked'));
    const token = await mocks.handler.current!();
    expect(token).toBeNull();
    expect(useAuthStore.getState().session).toBeNull();
    expect(mocks.setAuthToken).toHaveBeenLastCalledWith(null);
  });

  it('clears immediately for local-profile sessions (no refresh grant exists)', async () => {
    useAuthStore.setState({ session: { ...SUPA, provider: 'local' } });
    const token = await mocks.handler.current!();
    expect(token).toBeNull();
    expect(mocks.refresh).not.toHaveBeenCalled();
    expect(useAuthStore.getState().session).toBeNull();
  });
});
