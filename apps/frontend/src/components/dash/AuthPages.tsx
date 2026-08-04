import { useState, type FormEvent, type ReactNode } from 'react';
import { api } from '../../api/client';
import { navigate } from '../../lib/routes';
import { initialTheme } from '../../lib/theme';
import { createAndAdopt, loginAndAdopt } from '../auth/localSession';

/**
 * Full-page auth screens (v2 Part 35): sign in, create account, forgot PIN,
 * and the reset landing the email links to. These drive LOCAL profiles — the
 * shipped topology. Cloud (Supabase) sign-in stays available from the Studio
 * nav when the server is configured for it.
 */

function AuthFrame({ title, children }: { title: string; children: ReactNode }) {
  // Same token surface as the dashboard, so it needs the same data-theme. Without
  // it these pages always resolved to .dz-root's dark default, which is how a
  // light-mode user got a black sign-in page off a white dashboard (Part 44).
  const theme = initialTheme();
  return (
    <div className="dz-root dz-auth-root" data-theme={theme}>
      <div className="dz-auth-card dz-card">
        <a className="dz-brand dz-auth-brand" href="#/studio">
          <span aria-hidden>🧵</span> STITCHIQ
        </a>
        <h1 className="dz-auth-title">{title}</h1>
        {children}
      </div>
    </div>
  );
}

function useSubmit(fn: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await fn();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  };
  return { busy, err, onSubmit };
}

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [pin, setPin] = useState('');
  const { busy, err, onSubmit } = useSubmit(async () => {
    await loginAndAdopt(username.trim(), pin || undefined);
    navigate('dashboard');
  });

  return (
    <AuthFrame title="Sign in">
      <form className="dz-auth-form" onSubmit={onSubmit}>
        <label>
          Username or email
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus autoComplete="username" />
        </label>
        <label>
          PIN
          <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="current-password" placeholder="leave empty if none" />
        </label>
        {err ? <p className="dz-err" role="alert">{err}</p> : null}
        <button className="dz-btn dz-btn-primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="dz-auth-links">
        <a href="#/forgot">Forgot PIN?</a> · <a href="#/signup">Create account</a>
      </p>
    </AuthFrame>
  );
}

export function SignupPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [pin, setPin] = useState('');
  const { busy, err, onSubmit } = useSubmit(async () => {
    const session = await createAndAdopt(username.trim(), pin || undefined);
    if (email.trim()) {
      // Best-effort: the account works without it; recovery needs it.
      try {
        await api.setAccountEmail(email.trim());
      } catch {
        /* surfaced later on the Account page */
      }
    }
    void session;
    navigate('dashboard');
  });

  return (
    <AuthFrame title="Create your account">
      <form className="dz-auth-form" onSubmit={onSubmit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus autoComplete="username" />
        </label>
        <label>
          Email <span className="dz-muted dz-small">(for PIN recovery)</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" />
        </label>
        <label>
          PIN <span className="dz-muted dz-small">(4+ characters)</span>
          <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="new-password" />
        </label>
        {err ? <p className="dz-err" role="alert">{err}</p> : null}
        <button className="dz-btn dz-btn-primary" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p className="dz-auth-links">
        <a href="#/login">I already have an account</a>
      </p>
    </AuthFrame>
  );
}

export function ForgotPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const { busy, err, onSubmit } = useSubmit(async () => {
    await api.forgotPassword(email.trim());
    setSent(true);
  });

  return (
    <AuthFrame title="Reset your PIN">
      {sent ? (
        <>
          <p>
            If <strong>{email}</strong> has an account, a reset link is on its way. The link works
            once and expires in 30 minutes.
          </p>
          <p className="dz-auth-links">
            <a href="#/login">Back to sign in</a>
          </p>
        </>
      ) : (
        <>
          <p className="dz-muted">Enter your recovery email — we’ll send a one-time reset link.</p>
          <form className="dz-auth-form" onSubmit={onSubmit}>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
            </label>
            {err ? <p className="dz-err" role="alert">{err}</p> : null}
            <button className="dz-btn dz-btn-primary" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
          <p className="dz-auth-links">
            <a href="#/login">Back to sign in</a>
          </p>
        </>
      )}
    </AuthFrame>
  );
}

export function ResetPage({ token }: { token: string }) {
  const [pin, setPin] = useState('');
  const [pin2, setPin2] = useState('');
  const [done, setDone] = useState<string | null>(null);
  const { busy, err, onSubmit } = useSubmit(async () => {
    if (pin !== pin2) throw new Error('The two PINs don’t match.');
    const res = await api.resetPassword(token, pin);
    setDone(res.username);
  });

  return (
    <AuthFrame title="Choose a new PIN">
      {done ? (
        <>
          <p>
            Done — <strong>{done}</strong>, your PIN is updated and every old session is signed
            out.
          </p>
          <p className="dz-auth-links">
            <a href="#/login">Sign in with the new PIN</a>
          </p>
        </>
      ) : (
        <form className="dz-auth-form" onSubmit={onSubmit}>
          <label>
            New PIN <span className="dz-muted dz-small">(4+ characters)</span>
            <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} required autoFocus autoComplete="new-password" />
          </label>
          <label>
            Repeat new PIN
            <input type="password" value={pin2} onChange={(e) => setPin2(e.target.value)} required autoComplete="new-password" />
          </label>
          {err ? <p className="dz-err" role="alert">{err}</p> : null}
          <button className="dz-btn dz-btn-primary" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Set new PIN'}
          </button>
        </form>
      )}
    </AuthFrame>
  );
}
