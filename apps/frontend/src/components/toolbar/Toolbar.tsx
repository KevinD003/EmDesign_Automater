import { useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';

const TOOLS = ['Select', 'Run', 'Satin', 'Fill', 'Lettering', 'Appliqué', 'Manual', 'Shape'];
const ACCEPT = '.dst,.pes,.pec,.jef,.exp,.vp3,.vip,.xxx,.sew,.u01';

/** Top toolbar. Open (parse a file) and Export (download) are live; digitizing tools land in Phase 2. */
export function Toolbar() {
  const design = useDesignStore((s) => s.design);
  const setDesign = useDesignStore((s) => s.setDesign);
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onOpen = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      setDesign(await api.parseFile(file));
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Failed to open file');
    } finally {
      setBusy(false);
    }
  };

  const onExport = async () => {
    if (!design) return;
    setBusy(true);
    setErr(null);
    try {
      const blob = await api.exportDesign(design, 'dst');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(design.name || 'design').replace(/\.[^.]+$/, '')}.dst`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Export failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <header className="toolbar">
      <span className="brand">🧵 STITCHIQ</span>
      <nav className="tools">
        {TOOLS.map((tool) => (
          <button key={tool} type="button" className="tool-btn" disabled title="Coming in Phase 2">
            {tool}
          </button>
        ))}
      </nav>
      <div className="toolbar-actions">
        <input ref={fileRef} type="file" accept={ACCEPT} hidden onChange={onOpen} />
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
          {busy ? '…' : 'Open'}
        </button>
        <button type="button" onClick={onExport} disabled={!design || busy}>
          Export .DST
        </button>
        {err && (
          <span className="toolbar-err" title={err}>
            ⚠ {err}
          </span>
        )}
      </div>
    </header>
  );
}
