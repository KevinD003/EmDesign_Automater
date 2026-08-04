import { useEffect, useState, type ReactNode } from 'react';
import { navigate } from '../../lib/routes';
import { initialTheme, saveTheme, type Theme } from '../../lib/theme';
import { useAuthStore } from '../../store/authStore';
import { useAccount } from './useAccount';

/**
 * Dashboard shell (v2 Part 35) — sidebar nav + themed surface.
 *
 * The dashboard is the one part of the app that follows the viewer's theme
 * (light/dark): tokens live on .dz-root, the toggle stamps data-theme on
 * <html>, and prefers-color-scheme supplies the default. The Studio stays
 * deliberately dark — it is a canvas tool, like every pro editor.
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
  const [theme, setTheme] = useState<Theme>(initialTheme);

  // The tokens live on .dz-root's own data-theme (below), so nothing needs to
  // be stamped on <html>; this only remembers the choice across visits.
  useEffect(() => saveTheme(theme), [theme]);

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
    <div className="dz-root" data-theme={theme}>
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
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
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
