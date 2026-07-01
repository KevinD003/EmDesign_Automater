import type { ColorStop, Design, Stitch } from '../types/design';

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

/** Split a stitch stream into blocks separated by COLOR_CHANGE (the marker is dropped). */
function partitionByColorChange(stitches: Stitch[]): Stitch[][] {
  const blocks: Stitch[][] = [];
  let cur: Stitch[] = [];
  for (const s of stitches) {
    if (s.command === 'COLOR_CHANGE') {
      blocks.push(cur);
      cur = [];
    } else {
      cur.push(s);
    }
  }
  blocks.push(cur);
  return blocks;
}

/** Rejoin blocks with a COLOR_CHANGE between them (positioned at the previous stitch). */
function joinBlocks(blocks: Stitch[][]): Stitch[] {
  const out: Stitch[] = [];
  blocks.forEach((block, i) => {
    if (i > 0) {
      const prev = out[out.length - 1];
      out.push({ x: prev?.x ?? 0, y: prev?.y ?? 0, command: 'COLOR_CHANGE' });
    }
    out.push(...block);
  });
  return out;
}

/**
 * Move a color stop one position up/down: re-sequences the underlying stitch blocks,
 * renumbers stops, and keeps a trailing END last. Returns the SAME design reference on
 * a no-op (boundary or a stitch/stop structure mismatch). Pure — unit-tested.
 */
export function reorderColorStop(design: Design, stopNumber: number, direction: 'up' | 'down'): Design {
  const idx = design.colorStops.findIndex((cs) => cs.stopNumber === stopNumber);
  if (idx < 0) return design;
  const target = direction === 'up' ? idx - 1 : idx + 1;
  if (target < 0 || target >= design.colorStops.length) return design;

  // Keep a trailing END at the very end after reordering.
  const raw = design.stitches.slice();
  const endCmd = raw.length > 0 && raw[raw.length - 1].command === 'END' ? raw.pop() : undefined;

  const blocks = partitionByColorChange(raw);
  if (blocks.length !== design.colorStops.length) return design; // structure mismatch → safe no-op

  const newBlocks = blocks.slice();
  [newBlocks[idx], newBlocks[target]] = [newBlocks[target], newBlocks[idx]];
  const newStitches = joinBlocks(newBlocks);
  if (endCmd) newStitches.push(endCmd);

  const swapped = design.colorStops.slice();
  [swapped[idx], swapped[target]] = [swapped[target], swapped[idx]];
  const newStops = swapped.map((cs, i) => ({ ...cs, stopNumber: i + 1 }));

  return { ...design, stitches: newStitches, colorStops: newStops };
}
