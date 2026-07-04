import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';
import type { ValidationReport } from '../../types/design';
import { browserKV, deleteDesign, listSaved, loadDesign, saveDesign, type SavedMeta } from '../../lib/storage';
import { isMasterFilename, parseMasterDesign } from '../../lib/masterFile';
import { DigitizeDialog } from '../dialogs/DigitizeDialog';
import type { DigitizeParams } from '../dialogs/DigitizeDialog';
import { LetteringDialog } from '../dialogs/LetteringDialog';
import type { LetteringParams } from '../dialogs/LetteringDialog';

const TOOLS = ['Select', 'Run', 'Satin', 'Fill', 'Lettering', 'Appliqué', 'Manual', 'Shape'];
const ACCEPT = '.dst,.pes,.pec,.jef,.exp,.vp3,.vip,.xxx,.sew,.u01,.json';
const ACCEPT_IMG = '.png,.jpg,.jpeg,.bmp,.webp';

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Top toolbar. Open / Export / Worksheet / Undo / Redo are live; digitizing tools land in later phases. */
export function Toolbar() {
  const design = useDesignStore((s) => s.design);
  const setDesign = useDesignStore((s) => s.setDesign);
  const setDesignId = useDesignStore((s) => s.setDesignId);
  const undo = useDesignStore((s) => s.undo);
  const redo = useDesignStore((s) => s.redo);
  const canUndo = useDesignStore((s) => s.past.length > 0);
  const canRedo = useDesignStore((s) => s.future.length > 0);
  const fileRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [showLettering, setShowLettering] = useState(false);
  const [exportFormat, setExportFormat] = useState('dst');
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [saved, setSaved] = useState<SavedMeta[]>([]);
  const [showSaved, setShowSaved] = useState(false);

  const refreshSaved = () => {
    try {
      setSaved(listSaved(browserKV()));
    } catch {
      /* localStorage unavailable */
    }
  };
  useEffect(refreshSaved, []);

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
    run(async () => {
      // .stiq.json master → local parse (keeps objects/contours); embroidery format → backend.
      if (isMasterFilename(file.name)) {
        setDesign(parseMasterDesign(await file.text()));
      } else {
        setDesign(await api.parseFile(file));
      }
    });
  };

  const onPickImage = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) setPendingImage(file); // opens the params dialog
  };

  const onDigitizeConfirm = (p: DigitizeParams) => {
    const file = pendingImage;
    setPendingImage(null);
    if (!file) return;
    run(async () => setDesign(await api.digitize(file, p.fabricType, p.hoopSize, p.maxColors)));
  };

  const onLetteringConfirm = (p: LetteringParams) => {
    setShowLettering(false);
    run(async () => setDesign(await api.lettering(p.text, p.heightMm, p.fabricType)));
  };

  const stem = (design?.name || 'design').replace(/\.[^.]+$/, '');
  const onCheck = () => design && run(async () => setReport(await api.validate(design)));
  const onExport = () =>
    design &&
    run(async () => {
      setReport(await api.validate(design)); // advisory — always show the report, never block
      download(await api.exportDesign(design, exportFormat), `${stem}.${exportFormat}`);
    });
  const onPackage = () =>
    design &&
    run(async () => download(await api.exportPackage(design, exportFormat), `${stem}-package.zip`));
  const onWorksheet = () => design && run(async () => download(await api.worksheetPdf(design), `${stem}-worksheet.pdf`));

  const onSave = () =>
    design &&
    run(async () => {
      const meta = saveDesign(design, browserKV());
      setDesignId(meta.id); // subsequent saves overwrite (no history churn)
      refreshSaved();
    });
  const onLoad = (id: string) => {
    const d = loadDesign(id, browserKV());
    if (d) {
      setDesign(d);
      setShowSaved(false);
    }
  };
  const onDelete = (id: string) => {
    deleteDesign(id, browserKV());
    refreshSaved();
  };

  return (
    <header className="toolbar">
      <span className="brand">🧵 STITCHIQ</span>
      <div className="undo-redo">
        <button type="button" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
          ↶
        </button>
        <button type="button" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Shift+Z)">
          ↷
        </button>
      </div>
      <nav className="tools">
        {TOOLS.map((tool) => (
          <button key={tool} type="button" className="tool-btn" disabled title="Coming in a later phase">
            {tool}
          </button>
        ))}
      </nav>
      <div className="toolbar-actions">
        <input ref={fileRef} type="file" accept={ACCEPT} hidden onChange={onOpen} />
        <input ref={imgRef} type="file" accept={ACCEPT_IMG} hidden onChange={onPickImage} />
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
          {busy ? '…' : 'Open'}
        </button>
        <button type="button" onClick={() => imgRef.current?.click()} disabled={busy} title="Auto-digitize an image (PNG/JPG)">
          Digitize
        </button>
        <button type="button" onClick={() => setShowLettering(true)} disabled={busy} title="Text → embroidery (§4.10)">
          Text
        </button>
        <select
          value={exportFormat}
          onChange={(e) => setExportFormat(e.target.value)}
          disabled={!design || busy}
          aria-label="Export format"
          className="format-select"
        >
          {['dst', 'pes', 'jef', 'exp', 'vp3'].map((f) => (
            <option key={f} value={f}>
              .{f.toUpperCase()}
            </option>
          ))}
        </select>
        <button type="button" onClick={onSave} disabled={!design || busy} title="Save to this browser">
          Save
        </button>
        <button
          type="button"
          onClick={() => {
            refreshSaved();
            setShowSaved((v) => !v);
          }}
          title="Saved designs"
        >
          Saved ({saved.length})
        </button>
        <button type="button" onClick={onCheck} disabled={!design || busy} title="Pre-export validation">
          Check
        </button>
        <button type="button" onClick={onExport} disabled={!design || busy}>
          Export
        </button>
        <button type="button" onClick={onPackage} disabled={!design || busy} title="Full production ZIP">
          Package
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
      {pendingImage && (
        <DigitizeDialog
          filename={pendingImage.name}
          onCancel={() => setPendingImage(null)}
          onConfirm={onDigitizeConfirm}
        />
      )}
      {showLettering && (
        <LetteringDialog onCancel={() => setShowLettering(false)} onConfirm={onLetteringConfirm} />
      )}
      {showSaved && (
        <div className="saved-panel">
          <button type="button" className="vr-close" onClick={() => setShowSaved(false)} aria-label="Close">
            ×
          </button>
          <strong>Saved designs</strong>
          {saved.length === 0 && <div className="muted small">Nothing saved in this browser yet.</div>}
          {saved.map((m) => (
            <div key={m.id} className="saved-row">
              <span className="saved-name" title={m.name}>{m.name}</span>
              <span className="muted saved-meta">{m.stitchCount.toLocaleString()} st</span>
              <button type="button" onClick={() => onLoad(m.id)}>Load</button>
              <button type="button" className="saved-del" onClick={() => onDelete(m.id)} aria-label="Delete">✕</button>
            </div>
          ))}
        </div>
      )}
      {report && (
        <div className={`validation-report${report.passed ? '' : ' has-issues'}`}>
          <button type="button" className="vr-close" onClick={() => setReport(null)} aria-label="Dismiss">
            ×
          </button>
          <strong>{report.passed ? '✓ Ready to stitch' : '⛔ Issues found'}</strong>
          {report.issues.map((m, i) => (
            <div key={`i${i}`} className="vr-issue">⛔ {m}</div>
          ))}
          {report.warnings.map((m, i) => (
            <div key={`w${i}`} className="vr-warn">⚠ {m}</div>
          ))}
          {report.passed && report.warnings.length === 0 && <div className="vr-ok">No problems detected.</div>}
        </div>
      )}
    </header>
  );
}
