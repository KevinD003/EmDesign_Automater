import { useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';
import { api } from '../../api/client';
import { toastError } from '../feedback/toastStore';

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

  // Offer the object's fill type + Appliqué; when already appliqué, allow reverting to a fill.
  const typeOptions = obj ? (obj.stitchType === 'APPLIQUE' ? ['APPLIQUE', 'TATAMI', 'SATIN'] : [obj.stitchType, 'APPLIQUE']) : [];

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
                  {t === 'APPLIQUE' ? 'Appliqué' : t}
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
              disabled={obj.stitchType === 'SATIN'}
              title={obj.stitchType === 'SATIN' ? 'Satin columns follow the shape axis' : ''}
            />
          </label>
          <label className="prop-row">
            <span>Underlay</span>
            <select value={underlay} onChange={(e) => setUnderlay(e.target.value)}>
              <option value="NONE">None</option>
              {obj.stitchType === 'SATIN' ? (
                <option value="CENTER_WALK">Center walk</option>
              ) : (
                <option value="EDGE_WALK">Edge walk</option>
              )}
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
