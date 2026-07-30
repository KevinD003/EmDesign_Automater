import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { useDesignStore } from '../../store/designStore';
import type { Thread } from '../../types/design';
import { toastError } from '../feedback/toastStore';

/** Thread palette (spec §4.4). Loads the catalog; click a swatch to apply it to the selected
 * stop, or snap the stop's current color to the nearest real (orderable) catalog thread. */
export function ThreadPalette() {
  const design = useDesignStore((s) => s.design);
  const selectedStop = useDesignStore((s) => s.selectedStop);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const stop = design?.colorStops.find((c) => c.stopNumber === selectedStop) ?? null;
  const [busy, setBusy] = useState(false);

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

  const matchNearest = async () => {
    if (!stop) return;
    setBusy(true);
    try {
      apply(await api.matchThread(stop.hex));
    } catch (ex) {
      // Color is left as-is; surface why the match didn't apply.
      toastError(
        ex instanceof Error ? `Thread match failed — ${ex.message}` : 'Thread match failed — try again',
      );
    } finally {
      setBusy(false);
    }
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
          {stop && (
            <button type="button" className="nearest-btn" onClick={matchNearest} disabled={busy}>
              {busy ? 'Matching…' : `↳ Nearest catalog thread to ${stop.hex}`}
            </button>
          )}
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
