import { useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';

const TOOLS = ['Select', 'Run', 'Satin', 'Fill', 'Lettering', 'Appliqué', 'Manual', 'Shape'];
const ACCEPT = '.dst,.pes,.pec,.jef,.exp,.vp3,.vip,.xxx,.sew,.u01';

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Top toolbar. Open / Export / Worksheet are live; digitizing tools land in later phases. */
export function Toolbar() {
  const design = useDesignStore((s) => s.design);
  const setDesign = useDesignStore((s) => s.setDesign);
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  const onOpen = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    run(async () => setDesign(await api.parseFile(file)));
  };

  const stem = (design?.name || 'design').replace(/\.[^.]+$/, '');
  const onExport = () => design && run(async () => download(await api.exportDesign(design, 'dst'), `${stem}.dst`));
  const onWorksheet = () => design && run(async () => download(await api.worksheetPdf(design), `${stem}-worksheet.pdf`));

  return (
    <header className="toolbar">
      <span className="brand">🧵 STITCHIQ</span>
      <nav className="tools">
        {TOOLS.map((tool) => (
          <button key={tool} type="button" className="tool-btn" disabled title="Coming in a later phase">
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
        <button type="button" onClick={onWorksheet} disabled={!design || busy}>
          Worksheet
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
