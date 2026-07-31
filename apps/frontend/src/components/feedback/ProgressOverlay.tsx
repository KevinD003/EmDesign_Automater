import { useEffect, useRef, useState } from 'react';
import { progressAt, type ProgressStage } from './progressStages';

// Repaint cadence of the bar. 200ms is well under the CSS width transition (0.2s)
// so the fill animates continuously without spending a frame budget on re-renders.
const PROGRESS_TICK_MS = 200;

/** Milliseconds since mount, re-rendered every PROGRESS_TICK_MS; interval cleared on unmount. */
function useElapsedMs(): number {
  const startRef = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setElapsed(Date.now() - startRef.current), PROGRESS_TICK_MS);
    return () => window.clearInterval(timer);
  }, []);
  return elapsed;
}

/**
 * Blocking overlay for a long backend call. Progress is an estimate from
 * `stages` (see progressStages.ts) — it never reaches 100%; unmounting the
 * overlay is what signals completion.
 */
export function ProgressOverlay({ title, stages }: { title: string; stages: ProgressStage[] }) {
  const elapsed = useElapsedMs();
  const { label, fraction } = progressAt(stages, elapsed);
  const percent = Math.round(fraction * 100);
  return (
    <div className="progress-overlay">
      <div className="progress-card">
        <strong>{title}</strong>
        <div
          className="progress-track"
          role="progressbar"
          aria-label={title}
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <div className="progress-stage">{label}</div>
      </div>
    </div>
  );
}
