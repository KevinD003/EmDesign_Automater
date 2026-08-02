/**
 * Hash routing (v2 Part 35). The app is a single Vite page, and email links
 * (password reset) need a URL that survives a static host with no server-side
 * rewrites — `/#/reset?token=…` does, `/reset` does not. So routes live in
 * the hash, parsed here and driven by one `hashchange` listener in App.
 */

export type Route =
  | { page: 'studio' }
  | { page: 'dashboard'; section: 'overview' | 'analytics' | 'account' | 'admin' }
  | { page: 'login' }
  | { page: 'signup' }
  | { page: 'forgot' }
  | { page: 'reset'; token: string };

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#\/?/, '');
  const [pathPart, queryPart = ''] = raw.split('?');
  const path = pathPart.replace(/\/+$/, '');
  if (path === 'login') return { page: 'login' };
  if (path === 'signup') return { page: 'signup' };
  if (path === 'forgot') return { page: 'forgot' };
  if (path === 'reset') {
    const token = new URLSearchParams(queryPart).get('token') ?? '';
    return { page: 'reset', token };
  }
  if (path === 'dashboard') return { page: 'dashboard', section: 'overview' };
  if (path.startsWith('dashboard/')) {
    const section = path.slice('dashboard/'.length);
    if (section === 'analytics' || section === 'account' || section === 'admin') {
      return { page: 'dashboard', section };
    }
    return { page: 'dashboard', section: 'overview' };
  }
  return { page: 'studio' };
}

export function navigate(to: string): void {
  window.location.hash = to.startsWith('#') ? to : `#/${to.replace(/^\/+/, '')}`;
}
