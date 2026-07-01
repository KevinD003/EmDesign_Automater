import { useDesignStore } from '../../store/designStore';

/**
 * Left sidebar — the color sequence of the loaded design (spec §3). Click a stop to
 * select it (highlights its stitches on the canvas and opens it in the Properties panel).
 */
export function ColorObjectList() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const selectStop = useDesignStore((s) => s.selectStop);
  const stops = design?.colorStops ?? [];

  return (
    <aside className="panel panel-left">
      <h2 className="panel-title">Color · Object List</h2>
      {stops.length > 0 ? (
        <ol className="object-list">
          {stops.map((cs) => (
            <li key={cs.stopNumber}>
              <button
                type="button"
                className={`stop-row${selectedStop === cs.stopNumber ? ' selected' : ''}`}
                onClick={() => selectStop(selectedStop === cs.stopNumber ? null : cs.stopNumber)}
              >
                <span className="swatch" style={{ background: cs.hex }} />
                <span className="seq">{cs.stopNumber}</span>
                <span className="stop-name">{cs.threadName}</span>
                <span className="stop-count muted">{cs.stitchCount.toLocaleString()}</span>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No design loaded. Open a .DST/.PES file to populate the color sequence.</p>
      )}
    </aside>
  );
}
