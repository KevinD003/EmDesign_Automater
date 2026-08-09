/**
 * Mobile tab bar — the Studio's answer to a 390px viewport.
 *
 * The current layout is a three-column grid with fixed side rails; below 64rem
 * the rails are hidden by atelier.css and this bar carries navigation instead.
 * Render it as the last child of `.app-shell`, after <StitchPlayer />.
 */
import { navigate } from '../../lib/routes';
import type { Route } from '../../lib/routes';

const ITEMS = [
  { key: 'studio', label: 'Studio', icon: '✎', hash: 'studio' },
  { key: 'overview', label: 'Home', icon: '◫', hash: 'dashboard' },
  { key: 'analytics', label: 'Analytics', icon: '▤', hash: 'dashboard/analytics' },
  { key: 'account', label: 'Account', icon: '◉', hash: 'dashboard/account' },
] as const;

export function MobileTabBar({ route }: { route: Route }) {
  const current = route.page === 'dashboard' ? route.section : route.page;

  return (
    <nav className="sq-tabbar" aria-label="Sections">
      {ITEMS.map((it) => (
        <button
          key={it.key}
          type="button"
          aria-current={current === it.key ? 'page' : undefined}
          onClick={() => navigate(it.hash)}
        >
          <span aria-hidden style={{ fontSize: '1.1em', lineHeight: 1 }}>
            {it.icon}
          </span>
          <span style={{ fontSize: '0.72rem' }}>{it.label}</span>
        </button>
      ))}
    </nav>
  );
}
