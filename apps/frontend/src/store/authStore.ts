import { create } from 'zustand';
import { api, setAuthToken } from '../api/client';
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

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  init: () => {
    const store = kv();
    const session = store ? loadSession(store) : null;
    if (session) {
      setAuthToken(session.accessToken);
      set({ session });
    }
  },
  login: async (email, password) => {
    adopt(set, await api.login(email, password));
  },
  signup: async (email, password) => {
    adopt(set, await api.signup(email, password));
  },
  logout: () => {
    setAuthToken(null);
    const store = kv();
    if (store) clearSession(store);
    set({ session: null });
  },
}));
