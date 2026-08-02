import { useCallback, useEffect, useState } from 'react';
import { api, type CustomThread, type SavedPalette } from '../../api/client';
import { useDesignStore } from '../../store/designStore';

/**
 * Thread editor (v2 Part 36) — the shop's own thread chart.
 *
 * Every real embroidery shop runs cones the shipped catalogue does not have:
 * a house brand, a customer's matched special, a metallic from one supplier.
 * This panel keeps a per-user chart of those, lets a design's stops be
 * repainted from it in one click, and saves the whole colour set as a named
 * palette so the next job starts from the same threads.
 */
export function ThreadEditor() {
  const design = useDesignStore((s) => s.design);
  const updateColorStop = useDesignStore((s) => s.updateColorStop);
  const [threads, setThreads] = useState<CustomThread[]>([]);
  const [palettes, setPalettes] = useState<SavedPalette[]>([]);
  const [draft, setDraft] = useState({ brand: '', name: '', code: '', hex: '#3987e5' });
  const [paletteName, setPaletteName] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.listCustomThreads(), api.listPalettes()])
      .then(([t, p]) => {
        setThreads(t);
        setPalettes(p);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(load, [load]);

  const wrap = async (fn: () => Promise<unknown>, ok?: string) => {
    setErr(null);
    setMsg(null);
    try {
      await fn();
      load();
      if (ok) setMsg(ok);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const addThread = (e: React.FormEvent) => {
    e.preventDefault();
    void wrap(async () => {
      await api.addCustomThread(draft);
      setDraft({ brand: draft.brand, name: '', code: '', hex: '#3987e5' });
    }, 'Thread added to your chart.');
  };

  /** Paint the selected stop (or the first) with a chart thread. */
  const applyThread = (t: CustomThread) => {
    if (!design?.colorStops.length) return;
    const stop = useDesignStore.getState().selectedStop ?? design.colorStops[0].stopNumber;
    updateColorStop(stop, { hex: t.hex, threadName: t.name, threadBrand: t.brand, catalogNumber: t.code });
    setMsg(`Stop ${stop} is now ${t.name}.`);
  };

  const savePalette = (e: React.FormEvent) => {
    e.preventDefault();
    if (!design?.colorStops.length) return;
    void wrap(async () => {
      await api.savePalette(
        paletteName,
        design.colorStops.map((c) => ({
          hex: c.hex,
          name: c.threadName,
          brand: c.threadBrand,
          code: c.catalogNumber,
        })),
      );
      setPaletteName('');
    }, 'Palette saved.');
  };

  const applyPalette = (p: SavedPalette) => {
    if (!design) return;
    design.colorStops.forEach((cs, i) => {
      const c = p.colors[i];
      if (c) {
        updateColorStop(cs.stopNumber, {
          hex: c.hex,
          threadName: c.name,
          threadBrand: c.brand,
          catalogNumber: c.code,
        });
      }
    });
    setMsg(
      p.colors.length < design.colorStops.length
        ? `Applied ${p.colors.length} of ${design.colorStops.length} stops — the palette is shorter than this design.`
        : `Applied “${p.name}” to all ${design.colorStops.length} stops.`,
    );
  };

  return (
    <section className="panel te-panel">
      <h2 className="panel-title">Thread editor</h2>

      <form className="te-add" onSubmit={addThread}>
        <input
          aria-label="Brand"
          placeholder="Brand"
          value={draft.brand}
          onChange={(e) => setDraft({ ...draft, brand: e.target.value })}
          required
        />
        <input
          aria-label="Thread name"
          placeholder="Thread name"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          required
        />
        <input
          aria-label="Catalog number"
          placeholder="Code"
          value={draft.code}
          onChange={(e) => setDraft({ ...draft, code: e.target.value })}
        />
        <input
          aria-label="Colour"
          type="color"
          value={draft.hex}
          onChange={(e) => setDraft({ ...draft, hex: e.target.value })}
        />
        <button type="submit" className="primary">Add</button>
      </form>

      <div className="te-list">
        {threads.length === 0 ? (
          <p className="muted small">No custom threads yet — add your shop’s cones above.</p>
        ) : (
          threads.map((t) => (
            <div key={t.id} className="te-row">
              <span className="te-swatch" style={{ background: t.hex }} />
              <button type="button" className="te-apply" onClick={() => applyThread(t)} title="Apply to the selected colour stop">
                {t.name}
              </button>
              <span className="muted small">{t.brand}{t.code ? ` · ${t.code}` : ''}</span>
              <button
                type="button"
                className="te-del"
                aria-label={`Delete ${t.name}`}
                onClick={() => void wrap(() => api.deleteCustomThread(t.id))}
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>

      <h3 className="te-sub">Palettes</h3>
      <form className="te-add" onSubmit={savePalette}>
        <input
          aria-label="Palette name"
          placeholder="Save this design’s colours as…"
          value={paletteName}
          onChange={(e) => setPaletteName(e.target.value)}
          required
        />
        <button type="submit" disabled={!design?.colorStops.length}>Save</button>
      </form>
      <div className="te-list">
        {palettes.map((p) => (
          <div key={p.id} className="te-row">
            <span className="te-mini">
              {p.colors.slice(0, 8).map((c, i) => (
                <span key={`${c.hex}-${i}`} style={{ background: c.hex }} />
              ))}
            </span>
            <button type="button" className="te-apply" onClick={() => applyPalette(p)}>
              {p.name}
            </button>
            <span className="muted small">{p.colors.length}</span>
            <button
              type="button"
              className="te-del"
              aria-label={`Delete ${p.name}`}
              onClick={() => void wrap(() => api.deletePalette(p.id))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {msg ? <p className="te-ok" role="status">{msg}</p> : null}
      {err ? <p className="te-err" role="alert">{err}</p> : null}
    </section>
  );
}
