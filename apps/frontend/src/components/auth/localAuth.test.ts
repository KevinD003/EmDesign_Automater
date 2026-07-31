import { describe, it, expect, vi } from 'vitest';
import {
  listLocalProfiles,
  createLocalProfile,
  loginLocalProfile,
  logoutLocalProfile,
  type FetchLike,
} from './localAuth';

/** Minimal Response stand-in: these helpers only read ok/status/statusText/json. */
function jsonRes(body: unknown, init?: { ok?: boolean; status?: number; statusText?: string }): Response {
  return {
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    statusText: init?.statusText ?? 'OK',
    json: async () => body,
  } as Response;
}

/** 204 has no body: json() rejects, so nothing may parse it. */
function noContentRes(): Response {
  return {
    ok: true,
    status: 204,
    statusText: 'No Content',
    json: async () => {
      throw new Error('204 has no body');
    },
  } as unknown as Response;
}

function stub(res: Response): FetchLike {
  return vi.fn(async () => res) as unknown as FetchLike;
}

describe('localAuth helpers', () => {
  it('maps a login response onto a local Session', async () => {
    const fetchFn = stub(
      jsonRes({ accessToken: 'tok-1', userId: 'local-abc', username: 'Dana', hasPin: true }),
    );
    const session = await loginLocalProfile('Dana', '1234', fetchFn);
    expect(session).toEqual({
      accessToken: 'tok-1',
      userId: 'local-abc',
      username: 'Dana',
      provider: 'local',
    });
    expect(fetchFn).toHaveBeenCalledWith('/api/auth/local/login', expect.anything());
  });

  it('throws the FastAPI detail on a 401 login', async () => {
    const fetchFn = stub(
      jsonRes({ detail: 'invalid username or PIN' }, { ok: false, status: 401, statusText: 'Unauthorized' }),
    );
    await expect(loginLocalProfile('Dana', 'wrong', fetchFn)).rejects.toThrow('invalid username or PIN');
  });

  it('falls back to the status line when the error body has no detail', async () => {
    const fetchFn = stub(jsonRes({}, { ok: false, status: 500, statusText: 'Internal Server Error' }));
    await expect(listLocalProfiles(fetchFn)).rejects.toThrow('500 Internal Server Error');
  });

  it('posts username and pin as JSON when creating a profile', async () => {
    const fetchFn = stub(
      jsonRes({ accessToken: 'tok-2', userId: 'local-def', username: 'Rae', hasPin: true }, { status: 201 }),
    );
    const session = await createLocalProfile('Rae', '4321', fetchFn);
    expect(session.provider).toBe('local');
    const [url, init] = (fetchFn as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/auth/local/profiles');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ username: 'Rae', pin: '4321' });
  });

  it('omits the pin key when no pin is given', async () => {
    const fetchFn = stub(
      jsonRes({ accessToken: 'tok-3', userId: 'local-ghi', username: 'Sam', hasPin: false }, { status: 201 }),
    );
    await createLocalProfile('Sam', undefined, fetchFn);
    const [, init] = (fetchFn as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ username: 'Sam' });
  });

  it('returns the parsed profile array', async () => {
    const profiles = [
      { userId: 'local-1', username: 'A', hasPin: false, createdAt: '2026-01-01T00:00:00+00:00' },
      { userId: 'local-2', username: 'B', hasPin: true, createdAt: '2026-01-02T00:00:00+00:00' },
    ];
    const fetchFn = stub(jsonRes(profiles));
    await expect(listLocalProfiles(fetchFn)).resolves.toEqual(profiles);
    expect(fetchFn).toHaveBeenCalledWith('/api/auth/local/profiles');
  });

  it('sends the bearer header on logout and resolves on 204', async () => {
    const fetchFn = stub(noContentRes());
    await expect(logoutLocalProfile('tok-1', fetchFn)).resolves.toBeUndefined();
    const [url, init] = (fetchFn as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/auth/local/logout');
    expect(init.method).toBe('POST');
    expect(init.headers.Authorization).toBe('Bearer tok-1');
  });
});
