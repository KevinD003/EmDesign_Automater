import { setAuthToken } from '../../api/client';
import { saveSession, type Session } from '../../lib/auth';
import { browserKV } from '../../lib/storage';
import { useAuthStore } from '../../store/authStore';
import { createLocalProfile, loginLocalProfile, type FetchLike } from './localAuth';

/**
 * Adoption glue for local (offline/LAN) sessions: makes a local login land in exactly the
 * same places as the Supabase login — API bearer header, localStorage, auth store — without
 * modifying the store or the API client. React-free on purpose so it stays unit-testable.
 */

/**
 * Mirror of the private `adopt` in store/authStore.ts. zustand's setState on the store hook
 * is public API, so writing session state from here needs no change to the store module.
 */
export function adoptLocalSession(session: Session): void {
  setAuthToken(session.accessToken);
  try {
    saveSession(session, browserKV());
  } catch {
    // No localStorage (node tests / SSR): the session stays in-memory for this page load.
  }
  useAuthStore.setState({ session });
}

/** Sign in to an existing local profile and adopt the resulting session. */
export async function loginAndAdopt(
  username: string,
  pin: string | undefined,
  fetchFn?: FetchLike,
): Promise<Session> {
  const session = await loginLocalProfile(username, pin, fetchFn);
  adoptLocalSession(session);
  return session;
}

/** Create a local profile and adopt the session it is signed in with. */
export async function createAndAdopt(
  username: string,
  pin: string | undefined,
  fetchFn?: FetchLike,
): Promise<Session> {
  const session = await createLocalProfile(username, pin, fetchFn);
  adoptLocalSession(session);
  return session;
}
