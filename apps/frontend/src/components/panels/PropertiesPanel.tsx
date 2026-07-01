import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';

/** Coerce arbitrary hex to the #rrggbb form that <input type="color"> requires. */
function normalizeHex(h: string): string {
  return /^#[0-9a-fA-F]{6}$/.test(h) ? h : '#000000';
}

/**
 * Properties panel (spec §3). For a parsed stitch file the editable unit is the color
 * stop (recolor / rename). Object-level properties (density, underlay, angle) arrive with
 * the vector object model later in Phase 2.
 */
export function PropertiesPanel() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const stop = design?.colorStops.find((cs) => cs.stopNumber === selectedStop) ?? null;

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
            <span>Catalog</span>
            <span className="muted">{stop.catalogNumber || '—'}</span>
          </div>
          <div className="prop-row">
            <span>Stitches</span>
            <span className="muted">{stop.stitchCount.toLocaleString()}</span>
          </div>
          <p className="muted small">
            Density, underlay &amp; angle need a vector object model — coming later in Phase 2.
          </p>
        </div>
      ) : (
        <p className="muted">Select a color stop (left panel) to recolor or rename it.</p>
      )}
    </section>
  );
}
