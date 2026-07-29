import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';
import type { Design, OptimizeReport, ValidationReport } from '../../types/design';
import { browserKV, deleteDesign, listSaved, loadDesign, saveDesign, type SavedMeta } from '../../lib/storage';
import { isMasterFilename, parseMasterDesign, serializeMasterDesign } from '../../lib/masterFile';
import { buildManualDesign, isImportedNotEditable, minPointsFor, type ManualTool } from '../../lib/manual';
import { DigitizeDialog } from '../dialogs/DigitizeDialog';
import type { DigitizeParams } from '../dialogs/DigitizeDialog';
import { LetteringDialog } from '../dialogs/LetteringDialog';
import type { LetteringParams } from '../dialogs/LetteringDialog';

// Manual-digitizing tools that are wired to draw mode; the rest are still stubs.
const DRAW_TOOLS: { label: string; tool: ManualTool }[] = [
  { label: 'Run', tool: 'run' },
  { label: 'Satin', tool: 'satin' },
  { label: 'Fill', tool: 'fill' },
];
const STUB_TOOLS = ['Lettering', 'Appliqué', 'Shape'];
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
  const replaceDesign = useDesignStore((s) => s.replaceDesign);
  const setDesignId = useDesignStore((s) => s.setDesignId);
  const undo = useDesignStore((s) => s.undo);
  const redo = useDesignStore((s) => s.redo);
  const canUndo = useDesignStore((s) => s.past.length > 0);
  const canRedo = useDesignStore((s) => s.future.length > 0);
  const activeTool = useDesignStore((s) => s.activeTool);
  const draft = useDesignStore((s) => s.draft);
  const setTool = useDesignStore((s) => s.setTool);
  const undoDraftPoint = useDesignStore((s) => s.undoDraftPoint);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const setQuality = useDesignStore((s) => s.setQuality);
  const fileRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [showLettering, setShowLettering] = useState(false);
  const [exportFormat, setExportFormat] = useState('dst');
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [optimizeReport, setOptimizeReport] = useState<OptimizeReport | null>(null);
  const [saved, setSaved] = useState<SavedMeta[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const session = useAuthStore((s) => s.session);
  const [cloud, setCloud] = useState<Design[]>([]);
  const [showCloud, setShowCloud] = useState(false);

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

  // Load a freshly generated design and auto-score it — the Quality panel (right side)
  // shows the result without an extra click.
  const loadAndScore = async (d: Design) => {
    setDesign(d);
    setQuality(await api.analyzeQuality(d));
  };

  const onDigitizeConfirm = (p: DigitizeParams) => {
    const file = pendingImage;
    setPendingImage(null);
    if (!file) return;
    run(async () => loadAndScore(await api.digitize(file, p.fabricType, p.hoopSize, p.maxColors)));
  };

  const onLetteringConfirm = (p: LetteringParams) => {
    setShowLettering(false);
    run(async () => loadAndScore(await api.lettering(p.text, p.heightMm, p.fabricType, p.letterSpacingMm)));
  };

  const stem = (design?.name || 'design').replace(/\.[^.]+$/, '');
  const onCheck = () => design && run(async () => setReport(await api.validate(design)));
  const onOptimize = () =>
    design &&
    run(async () => {
      const result = await api.optimizePath(design);
      setOptimizeReport(result.report);
      if (result.report.reordered) {
        replaceDesign(result.design); // keeps undo history
        // A visible quality report is now stale — re-score against the reordered design.
        if (useDesignStore.getState().quality) setQuality(await api.analyzeQuality(result.design));
      }
    });
  // Refreshes the Quality panel (right side) — the report itself renders there.
  const onQuality = () => design && run(async () => setQuality(await api.analyzeQuality(design)));

  // ── Manual digitizing: draw a Run/Satin/Fill, commit via server rebuild ──
  const startTool = (tool: ManualTool) => {
    if (isImportedNotEditable(design)) {
      setErr('Manual tools need a blank or digitized canvas — imported files aren’t editable object-by-object.');
      return;
    }
    setErr(null);
    setTool(activeTool === tool ? 'select' : tool);
  };
  const canFinish = activeTool !== 'select' && draft.length >= minPointsFor(activeTool as ManualTool);
  const onFinishDraw = () => {
    // Guard again at commit time: even if a draw was begun before an imported file was
    // loaded, never let Finish rebuild (and thus wipe) an imported stitch stream.
    if (isImportedNotEditable(design)) {
      setTool('select');
      setErr('Manual tools need a blank or digitized canvas — imported files aren’t editable object-by-object.');
      return;
    }
    run(async () => {
      const tool = activeTool as ManualTool;
      const built = buildManualDesign(design, tool, draft, selectedStop);
      const rebuilt = await api.rebuild(built);
      if (design) replaceDesign(rebuilt);
      else setDesign(rebuilt);
      setTool('select');
    });
  };
  const onCancelDraw = () => setTool('select');
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
  const onSaveMaster = () =>
    design &&
    run(async () =>
      download(new Blob([serializeMasterDesign(design)], { type: 'application/json' }), `${stem}.stiq.json`),
    );

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

  // ── Cloud (Supabase, per-user; requires sign-in) ──
  const onCloudSave = () =>
    design &&
    run(async () => {
      const saved = await api.createDesign(design);
      if (saved.id) setDesignId(saved.id);
    });
  const openCloudList = () =>
    run(async () => {
      setCloud(await api.listDesigns());
      setShowCloud(true);
    });
  const onCloudOpen = (id: string) =>
    run(async () => {
      setDesign(await api.getDesign(id));
      setShowCloud(false);
    });
  const onCloudDelete = (id: string) =>
    run(async () => {
      await api.deleteCloudDesign(id);
      setCloud(await api.listDesigns());
    });

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
        <button
          type="button"
          className={`tool-btn${activeTool === 'select' ? ' active' : ''}`}
          onClick={() => setTool('select')}
          title="Select / pan"
        >
          Select
        </button>
        {DRAW_TOOLS.map(({ label, tool }) => (
          <button
            key={tool}
            type="button"
            className={`tool-btn${activeTool === tool ? ' active' : ''}`}
            onClick={() => startTool(tool)}
            title={`Draw a ${label} object on the canvas`}
          >
            {label}
          </button>
        ))}
        {activeTool !== 'select' && (
          <>
            <button type="button" className="tool-btn primary" onClick={onFinishDraw} disabled={!canFinish || busy}>
              Finish ✓
            </button>
            <button
              type="button"
              className="tool-btn"
              onClick={undoDraftPoint}
              disabled={draft.length === 0}
              title="Undo last point"
            >
              ⌫
            </button>
            <button type="button" className="tool-btn" onClick={onCancelDraw} title="Cancel drawing">
              Cancel
            </button>
          </>
        )}
        {STUB_TOOLS.map((tool) => (
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
          title="Saved designs (this browser)"
        >
          Saved ({saved.length})
        </button>
        {session && (
          <>
            <button
              type="button"
              onClick={onCloudSave}
              disabled={!design || busy}
              title="Save to your cloud account (Supabase)"
            >
              ☁ Save
            </button>
            <button type="button" onClick={openCloudList} disabled={busy} title="Open a design from your cloud account">
              ☁ Open
            </button>
          </>
        )}
        <button type="button" onClick={onCheck} disabled={!design || busy} title="Pre-export validation">
          Check
        </button>
        <button type="button" onClick={onQuality} disabled={!design || busy} title="Quality score + findings (§Phase 8)">
          Quality
        </button>
        <button
          type="button"
          onClick={onOptimize}
          disabled={!design || busy}
          title="Optimize stitch path — cut travel/jumps (§Phase 8)"
        >
          Optimize
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
        <button type="button" onClick={onSaveMaster} disabled={!design || busy} title="Download editable master (.stiq.json)">
          Master
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
      {showCloud && (
        <div className="saved-panel cloud-panel">
          <button type="button" className="vr-close" onClick={() => setShowCloud(false)} aria-label="Close">
            ×
          </button>
          <strong>☁ Cloud designs</strong>
          {cloud.length === 0 && <div className="muted small">No cloud designs yet — hit ☁ Save.</div>}
          {cloud.map((d) => (
            <div key={d.id} className="saved-row">
              <span className="saved-name" title={d.name}>{d.name}</span>
              <span className="muted saved-meta">{d.stitchCount.toLocaleString()} st</span>
              <button type="button" onClick={() => d.id && onCloudOpen(d.id)}>Open</button>
              <button
                type="button"
                className="saved-del"
                onClick={() => d.id && onCloudDelete(d.id)}
                aria-label="Delete"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="report-stack">
      {optimizeReport && (
        <div className="validation-report">
          <button type="button" className="vr-close" onClick={() => setOptimizeReport(null)} aria-label="Dismiss">
            ×
          </button>
          <strong>{optimizeReport.reordered ? '✓ Path optimized' : 'Path already optimal'}</strong>
          {optimizeReport.reordered ? (
            <>
              <div className="vr-ok">
                Travel {optimizeReport.before.travelMm}mm → {optimizeReport.after.travelMm}mm
                {' '}(−{optimizeReport.travelSavedMm}mm)
              </div>
              {optimizeReport.trimsSaved > 0 && <div className="vr-ok">{optimizeReport.trimsSaved} fewer trims</div>}
              <div className="muted small">Applied — Undo (↶) reverts.</div>
            </>
          ) : (
            <div className="muted small">{optimizeReport.note}</div>
          )}
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
      </div>
    </header>
  );
}
