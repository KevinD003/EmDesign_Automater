import { useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';
import { toastError } from '../feedback/toastStore';
import { flowAngleDeg } from '../../lib/flow';

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
            <input
              type="number"
              step="5"
              value={angle}
              onChange={(e) => setAngle(e.target.value)}
              disabled={obj.stitchType === 'SATIN' || !!obj.flowLine}
              title={
                obj.stitchType === 'SATIN'
                  ? 'Satin columns follow the shape axis'
                  : obj.flowLine
                    ? 'Overridden by the Stitch Flow line — remove the line to edit'
                    : ''
              }
            />
          </label>
          {/* Stitch Flow (v2 Part 62): a drawn direction line that overrides the
              angle at rebuild. Offered only where rebuild actually consumes it
              (tatami with a stored contour) — no dead controls. */}
          {obj.stitchType === 'TATAMI' && obj.contour && (
            <>
              <div className="prop-row">
                <span>Stitch Flow</span>
                <span className="muted">
                  {obj.flowLine
                    ? `line at ${flowAngleDeg(obj.flowLine)?.toFixed(0)}°`
                    : `automatic (${Number(obj.stitchAngle).toFixed(0)}°)`}
                </span>
              </div>
              <div className="prop-row">
                <span />
                <span className="move-btns">
                  <button
                    type="button"
                    onClick={() => setTool(activeTool === 'flow' ? 'select' : 'flow')}
                  >
                    {activeTool === 'flow' ? 'Cancel drawing' : obj.flowLine ? 'Redraw line' : 'Draw line'}
                  </button>
                  {obj.flowLine && (
                    <button type="button" onClick={() => updateObject(obj.sequenceOrder, { flowLine: null })}>
                      Remove line
                    </button>
                  )}
                </span>
              </div>
              {activeTool === 'flow' && (
                <p className="muted small">Click the start and end of the direction line on the canvas.</p>
              )}
              {obj.flowLine && (
                <p className="muted small">Rows follow the line after Apply. Drag its endpoints on the canvas to adjust.</p>
              )}
            </>
          )}
          <label className="prop-row">
            <span>Underlay</span>
            {/* Every type the generator can PRODUCE is listed for both families
                (v2 Part 24 added DOUBLE_ZIGZAG and PARALLEL; this dropdown was
                not updated with it, so an object could carry an underlay the
                panel could neither display nor round-trip — the select showed
                blank). Rebuild maps any non-NONE value to the width-appropriate
                underlay for the object's current stitch type. */}
            <select value={underlay} onChange={(e) => setUnderlay(e.target.value)}>
              <option value="NONE">None</option>
              <option value="CENTER_WALK">Center walk</option>
              <option value="EDGE_WALK">Edge walk</option>
              <option value="DOUBLE_ZIGZAG">Double zigzag</option>
              <option value="PARALLEL">Edge walk + tatami</option>
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
