import { create } from 'zustand';
import { api, setAuthToken, setUnauthorizedHandler } from '../api/client';
import { browserKV } from '../lib/storage';
import { clearSession, loadSession, saveSession, type Session } from '../lib/auth';

interface AuthState {
  session: Session | null;
  /** Load any persisted session on app start and prime the API token. */
  init: () => void;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

function kv() {
  try {
    return browserKV();
  } catch {
    return null;
  }
}

function adopt(set: (s: Partial<AuthState>) => void, session: Session) {
  setAuthToken(session.accessToken);
  const store = kv();
  if (store) saveSession(session, store);
  set({ session });
}

function dropSession(set: (s: Partial<AuthState>) => void) {
  setAuthToken(null);
  const store = kv();
  if (store) clearSession(store);
  set({ session: null });
}

export const useAuthStore = create<AuthState>((set, get) => ({
  session: null,
  init: () => {
    const store = kv();
    const session = store ? loadSession(store) : null;
    if (session) {
      setAuthToken(session.accessToken);
      set({ session });
    }
    // 401 recovery (CTO A15/N5): try the refresh grant once; on any failure
    // clear the session so the UI shows signed-out instead of silently
    // failing saves while claiming "signed in". Local-profile sessions have
    // no refresh grant — they just clear.
    setUnauthorizedHandler(async () => {
      const s = get().session;
      if (!s?.refreshToken || s.provider === 'local') {
        dropSession(set);
        return null;
      }
      try {
        const renewed = await api.refresh(s.refreshToken);
        adopt(set, { ...s, ...renewed });
        return renewed.accessToken;
      } catch {
        dropSession(set);
        return null;
      }
    });
  },
  login: async (email, password) => {
    adopt(set, await api.login(email, password));
  },
  signup: async (email, password) => {
    adopt(set, await api.signup(email, password));
  },
  logout: () => {
    dropSession(set);
  },
}));
