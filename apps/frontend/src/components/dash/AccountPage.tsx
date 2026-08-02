import { useState } from 'react';
import { api } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { useAccount } from './useAccount';

const TIERS: { key: 'free' | 'pro' | 'studio'; name: string; blurb: string; features: string[] }[] = [
  {
    key: 'free',
    name: 'Free',
    blurb: 'Everything you need to stitch today.',
    features: ['Auto-digitizing & lettering', 'All export formats', 'Hoops up to 130×180 mm', 'Quality checks'],
  },
  {
    key: 'pro',
    name: 'Pro',
    blurb: 'The production toolkit.',
    features: ['Everything in Free', 'Production package ZIP', 'Worksheet PDF', 'Path optimizer', 'Format converter'],
  },
  {
    key: 'studio',
    name: 'Studio',
    blurb: 'For digitizing businesses.',
    features: ['Everything in Pro', 'Photo & textured pipeline', 'Large-format hoops', 'Priority features'],
  },
];

/** Profile, recovery email, and the plan ladder. Plans are admin-assigned. */
export function AccountPage() {
  const session = useAuthStore((s) => s.session);
  const logout = useAuthStore((s) => s.logout);
  const { account, refresh } = useAccount();
  const [email, setEmail] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (!session) {
    return (
      <section className="dz-card">
        <h2 className="dz-card-title">You’re not signed in</h2>
        <p className="dz-muted">Sign in to manage your account, recovery email and plan.</p>
        <div className="dz-actions">
          <a className="dz-btn dz-btn-primary" href="#/login">Sign in</a>
          <a className="dz-btn" href="#/signup">Create account</a>
        </div>
      </section>
    );
  }

  const saveEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      await api.setAccountEmail(email.trim());
      setMsg('Recovery email saved — password resets go there now.');
      setEmail('');
      refresh();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  };

  return (
    <>
      <div className="dz-grid2">
        <section className="dz-card" aria-label="Profile">
          <h2 className="dz-card-title">Profile</h2>
          <dl className="dz-kv">
            <dt>Signed in as</dt>
            <dd>{account?.username ?? session.username ?? session.email}</dd>
            <dt>Account type</dt>
            <dd>{session.provider === 'supabase' ? 'Cloud (Supabase)' : 'Local profile'}</dd>
            {account ? (
              <>
                <dt>Role</dt>
                <dd>{account.role}</dd>
                <dt>Recovery email</dt>
                <dd>{account.email ?? <span className="dz-muted">not set — add one below</span>}</dd>
              </>
            ) : null}
          </dl>
          {account ? (
            <form className="dz-form-row" onSubmit={saveEmail}>
              <input
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label="Recovery email"
              />
              <button type="submit" className="dz-btn dz-btn-primary">Save email</button>
            </form>
          ) : null}
          {msg ? <p className="dz-ok" role="status">{msg}</p> : null}
          {err ? <p className="dz-err" role="alert">{err}</p> : null}
          <div className="dz-actions">
            <button
              type="button"
              className="dz-btn"
              onClick={() => {
                logout();
                window.location.hash = '#/login';
              }}
            >
              Sign out
            </button>
          </div>
        </section>

        <section className="dz-card" aria-label="Your plan">
          <h2 className="dz-card-title">Your plan</h2>
          <p>
            <span className={`dz-plan dz-plan-${account?.plan ?? 'free'}`}>
              {(account?.plan ?? 'free').toUpperCase()}
            </span>
          </p>
          <p className="dz-muted">
            Plans are assigned by your workspace admin — ask them to upgrade you from the Admin
            panel. Billing integration is deliberately not wired yet; the gate and the ladder are.
          </p>
        </section>
      </div>

      <section aria-label="Plan ladder" className="dz-tiers">
        {TIERS.map((t) => (
          <div key={t.key} className={`dz-card dz-tier ${account?.plan === t.key ? 'dz-tier-current' : ''}`}>
            <div className="dz-tier-head">
              <span className="dz-tier-name">{t.name}</span>
              {account?.plan === t.key ? <span className="dz-tier-badge">current</span> : null}
            </div>
            <p className="dz-muted">{t.blurb}</p>
            <ul className="dz-tier-list">
              {t.features.map((f) => (
                <li key={f}>✓ {f}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </>
  );
}
