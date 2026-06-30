import { useDesignStore } from '../../store/designStore';

/** Left sidebar — objects in stitching sequence, grouped by color stop (spec §3). */
export function ColorObjectList() {
  const design = useDesignStore((s) => s.design);
  const selectObject = useDesignStore((s) => s.selectObject);

  return (
    <aside className="panel panel-left">
      <h2 className="panel-title">Color · Object List</h2>
      {design && design.objects.length > 0 ? (
        <ol className="object-list">
          {design.objects.map((obj) => (
            <li key={obj.id ?? obj.sequenceOrder}>
              <button type="button" onClick={() => selectObject(obj.id ?? null)}>
                <span className="seq">{obj.sequenceOrder}</span>
                {obj.name} — {obj.stitchType}
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No design loaded. Open a .DST/.PES file to populate the sequence.</p>
      )}
    </aside>
  );
}
