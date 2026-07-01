import { useDesignStore } from '../../store/designStore';

/**
 * Left sidebar — the color sequence of the loaded design (spec §3). Parsed stitch
 * files (.DST/.PES) carry color stops but no vector objects; object-level editing
 * arrives in Phase 2.
 */
export function ColorObjectList() {
  const design = useDesignStore((s) => s.design);
  const stops = design?.colorStops ?? [];

  return (
    <aside className="panel panel-left">
      <h2 className="panel-title">Color · Object List</h2>
      {stops.length > 0 ? (
        <ol className="object-list">
          {stops.map((cs) => (
            <li key={cs.stopNumber}>
              <span className="swatch" style={{ background: cs.hex }} />
              <span className="seq">{cs.stopNumber}</span>
              <span className="stop-name">{cs.threadName}</span>
              <span className="stop-count muted">{cs.stitchCount.toLocaleString()}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No design loaded. Open a .DST/.PES file to populate the color sequence.</p>
      )}
    </aside>
  );
}
