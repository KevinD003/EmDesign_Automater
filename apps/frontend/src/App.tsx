import { Toolbar } from './components/toolbar/Toolbar';
import { ColorObjectList } from './components/panels/ColorObjectList';
import { ThreadPalette } from './components/panels/ThreadPalette';
import { PropertiesPanel } from './components/panels/PropertiesPanel';
import { StitchPlayer } from './components/player/StitchPlayer';
import { StitchCanvas } from './components/canvas/StitchCanvas';
import { useDesignStore } from './store/designStore';

/**
 * App shell — the Wilcom-style studio layout (spec §3):
 * Toolbar (top) · ColorObjectList (left) · StitchCanvas (center) ·
 * ThreadPalette + PropertiesPanel (right) · StitchPlayer (bottom).
 * Panels render placeholder content; features are stubs.
 */
export default function App() {
  const design = useDesignStore((s) => s.design);

  return (
    <div className="app-shell">
      <Toolbar />
      <div className="app-body">
        <ColorObjectList />
        <main className="canvas-area">
          <StitchCanvas stitches={design?.stitches ?? []} />
        </main>
        <div className="panel-right">
          <ThreadPalette />
          <PropertiesPanel />
        </div>
      </div>
      <StitchPlayer />
    </div>
  );
}
