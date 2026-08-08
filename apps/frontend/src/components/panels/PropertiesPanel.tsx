import { useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';
import { toastError } from '../feedback/toastStore';
import { flowAngleDeg, flowDivideValid, flowSideAngles } from '../../lib/flow';
import { UNDERLAY_LABEL, underlayFamily, underlayOptions } from '../../lib/underlay';

/** Coerce arbitrary hex to the #rrggbb form that <input type="color"> requires. */
function normalizeHex(h: string): string {
  return /^#[0-9a-fA-F]{6}$/.test(h) ? h : '#000000';
}

/**
 * Properties panel (spec §3). Two modes:
 * - Color stop selected → recolor / rename / reorder (works for all designs).
 * - Object selected (digitized designs) → edit density & stitch angle, then Apply
 *   regenerates the stitches server-side via POST /api/designs/rebuild.
 */
export function PropertiesPanel() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const selectedObject = useDesignStore((s) => s.selectedObject);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const reorderStop = useDesignStore((s) => s.reorderStop);
  const replaceDesign = useDesignStore((s) => s.replaceDesign);
  const updateObject = useDesignStore((s) => s.updateObject);
  const setTool = useDesignStore((s) => s.setTool);
  const activeTool = useDesignStore((s) => s.activeTool);

  const stops = design?.colorStops ?? [];
  const stopIdx = stops.findIndex((cs) => cs.stopNumber === selectedStop);
  const stop = stopIdx >= 0 ? stops[stopIdx] : null;
  const obj = design?.objects.find((o) => o.sequenceOrder === selectedObject) ?? null;

  const [density, setDensity] = useState('');
  const [angle, setAngle] = useState('');
  const [underlay, setUnderlay] = useState('NONE');
  const [pull, setPull] = useState('');
  const [stype, setStype] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setDensity(obj ? String(obj.density) : '');
    setAngle(obj ? String(obj.stitchAngle) : '');
    setUnderlay(obj ? String(obj.underlayType) : 'NONE');
    setPull(obj ? String(obj.pullCompensation) : '');
    setStype(obj ? String(obj.stitchType) : '');
    setErr(null);
  }, [obj?.sequenceOrder, obj?.density, obj?.stitchAngle, obj?.underlayType, obj?.pullCompensation, obj?.stitchType]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fill family (interchangeable via rebuild): straight tatami, contour rows
  // that follow the outline, and the Part 26 curved fills. Satin stays satin;
  // Appliqué is always offered; an appliqué object can revert to any fill.
  const FILLS = ['TATAMI', 'CONTOUR_FILL', 'SPIRAL_FILL', 'RADIAL_FILL'];
  const typeOptions = obj
    ? obj.stitchType === 'APPLIQUE'
      ? ['APPLIQUE', ...FILLS, 'SATIN']
      : FILLS.includes(obj.stitchType)
        ? [...FILLS, 'APPLIQUE']
        : [obj.stitchType, 'APPLIQUE']
    : [];
  const TYPE_LABEL: Record<string, string> = {
    APPLIQUE: 'Appliqué',
    TATAMI: 'Tatami (straight rows)',
    CONTOUR_FILL: 'Contour (rows follow outline)',
    SPIRAL_FILL: 'Spiral (one continuous path)',
    RADIAL_FILL: 'Radial (sunburst)',
  };

  const onApply = async () => {
    if (!design || !obj) return;
    const d = Number(density);
    const a = Number(angle);
    if (!Number.isFinite(d) || d <= 0 || !Number.isFinite(a)) {
      setErr('Density must be > 0; angle must be a number.');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const p = Number(pull);
      if (!Number.isFinite(p) || p < 0 || p > 2) {
        setErr('Pull compensation must be 0–2 mm.');
        setBusy(false);
        return;
      }
      const patched = {
        ...design,
        objects: design.objects.map((o) =>
          o.sequenceOrder === obj.sequenceOrder
            ? {
                ...o,
                density: d,
                stitchAngle: a,
                underlayType: underlay as typeof o.underlayType,
                pullCompensation: p,
                stitchType: stype as typeof o.stitchType,
              }
            : o,
        ),
      };
      replaceDesign(await api.rebuild(patched)); // history recorded; undo restores pre-rebuild
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : 'Rebuild failed';
      setErr(msg); // inline error stays next to the form fields
      toastError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Properties</h2>
      {obj ? (
        <div className="prop-form">
          <div className="prop-row">
            <span>Object</span>
            <span className="muted">{obj.name}</span>
          </div>
          <label className="prop-row">
            <span>Stitch type</span>
            <select value={stype} onChange={(e) => setStype(e.target.value)}>
              {typeOptions.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t] ?? t}
                </option>
              ))}
            </select>
          </label>
          <label className="prop-row">
            <span>Density (lines/mm)</span>
            <input type="number" step="0.1" min="0.2" max="5" value={density} onChange={(e) => setDensity(e.target.value)} />
          </label>
          <label className="prop-row">
            <span>Angle (°)</span>
            {/* Satin angle is editable since CTO A5: rebuild honors the stored
                walk axis instead of recomputing minAreaRect, so the edit is no
                longer a silent no-op. */}
            <input
              type="number"
              step="5"
              value={angle}
              onChange={(e) => setAngle(e.target.value)}
              disabled={!!obj.flowLine || !!obj.flowLineB}
              title={
                obj.flowLine || obj.flowLineB
                  ? 'Overridden by the Stitch Flow line — remove the line to edit'
                  : obj.stitchType === 'SATIN'
                    ? 'Column axis — stitches run across it'
                    : ''
              }
            />
          </label>
          {/* Stitch Flow (v2 Part 62/63): a drawn direction line overrides the
              angle at rebuild; a divide line (Part 63) splits the object into
              two flow regions, each following its own line. Offered only where
              rebuild actually consumes it (tatami with a stored contour) — no
              dead controls. */}
          {obj.stitchType === 'TATAMI' && obj.contour && (
            <>
              <div className="prop-row">
                <span>Stitch Flow</span>
                <span className="muted">
                  {(() => {
                    if (flowDivideValid(obj.flowDivide)) {
                      const { pos, neg } = flowSideAngles(obj.flowDivide!, obj.flowLine, obj.flowLineB);
                      const fmt = (a: number | null) => (a === null ? 'auto' : `${a.toFixed(0)}°`);
                      return `divided: ${fmt(pos)} / ${fmt(neg)}`;
                    }
                    return obj.flowLine
                      ? `line at ${flowAngleDeg(obj.flowLine)?.toFixed(0)}°`
                      : `automatic (${Number(obj.stitchAngle).toFixed(0)}°)`;
                  })()}
                </span>
              </div>
              <div className="prop-row">
                <span />
                <span className="move-btns">
                  <button
                    type="button"
                    onClick={() => setTool(activeTool === 'flow' ? 'select' : 'flow')}
                  >
                    {activeTool === 'flow'
                      ? 'Cancel drawing'
                      : flowDivideValid(obj.flowDivide)
                        ? 'Draw side line'
                        : obj.flowLine
                          ? 'Redraw line'
                          : 'Draw line'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setTool(activeTool === 'divide' ? 'select' : 'divide')}
                  >
                    {activeTool === 'divide'
                      ? 'Cancel divide'
                      : obj.flowDivide
                        ? 'Redraw divide'
                        : 'Divide'}
                  </button>
                </span>
              </div>
              {(obj.flowLine || obj.flowLineB || obj.flowDivide) && (
                <div className="prop-row">
                  <span />
                  <span className="move-btns">
                    {(obj.flowLine || obj.flowLineB) && (
                      <button
                        type="button"
                        onClick={() => updateObject(obj.sequenceOrder, { flowLine: null, flowLineB: null })}
                      >
                        Remove {obj.flowLine && obj.flowLineB ? 'lines' : 'line'}
                      </button>
                    )}
                    {obj.flowDivide && (
                      <button
                        type="button"
                        onClick={() =>
                          // a side line is meaningless without its divide, so
                          // removing the divide also clears the second line
                          updateObject(obj.sequenceOrder, { flowDivide: null, flowLineB: null })
                        }
                      >
                        Remove divide
                      </button>
                    )}
                  </span>
                </div>
              )}
              {activeTool === 'flow' && (
                <p className="muted small">Click the start and end of the direction line on the canvas.</p>
              )}
              {activeTool === 'divide' && (
                <p className="muted small">Click the start and end of the divide line on the canvas.</p>
              )}
              {activeTool !== 'flow' && activeTool !== 'divide' && flowDivideValid(obj.flowDivide) && (
                <p className="muted small">
                  Each side follows its own line after Apply — draw one line per side; drag endpoints on the canvas to adjust.
                </p>
              )}
              {activeTool !== 'flow' && activeTool !== 'divide' && !flowDivideValid(obj.flowDivide) && obj.flowLine && (
                <p className="muted small">Rows follow the line after Apply. Drag its endpoints on the canvas to adjust.</p>
              )}
            </>
          )}
          <label className="prop-row">
            <span>Underlay</span>
            {/* Per-family choices, every one dispatched to a real generator on
                rebuild (CTO A5/C5 — the old shared list collapsed most values
                to one default per family, so the selection was fake). A legacy
                stored value outside the family list is appended so the select
                never renders blank. Runs/manual/appliqué take no underlay, so
                the control is disabled for them. */}
            <select
              value={underlay}
              onChange={(e) => setUnderlay(e.target.value)}
              disabled={underlayFamily(obj.stitchType).length === 0}
              title={
                underlayFamily(obj.stitchType).length === 0
                  ? 'This stitch type takes no underlay'
                  : ''
              }
            >
              {underlayOptions(obj.stitchType, underlay).map((u) => (
                <option key={u} value={u}>
                  {UNDERLAY_LABEL[u] ?? u}
                </option>
              ))}
            </select>
          </label>
          <label className="prop-row">
            <span>Pull comp (mm)</span>
            <input type="number" step="0.05" min="0" max="2" value={pull} onChange={(e) => setPull(e.target.value)} />
          </label>
          <div className="dialog-actions">
            <button type="button" className="primary" onClick={onApply} disabled={busy || !obj.contour}>
              {busy ? 'Rebuilding…' : 'Apply (rebuild)'}
            </button>
          </div>
          {!obj.contour && <p className="muted small">No contour stored — object is not regenerable.</p>}
          {err && <p className="toolbar-err">⚠ {err}</p>}
          <div className="prop-row">
            <span>Stitches</span>
            <span className="muted">{obj.stitchCount.toLocaleString()}</span>
          </div>
        </div>
      ) : stop ? (
        <div className="prop-form">
          <label className="prop-row">
            <span>Color</span>
            <input
              type="color"
              value={normalizeHex(stop.hex)}
              onChange={(e: ChangeEvent<HTMLInputElement>) => updateColorStop(stop.stopNumber, { hex: e.target.value })}
            />
          </label>
          <label className="prop-row">
            <span>Name</span>
            <input
              type="text"
              value={stop.threadName}
              onChange={(e: ChangeEvent<HTMLInputElement>) => updateColorStop(stop.stopNumber, { threadName: e.target.value })}
            />
          </label>
          <div className="prop-row">
            <span>Order</span>
            <span className="move-btns">
              <button type="button" onClick={() => reorderStop(stop.stopNumber, 'up')} disabled={stopIdx <= 0}>
                ▲ Up
              </button>
              <button
                type="button"
                onClick={() => reorderStop(stop.stopNumber, 'down')}
                disabled={stopIdx < 0 || stopIdx >= stops.length - 1}
              >
                ▼ Down
              </button>
            </span>
          </div>
          <div className="prop-row">
            <span>Catalog</span>
            <span className="muted">{stop.catalogNumber || '—'}</span>
          </div>
          <div className="prop-row">
            <span>Stitches</span>
            <span className="muted">{stop.stitchCount.toLocaleString()}</span>
          </div>
        </div>
      ) : (
        <p className="muted">Select a color stop or an object (left panel) to edit it.</p>
      )}
    </section>
  );
}
