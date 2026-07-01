import { useEffect, useRef } from 'react';
import type { ChangeEvent } from 'react';
import { useDesignStore } from '../../store/designStore';

/** Bottom stitch player — animate the stitch sequence (spec §3) by driving the store's playHead. */
export function StitchPlayer() {
  const total = useDesignStore((s) => s.design?.stitches.length ?? 0);
  const playHead = useDesignStore((s) => s.playHead);
  const setPlayHead = useDesignStore((s) => s.setPlayHead);
  const raf = useRef<number | null>(null);
  const playing = useRef(false);

  const value = playHead ?? total;

  const stop = () => {
    playing.current = false;
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    raf.current = null;
  };
  useEffect(() => stop, []);

  const play = () => {
    if (!total) return;
    stop();
    playing.current = true;
    let cur = value >= total ? 0 : value;
    const inc = Math.max(1, Math.floor(total / 300));
    const tick = () => {
      if (!playing.current) return;
      cur = Math.min(total, cur + inc);
      setPlayHead(cur);
      if (cur >= total) {
        playing.current = false;
        return;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  const onScrub = (e: ChangeEvent<HTMLInputElement>) => {
    stop();
    setPlayHead(Number(e.target.value));
  };

  return (
    <footer className="stitch-player">
      <button type="button" onClick={play} disabled={!total}>
        ▶ Play
      </button>
      <button type="button" onClick={() => { stop(); setPlayHead(null); }} disabled={!total}>
        ↺ Reset
      </button>
      <input
        type="range"
        min={0}
        max={total || 1}
        value={value}
        disabled={!total}
        onChange={onScrub}
        aria-label="Stitch progress"
      />
      <span className="muted">
        {total ? `${value.toLocaleString()} / ${total.toLocaleString()} stitches` : 'no design'}
      </span>
    </footer>
  );
}
