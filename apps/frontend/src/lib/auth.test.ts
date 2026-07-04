import { describe, it, expect } from 'vitest';
import { saveSession, loadSession, clearSession, type Session } from './auth';
import type { KV } from './storage';

function memKV(): KV {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
  };
}

const session: Session = {
  accessToken: 'tok-abc',
  refreshToken: 'ref-xyz',
  userId: 'u-1',
  email: 'a@b.com',
};

describe('auth session persistence', () => {
  it('saves and loads a session', () => {
    const kv = memKV();
    saveSession(session, kv);
    expect(loadSession(kv)).toEqual(session);
  });

  it('returns null when nothing is stored', () => {
    expect(loadSession(memKV())).toBeNull();
  });

  it('returns null on corrupt JSON', () => {
    const kv = memKV();
    kv.setItem('stitchiq:session', '{not json');
    expect(loadSession(kv)).toBeNull();
  });

  it('rejects a session with no access token', () => {
    const kv = memKV();
    kv.setItem('stitchiq:session', JSON.stringify({ userId: 'u-1' }));
    expect(loadSession(kv)).toBeNull();
  });

  it('clears a session (logout)', () => {
    const kv = memKV();
    saveSession(session, kv);
    clearSession(kv);
    expect(loadSession(kv)).toBeNull();
  });
});
