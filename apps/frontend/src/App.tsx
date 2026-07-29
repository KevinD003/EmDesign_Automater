import { useEffect, useState } from 'react';
import { Toolbar } from './components/toolbar/Toolbar';
import { ColorObjectList } from './components/panels/ColorObjectList';
import { ThreadPalette } from './components/panels/ThreadPalette';
import { PropertiesPanel } from './components/panels/PropertiesPanel';
import { QualityPanel } from './components/panels/QualityPanel';
import { StitchPlayer } from './components/player/StitchPlayer';
import { StitchCanvas } from './components/canvas/StitchCanvas';
import { TrueView3D } from './components/trueview/TrueView3D';
import { Dashboard } from './components/dashboard/Dashboard';
import { AuthBar } from './components/auth/AuthBar';
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
  const [page, setPage] = useState<'studio' | 'dashboard'>('studio');
  const initAuth = useAuthStore((s) => s.init);

  // Restore any persisted cloud session on load (primes the API bearer token).
  useEffect(initAuth, [initAuth]);

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

  return (
    <div className="app-shell">
      <Toolbar />
      <nav className="page-nav">
        <div className="view-toggle">
          <button type="button" className={page === 'studio' ? 'active' : ''} onClick={() => setPage('studio')}>
            Studio
          </button>
          <button
            type="button"
            className={page === 'dashboard' ? 'active' : ''}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>
        </div>
        <AuthBar />
      </nav>
      {page === 'dashboard' ? (
        <Dashboard />
      ) : (
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
              <PropertiesPanel />
              <QualityPanel />
            </div>
          </div>
          <StitchPlayer />
        </>
      )}
    </div>
  );
}
