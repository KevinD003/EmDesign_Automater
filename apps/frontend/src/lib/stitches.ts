import type { ColorStop, Stitch } from '../types/design';

/** Fallback palette for stops without a hex (e.g. missing color data). */
export const FALLBACK_COLORS = ['#e11d48', '#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d'];

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface StitchRun {
  /** Flat [x0,y0,x1,y1,...] in the design's mm space (untransformed). */
  points: number[];
  color: string;
  /** 1-based color stop this run belongs to. */
  stop: number;
}

/** Bounding box of a stitch list in mm (zeros when empty). Pure — unit-tested. */
export function computeBounds(stitches: Stitch[]): Bounds {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const s of stitches) {
    if (s.x < minX) minX = s.x;
    if (s.y < minY) minY = s.y;
    if (s.x > maxX) maxX = s.x;
    if (s.y > maxY) maxY = s.y;
  }
  if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  return { minX, minY, maxX, maxY };
}

export function colorForStop(colorStops: ColorStop[], stopIndex: number): string {
  return colorStops[stopIndex]?.hex ?? FALLBACK_COLORS[stopIndex % FALLBACK_COLORS.length];
}

/**
 * Group the raw stitch list into color-stop polylines (points in design mm space).
 * Consecutive STITCH commands accumulate into one run; JUMP/TRIM/COLOR_CHANGE/END break
 * it; COLOR_CHANGE advances the stop index. Runs shorter than one segment are dropped.
 * Pure — unit-tested.
 */
export function buildRuns(stitches: Stitch[], colorStops: ColorStop[], limit: number | null = null): StitchRun[] {
  const out: StitchRun[] = [];
  const n = limit == null ? stitches.length : Math.min(limit, stitches.length);
  let cur: number[] = [];
  let stopIdx = 0;
  for (let i = 0; i < n; i += 1) {
    const s = stitches[i];
    if (s.command === 'STITCH') {
      cur.push(s.x, s.y);
    } else {
      if (cur.length >= 4) out.push({ points: cur, color: colorForStop(colorStops, stopIdx), stop: stopIdx + 1 });
      cur = [];
      if (s.command === 'COLOR_CHANGE') stopIdx += 1;
    }
  }
  if (cur.length >= 4) out.push({ points: cur, color: colorForStop(colorStops, stopIdx), stop: stopIdx + 1 });
  return out;
}
