import { type ReactNode } from 'react';
import { navigate } from '../../lib/routes';
import { useTheme } from '../../lib/useTheme';
import { useAuthStore } from '../../store/authStore';
import { useAccount } from './useAccount';

/**
 * Dashboard shell (v2 Part 35) — sidebar nav + themed surface.
 *
 * THE THEME IS NO LONGER THE DASHBOARD'S ALONE (Atelier handoff). `data-theme`
 * used to be stamped on `.dz-root`, which themed this subtree and nothing else:
 * the Studio was hard-dark, and overlays portalled outside the dashboard — the
 * command palette, dialogs, toasts — never received the attribute at all.
 * `useTheme()` stamps <html> instead, so one attribute themes every surface.
 *
 * The Studio keeps dark as its DEFAULT (it is a canvas tool, and bright chrome
 * around artwork misleads the eye) but the toggle can now override it, which
 * was an explicit request in the handoff.
 */

export function DashShell({
  section,
  children,
}: {
  section: 'overview' | 'analytics' | 'account' | 'admin';
  children: ReactNode;
}) {
  const session = useAuthStore((s) => s.session);
  const { account } = useAccount();
  // Stamps <html> and persists the choice — see lib/useTheme.ts.
  const { theme, toggle } = useTheme();

  const nav = [
    { key: 'overview', label: 'Overview', hash: '#/dashboard', icon: '◫' },
    { key: 'analytics', label: 'Analytics', hash: '#/dashboard/analytics', icon: '▤' },
    { key: 'account', label: 'Account & plan', hash: '#/dashboard/account', icon: '◉' },
    ...(account?.role === 'admin'
      ? [{ key: 'admin', label: 'Admin', hash: '#/dashboard/admin', icon: '⚙' }]
      : []),
  ];

  const who = account?.username ?? session?.username ?? session?.email ?? 'Guest';

  return (
    <div className="dz-root">
      <aside className="dz-side" aria-label="Dashboard navigation">
        <button type="button" className="dz-brand" onClick={() => navigate('studio')} title="Back to Studio">
          <span className="dz-brand-mark" aria-hidden>🧵</span>
          <span className="dz-brand-name">STITCHIQ</span>
        </button>
        <nav className="dz-nav">
          {nav.map((n) => (
            <a key={n.key} href={n.hash} className={section === n.key ? 'dz-nav-item active' : 'dz-nav-item'}>
              <span className="dz-nav-icon" aria-hidden>{n.icon}</span>
              {n.label}
            </a>
          ))}
        </nav>
        <div className="dz-side-foot">
          <a href="#/studio" className="dz-nav-item">
            <span className="dz-nav-icon" aria-hidden>✎</span>
            Open Studio
          </a>
          <button
            type="button"
            className="dz-theme-btn"
            onClick={toggle}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? '☀ Light' : '☾ Dark'}
          </button>
        </div>
      </aside>
      <div className="dz-main">
        <header className="dz-top">
          <div className="dz-top-title">
            {section === 'overview' && 'Overview'}
            {section === 'analytics' && 'Design analytics'}
            {section === 'account' && 'Account & plan'}
            {section === 'admin' && 'Admin'}
          </div>
          <div className="dz-top-user">
            {account ? <span className={`dz-plan dz-plan-${account.plan}`}>{account.plan.toUpperCase()}</span> : null}
            <span className="dz-who">{who}</span>
            {session ? null : (
              <a className="dz-btn dz-btn-primary" href="#/login">
                Sign in
              </a>
            )}
          </div>
        </header>
        <main className="dz-content">{children}</main>
      </div>
    </div>
  );
}
