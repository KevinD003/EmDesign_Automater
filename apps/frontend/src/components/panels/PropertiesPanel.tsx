import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';

/** Coerce arbitrary hex to the #rrggbb form that <input type="color"> requires. */
function normalizeHex(h: string): string {
  return /^#[0-9a-fA-F]{6}$/.test(h) ? h : '#000000';
}

/**
 * Properties panel (spec §3). For a parsed stitch file the editable unit is the color
 * stop: recolor, rename, and reorder (which re-sequences the stitch blocks). Object-level
 * properties (density, underlay, angle) arrive with the vector object model in Phase 3.
 */
export function PropertiesPanel() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const reorderStop = useDesignStore((s) => s.reorderStop);

  const stops = design?.colorStops ?? [];
  const idx = stops.findIndex((cs) => cs.stopNumber === selectedStop);
  const stop = idx >= 0 ? stops[idx] : null;

  const onColor = (e: ChangeEvent<HTMLInputElement>) => {
    if (stop) updateColorStop(stop.stopNumber, { hex: e.target.value });
  };
  const onName = (e: ChangeEvent<HTMLInputElement>) => {
    if (stop) updateColorStop(stop.stopNumber, { threadName: e.target.value });
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Properties</h2>
      {stop ? (
        <div className="prop-form">
          <label className="prop-row">
            <span>Color</span>
            <input type="color" value={normalizeHex(stop.hex)} onChange={onColor} />
          </label>
          <label className="prop-row">
            <span>Name</span>
            <input type="text" value={stop.threadName} onChange={onName} />
          </label>
          <div className="prop-row">
            <span>Order</span>
            <span className="move-btns">
              <button type="button" onClick={() => reorderStop(stop.stopNumber, 'up')} disabled={idx <= 0}>
                ▲ Up
              </button>
              <button
                type="button"
                onClick={() => reorderStop(stop.stopNumber, 'down')}
                disabled={idx < 0 || idx >= stops.length - 1}
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
          <p className="muted small">
            Density, underlay &amp; angle need a vector object model — coming with the digitizer in Phase 3.
          </p>
        </div>
      ) : (
        <p className="muted">Select a color stop (left panel) to recolor, rename, or reorder it.</p>
      )}
    </section>
  );
}
