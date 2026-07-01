import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { useDesignStore } from '../../store/designStore';
import type { Thread } from '../../types/design';

/** Thread palette (spec §4.4). Loads the catalog; click a swatch to apply it to the selected stop. */
export function ThreadPalette() {
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const { data: threads = [], isLoading, isError } = useQuery({
    queryKey: ['threads'],
    queryFn: () => api.listThreads(),
  });

  const apply = (t: Thread) => {
    if (selectedStop == null) return;
    updateColorStop(selectedStop, {
      hex: t.hex,
      threadName: t.colorName,
      threadBrand: t.brand,
      catalogNumber: t.catalogNumber,
    });
  };

  return (
    <section className="panel">
      <h2 className="panel-title">Thread Palette</h2>
      {isLoading && <p className="muted">Loading…</p>}
      {isError && <p className="muted">Could not load threads.</p>}
      {!isLoading && !isError && (
        <>
          <p className="muted small">
            {selectedStop == null ? 'Select a color stop, then click a thread.' : `Applying to stop ${selectedStop}.`}
          </p>
          <div className="thread-grid">
            {threads.map((t) => (
              <button
                key={`${t.brand}-${t.catalogNumber}`}
                type="button"
                className="thread-swatch"
                style={{ background: t.hex }}
                title={`${t.colorName} · ${t.catalogNumber}`}
                disabled={selectedStop == null}
                onClick={() => apply(t)}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
