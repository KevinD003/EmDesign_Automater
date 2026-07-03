import type { ColorStop, Stitch } from '../types/design';
import { FALLBACK_COLORS } from './stitches';

/** One color run as a 3D poly-path (centered at origin, Y up, in the fabric plane z=0). */
export interface ThreadPath {
  points: [number, number, number][];
  color: string;
  stop: number;
}

export interface ThreadScene {
  paths: ThreadPath[];
  /** Largest design dimension in mm — used to frame the camera / size the fabric. */
  extent: number;
}

/**
 * Turn the raw stitch list into centered 3D thread paths for TrueView. Splits into
 * color runs like `buildRuns`, but keeps mm coordinates centered at the design's
 * midpoint and flips Y (screen-down → world-up). Pure — unit-tested.
 */
export function buildThreadScene(stitches: Stitch[], colorStops: ColorStop[]): ThreadScene {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const s of stitches) {
    if (s.command !== 'STITCH') continue;
    if (s.x < minX) minX = s.x;
    if (s.y < minY) minY = s.y;
    if (s.x > maxX) maxX = s.x;
    if (s.y > maxY) maxY = s.y;
  }
  if (!Number.isFinite(minX)) return { paths: [], extent: 1 };

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const extent = Math.max(maxX - minX, maxY - minY, 1);

  const paths: ThreadPath[] = [];
  let cur: [number, number, number][] = [];
  let stopIdx = 0;
  const colorAt = (i: number) => colorStops[i]?.hex ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length];
  const flush = () => {
    if (cur.length >= 2) paths.push({ points: cur, color: colorAt(stopIdx), stop: stopIdx + 1 });
  };

  for (const s of stitches) {
    if (s.command === 'STITCH') {
      cur.push([s.x - cx, -(s.y - cy), 0]);
    } else {
      flush();
      cur = [];
      if (s.command === 'COLOR_CHANGE') stopIdx += 1;
    }
  }
  flush();
  return { paths, extent };
}
