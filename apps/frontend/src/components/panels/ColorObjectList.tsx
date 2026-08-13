import { useDesignStore } from '../../store/designStore';

/**
 * Left sidebar — the stitching sequence (spec §3). Color stops are always shown;
 * digitized designs additionally list their vector objects under each stop
 * (imported stitch files have no objects). Click to select either.
 */
export function ColorObjectList() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const selectedObject = useDesignStore((s) => s.selectedObject);
  const selectStop = useDesignStore((s) => s.selectStop);
  const selectObject = useDesignStore((s) => s.selectObject);
  const stops = design?.colorStops ?? [];
  const objects = design?.objects ?? [];

  return (
    <aside className="panel panel-left">
      <h2 className="panel-title">Color · Object List</h2>
      {stops.length > 0 ? (
        <ol className="object-list">
          {stops.map((cs) => (
            <li key={cs.stopNumber}>
              <button
                type="button"
                className={`stop-row${selectedStop === cs.stopNumber && selectedObject == null ? ' selected' : ''}`}
                onClick={() => selectStop(selectedStop === cs.stopNumber ? null : cs.stopNumber)}
              >
                <span className="swatch" style={{ background: cs.hex }} />
                <span className="seq">{cs.stopNumber}</span>
                <span className="stop-name">{cs.threadName}</span>
                <span className="stop-count muted">{cs.penetrationCount.toLocaleString()}</span>
              </button>
              {objects.filter((o) => o.colorStop === cs.stopNumber).length > 0 && (
                <ul className="obj-sublist">
                  {objects
                    .filter((o) => o.colorStop === cs.stopNumber)
                    .map((o) => (
                      <li key={o.sequenceOrder}>
                        <button
                          type="button"
                          className={`stop-row obj-row${selectedObject === o.sequenceOrder ? ' selected' : ''}`}
                          onClick={() =>
                            selectObject(selectedObject === o.sequenceOrder ? null : o.sequenceOrder)
                          }
                        >
                          <span className="seq">{o.sequenceOrder}</span>
                          <span className="stop-name">{o.name}</span>
                          <span className="stop-count muted">{o.penetrationCount.toLocaleString()}</span>
                        </button>
                      </li>
                    ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No design loaded. Open a .DST/.PES file or Digitize an image.</p>
      )}
    </aside>
  );
}
