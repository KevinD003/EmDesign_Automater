import type { KV } from './storage';

/**
 * Auth session persistence. The backend (/api/auth) proxies Supabase GoTrue and returns
 * a session; we keep the access token in localStorage so a refresh stays logged in.
 * The KV backend is injectable so the logic is unit-tested without a browser.
 */
export interface Session {
  accessToken: string;
  refreshToken?: string;
  userId: string;
  email?: string;
  /** Absent on sessions persisted before local profiles existed; treat as 'supabase'. */
  provider?: 'supabase' | 'local';
  /** Display name for local profiles; Supabase sessions use email instead. */
  username?: string;
  /** Account role/plan (v2 Part 35) — refreshed from /auth/local/me. */
  role?: 'user' | 'admin';
  plan?: 'free' | 'pro' | 'studio';
}

const SESSION_KEY = 'stitchiq:session';

/** Persist a session. */
export function saveSession(session: Session, kv: KV): void {
  kv.setItem(SESSION_KEY, JSON.stringify(session));
}

/** Load the persisted session, or null if absent/corrupt/missing a token. */
export function loadSession(kv: KV): Session | null {
  try {
    const raw = kv.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return s && typeof s.accessToken === 'string' && s.accessToken ? s : null;
  } catch {
    return null;
  }
}

/** Forget the session (logout). */
export function clearSession(kv: KV): void {
  kv.removeItem(SESSION_KEY);
}
