// Staged progress model for long-running backend calls (digitize, lettering).
// Pure logic only: no React, no zustand, no imports — the UI layer polls
// progressAt() on a timer and renders the result.

export interface ProgressStage {
  label: string;
  /** Elapsed time (ms since the request started) at which this stage begins. */
  startMs: number;
}

/**
 * Stage timings for POST /api/digitize. These are UX ESTIMATES of the backend
 * pipeline (upload -> color reduction -> shape tracing -> stitch generation ->
 * quality scoring), NOT telemetry — the server reports no progress. Labels may
 * lag or lead the real work; only the final response closes the bar.
 */
export const DIGITIZE_STAGES: ProgressStage[] = [
  { label: 'Uploading image', startMs: 0 },
  { label: 'Reducing colors', startMs: 800 },
  { label: 'Tracing shapes', startMs: 2500 },
  { label: 'Generating stitches', startMs: 5000 },
  { label: 'Scoring quality', startMs: 9000 },
];

/**
 * Stage timings for lettering generation — same estimate caveat as
 * DIGITIZE_STAGES, but the pipeline skips image work so it is much shorter.
 */
export const LETTERING_STAGES: ProgressStage[] = [
  { label: 'Laying out text', startMs: 0 },
  { label: 'Generating stitches', startMs: 700 },
  { label: 'Scoring quality', startMs: 2500 },
];

/**
 * Hard ceiling on the reported fraction while waiting. The bar must never look
 * finished before the response lands; the caller jumps it to 1 on completion.
 */
export const PROGRESS_CAP = 0.95;

/** Time constant of the exponential approach (ms): ~63% of the cap at t=TAU_MS. */
export const TAU_MS = 6000;

export interface ProgressPoint {
  label: string;
  /** Overall progress in [0, PROGRESS_CAP]; monotonically non-decreasing in elapsedMs. */
  fraction: number;
}

/**
 * Active stage label + overall fraction at `elapsedMs`.
 *
 * Label = the last stage whose startMs <= elapsedMs (sticks at the final stage
 * for arbitrarily large elapsed). Fraction follows cap * (1 - exp(-t / TAU_MS)):
 * 0 at t=0, strictly increasing, asymptotic to PROGRESS_CAP so it never reaches 1.
 * Negative elapsed clamps to stage 0 / fraction 0.
 */
export function progressAt(stages: ProgressStage[], elapsedMs: number): ProgressPoint {
  const t = Number.isFinite(elapsedMs) && elapsedMs > 0 ? elapsedMs : 0;
  let label = stages.length > 0 ? stages[0].label : '';
  for (const stage of stages) {
    if (stage.startMs <= t) label = stage.label;
    else break; // stages are authored in ascending startMs order
  }
  const fraction = PROGRESS_CAP * (1 - Math.exp(-t / TAU_MS));
  return { label, fraction };
}
