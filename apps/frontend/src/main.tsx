import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { initObservability } from './lib/observability';
import { initialTheme } from './lib/theme';
import './index.css';
// The Atelier token layer, AFTER index.css so its --sq-* values win. It only
// defines custom properties and the new components' classes; index.css keeps
// all the layout. See docs/design/ATELIER-HANDOFF.md.
import './styles/atelier.css';

// Error reporting (CTO B1). A no-op unless VITE_SENTRY_DSN was set at build
// time, and deliberately not awaited: reporting must never delay first paint,
// and a Sentry outage must never stop the app from rendering.
void initObservability();

// Stamp the resolved theme on <html> BEFORE first paint.
//
// `useTheme()` owns changes, but it only runs while the dashboard is mounted.
// Land straight on the Studio — the common case — and <html> would carry no
// `data-theme` at all, so atelier.css would fall through to its `:root` light
// values and the canvas tool would come up bright. Resolving once here means
// every entry point starts on the right surface (dark unless the viewer has
// said otherwise), and the toggle takes over from there.
document.documentElement.setAttribute('data-theme', initialTheme());

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
