import { useState } from 'react';
import { api, type StitchOp } from '../../api/client';
import { useDesignStore } from '../../store/designStore';

/**
 * Stitch editor (v2 Part 36) — the "DST editor".
 *
 * Operates on the raw stitch stream, so it works on an imported machine file
 * that has no objects at all: select a stitch range, then delete it, retype it
 * (jump <-> stitch), strip its trims, split a colour block, or transform it.
 * The server restores the machine invariants after every edit and reports any
 * repair it made — an automatic fix is never invisible.
 */
export function StitchEditor() {
  const design = useDesignStore((s) => s.design);
  const setDesign = useDesignStore((s) => s.setDesign);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [scale, setScale] = useState(1);
  const [rotate, setRotate] = useState(0);
  const [notes, setNotes] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  // Shared global busy flag (CTO A15/N6) — see designStore.busyOp.
  const busy = useDesignStore((s) => s.busyOp) !== null;
  const beginOp = useDesignStore((s) => s.beginOp);
  const endOp = useDesignStore((s) => s.endOp);

  if (!design) {
    return (
      <section className="panel">
        <h2 className="panel-title">Stitch editor</h2>
        <p className="muted small">Open or digitize a design to edit its stitches.</p>
      </section>
    );
  }

  const total = design.stitches.length;
  const run = async (ops: StitchOp[]) => {
    if (!beginOp('stitch-edit')) return; // another mutation is mid-flight
    setErr(null);
    setNotes([]);
    try {
      // Stale-response guard (N6): drop the result if another design was
      // loaded while the server worked.
      const epoch = useDesignStore.getState().epoch;
      const res = await api.editStitches(design, ops);
      if (useDesignStore.getState().epoch !== epoch) return;
      setDesign(res.design);
      setNotes(res.notes);
      setEnd(Math.min(end, res.design.stitches.length - 1));
      setStart(Math.min(start, res.design.stitches.length - 1));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      endOp();
    }
  };

  const clampField = (v: string) => Math.max(0, Math.min(total - 1, Number(v) || 0));

  return (
    <section className="panel se-panel">
      <h2 className="panel-title">Stitch editor</h2>
      <p className="muted small">
        {total.toLocaleString()} stream entries · selection {Math.min(start, end)}–{Math.max(start, end)}
      </p>

      <div className="se-range">
        <label>
          From
          <input type="number" value={start} min={0} max={total - 1} onChange={(e) => setStart(clampField(e.target.value))} />
        </label>
        <label>
          To
          <input type="number" value={end} min={0} max={total - 1} onChange={(e) => setEnd(clampField(e.target.value))} />
        </label>
        <button type="button" onClick={() => { setStart(0); setEnd(total - 1); }}>
          All
        </button>
      </div>

      <div className="se-ops">
        <button type="button" disabled={busy} onClick={() => run([{ op: 'delete', start, end }])}>
          Delete range
        </button>
        <button type="button" disabled={busy} onClick={() => run([{ op: 'setCommand', start, end, command: 'STITCH' }])}>
          Jump → stitch
        </button>
        <button type="button" disabled={busy} onClick={() => run([{ op: 'setCommand', start, end, command: 'JUMP' }])}>
          Stitch → jump
        </button>
        <button type="button" disabled={busy} onClick={() => run([{ op: 'removeTrims', start, end }])}>
          Strip trims
        </button>
        <button type="button" disabled={busy} onClick={() => run([{ op: 'splitColor', index: start }])}>
          Split colour here
        </button>
      </div>

      <div className="se-transform">
        <label>
          Scale <em>{scale.toFixed(2)}×</em>
          <input type="range" min={0.25} max={3} step={0.05} value={scale} onChange={(e) => setScale(Number(e.target.value))} />
        </label>
        <label>
          Rotate <em>{rotate}°</em>
          <input type="range" min={-180} max={180} step={1} value={rotate} onChange={(e) => setRotate(Number(e.target.value))} />
        </label>
        <div className="se-ops">
          <button
            type="button"
            disabled={busy}
            onClick={() => run([{ op: 'transform', start, end, scale, rotateDeg: rotate }])}
          >
            Apply transform
          </button>
          <button type="button" disabled={busy} onClick={() => run([{ op: 'transform', start, end, mirrorX: true }])}>
            Mirror H
          </button>
          <button type="button" disabled={busy} onClick={() => run([{ op: 'transform', start, end, mirrorY: true }])}>
            Mirror V
          </button>
        </div>
      </div>

      {notes.length ? (
        <div className="se-notes" role="status">
          {notes.map((n) => (
            <div key={n}>✓ {n}</div>
          ))}
        </div>
      ) : null}
      {err ? <p className="se-err" role="alert">{err}</p> : null}
    </section>
  );
}
