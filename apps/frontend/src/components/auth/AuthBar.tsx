import { useState } from 'react';
import { useAuthStore } from '../../store/authStore';

/**
 * Compact auth control in the top bar. Logged out → email/password + Login / Sign up.
 * Logged in → the account email + Log out. Enables the cloud Save/Open buttons.
 */
export function AuthBar() {
  const session = useAuthStore((s) => s.session);
  const login = useAuthStore((s) => s.login);
  const signup = useAuthStore((s) => s.signup);
  const logout = useAuthStore((s) => s.logout);

  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (session) {
    return (
      <div className="auth-bar">
        <span className="auth-user" title={session.email ?? session.userId}>
          ☁ {session.email ?? 'signed in'}
        </span>
        <button type="button" className="auth-link" onClick={logout}>
          Log out
        </button>
      </div>
    );
  }

  const submit = (mode: 'login' | 'signup') => async () => {
    setBusy(true);
    setErr(null);
    try {
      if (mode === 'login') await login(email, password);
      else await signup(email, password);
      setOpen(false);
      setEmail('');
      setPassword('');
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Authentication failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-bar">
      <button type="button" className="auth-link" onClick={() => setOpen((v) => !v)}>
        ☁ Sign in
      </button>
      {open && (
        <div className="auth-popover">
          <strong>Cloud account</strong>
          <input
            type="email"
            placeholder="email"
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="password (min 6)"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
          />
          {err && <div className="auth-err">{err}</div>}
          <div className="auth-actions">
            <button type="button" onClick={submit('login')} disabled={busy || !email || !password}>
              {busy ? '…' : 'Log in'}
            </button>
            <button
              type="button"
              className="auth-secondary"
              onClick={submit('signup')}
              disabled={busy || !email || !password}
            >
              Sign up
            </button>
          </div>
          <div className="auth-hint muted small">Sign up creates a cloud account to save designs across devices.</div>
        </div>
      )}
    </div>
  );
}
