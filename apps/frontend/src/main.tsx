import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { initObservability } from './lib/observability';
import './index.css';

// Error reporting (CTO B1). A no-op unless VITE_SENTRY_DSN was set at build
// time, and deliberately not awaited: reporting must never delay first paint,
// and a Sentry outage must never stop the app from rendering.
void initObservability();

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
