import type { Session } from '../../lib/auth';

/**
 * API helpers for the offline/LAN local-profile endpoints (/api/auth/local/*).
 * fetch is injectable so the logic is unit-tested without a network or a browser.
 * Paths are relative: the Vite dev server proxies /api to the FastAPI backend.
 */
export interface LocalProfile {
  userId: string;
  username: string;
  hasPin: boolean;
  createdAt?: string;
}

export type FetchLike = typeof fetch;

/** Base path of the local-auth router; matches the backend prefix /api + /auth/local. */
const BASE = '/api/auth/local';

/** Wire shape of a successful create/login response. */
interface LocalSessionWire {
  accessToken: string;
  userId: string;
  username: string;
  hasPin: boolean;
}

/** Raise the FastAPI {detail} message when present, else the HTTP status line. */
async function raiseForStatus(res: Response): Promise<never> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {
    detail = undefined;
  }
  throw new Error(detail || `${res.status} ${res.statusText}`);
}

/** POST JSON and map the local session response onto a Session. */
async function postSession(
  path: string,
  username: string,
  pin: string | undefined,
  fetchFn: FetchLike,
): Promise<Session> {
  const res = await fetchFn(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // An undefined pin is dropped by JSON.stringify; the backend defaults it to null.
    body: JSON.stringify({ username, pin }),
  });
  if (!res.ok) await raiseForStatus(res);
  const data = (await res.json()) as LocalSessionWire;
  return {
    accessToken: data.accessToken,
    userId: data.userId,
    username: data.username,
    provider: 'local',
  };
}

/** All local profiles on this machine, for the profile picker. */
export async function listLocalProfiles(fetchFn: FetchLike = globalThis.fetch): Promise<LocalProfile[]> {
  const res = await fetchFn(`${BASE}/profiles`);
  if (!res.ok) await raiseForStatus(res);
  return (await res.json()) as LocalProfile[];
}

/** Create a profile and return its signed-in session. */
export async function createLocalProfile(
  username: string,
  pin: string | undefined,
  fetchFn: FetchLike = globalThis.fetch,
): Promise<Session> {
  return postSession('/profiles', username, pin, fetchFn);
}

/** Sign in to an existing profile. */
export async function loginLocalProfile(
  username: string,
  pin: string | undefined,
  fetchFn: FetchLike = globalThis.fetch,
): Promise<Session> {
  return postSession('/login', username, pin, fetchFn);
}

/** Revoke a token server-side. The endpoint answers 204, so no body is parsed. */
export async function logoutLocalProfile(
  token: string,
  fetchFn: FetchLike = globalThis.fetch,
): Promise<void> {
  const res = await fetchFn(`${BASE}/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) await raiseForStatus(res);
}
