import { useDesignStore } from '../../store/designStore';

/** Properties panel — edit stitch settings for the selected object (spec §3). Stub. */
export function PropertiesPanel() {
  const selectedId = useDesignStore((s) => s.selectedObjectId);
  // TODO: bind density, stitch angle, underlay type, pull compensation to the selected object.
  return (
    <section className="panel">
      <h2 className="panel-title">Properties</h2>
      {selectedId ? (
        <p className="muted">Editing object {selectedId} — fields stubbed.</p>
      ) : (
        <p className="muted">Select an object to edit density, underlay, and pull compensation.</p>
      )}
    </section>
  );
}
