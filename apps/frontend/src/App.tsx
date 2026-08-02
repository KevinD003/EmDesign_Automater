import { useEffect, useState } from 'react';
import { Toolbar } from './components/toolbar/Toolbar';
import { ColorObjectList } from './components/panels/ColorObjectList';
import { ThreadPalette } from './components/panels/ThreadPalette';
import { PropertiesPanel } from './components/panels/PropertiesPanel';
import { QualityPanel } from './components/panels/QualityPanel';
import { ThreadEditor } from './components/panels/ThreadEditor';
import { StitchEditor } from './components/panels/StitchEditor';
import { StitchPlayer } from './components/player/StitchPlayer';
import { StitchCanvas } from './components/canvas/StitchCanvas';
import { TrueView3D } from './components/trueview/TrueView3D';
import { Toasts } from './components/feedback/Toasts';
import { AuthBar } from './components/auth/AuthBar';
import { DashShell } from './components/dash/DashShell';
import { OverviewPage } from './components/dash/OverviewPage';
import { AnalyticsPage } from './components/dash/AnalyticsPage';
import { AccountPage } from './components/dash/AccountPage';
import { AdminPage } from './components/dash/AdminPage';
import { ForgotPage, LoginPage, ResetPage, SignupPage } from './components/dash/AuthPages';
import { parseRoute, type Route } from './lib/routes';
import { useDesignStore } from './store/designStore';
import { useAuthStore } from './store/authStore';

/**
 * App shell — the Wilcom-style studio layout (spec §3):
 * Toolbar (top) · ColorObjectList (left) · StitchCanvas (center) ·
 * ThreadPalette + PropertiesPanel + QualityPanel (right) · StitchPlayer (bottom).
 */
export default function App() {
  const design = useDesignStore((s) => s.design);
  const playHead = useDesignStore((s) => s.playHead);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const selectStop = useDesignStore((s) => s.selectStop);
  const [view, setView] = useState<'2d' | '3d'>('2d');
  // Hash routing (v2 Part 35): pages live in the URL so email links (PIN
  // reset) and dashboard sections survive a refresh on a static host.
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  const initAuth = useAuthStore((s) => s.init);

  // Restore any persisted cloud session on load (primes the API bearer token).
  useEffect(initAuth, [initAuth]);

  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Global undo/redo shortcuts: Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && useDesignStore.getState().activeTool !== 'select') {
        useDesignStore.getState().setTool('select'); // cancel manual drawing
        return;
      }
      if (!(e.metaKey || e.ctrlKey)) return;
      const k = e.key.toLowerCase();
      if (k === 'z') {
        e.preventDefault();
        if (e.shiftKey) useDesignStore.getState().redo();
        else useDesignStore.getState().undo();
      } else if (k === 'y') {
        e.preventDefault();
        useDesignStore.getState().redo();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Full-page routes render without the studio chrome.
  if (route.page === 'login') return <LoginPage />;
  if (route.page === 'signup') return <SignupPage />;
  if (route.page === 'forgot') return <ForgotPage />;
  if (route.page === 'reset') return <ResetPage token={route.token} />;
  if (route.page === 'dashboard') {
    return (
      <>
        <DashShell section={route.section}>
          {route.section === 'overview' && <OverviewPage />}
          {route.section === 'analytics' && <AnalyticsPage />}
          {route.section === 'account' && <AccountPage />}
          {route.section === 'admin' && <AdminPage />}
        </DashShell>
        <Toasts />
      </>
    );
  }

  return (
    <div className="app-shell">
      <Toolbar />
      <nav className="page-nav">
        <div className="view-toggle">
          <a className="active" href="#/studio">
            Studio
          </a>
          <a href="#/dashboard">Dashboard</a>
        </div>
        <AuthBar />
      </nav>
      {(
        <>
          <div className="app-body">
            <ColorObjectList />
            <main className="canvas-area">
              <div className="view-toggle">
                <button type="button" className={view === '2d' ? 'active' : ''} onClick={() => setView('2d')}>
                  2D
                </button>
                <button type="button" className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')}>
                  TrueView 3D
                </button>
              </div>
              {design?.warnings?.length ? (
                // What the digitizer left out or altered (v2 Part 25). Silent
                // loss was a measured defect: a 40x40mm hoop deleted 81% of the
                // badge fixture's objects with nothing shown to the user.
                <div className="design-warnings" role="status">
                  {design.warnings.map((w) => (
                    <div key={w}>⚠ {w}</div>
                  ))}
                </div>
              ) : null}
              {view === '2d' ? (
                <StitchCanvas
                  stitches={design?.stitches ?? []}
                  colorStops={design?.colorStops ?? []}
                  limit={playHead}
                  selectedStop={selectedStop}
                  onSelectStop={selectStop}
                />
              ) : (
                <TrueView3D stitches={design?.stitches ?? []} colorStops={design?.colorStops ?? []} />
              )}
            </main>
            <div className="panel-right">
              <ThreadPalette />
              <ThreadEditor />
              <PropertiesPanel />
              <StitchEditor />
              <QualityPanel />
            </div>
          </div>
          <StitchPlayer />
        </>
      )}
      <Toasts />
    </div>
  );
}
