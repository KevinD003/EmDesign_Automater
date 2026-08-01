/**
 * Design analytics (v2 Part 26) — pure functions behind the dashboard's
 * "current design" section. Everything is computed from the stitch stream the
 * machine will actually sew, the same source of truth the backend quality
 * bench measures; nothing is re-estimated from previews.
 */

import type { ColorStop, Design, Stitch } from '../types/design';

export interface StreamStats {
  stitches: number;
  jumps: number;
  trims: number;
  colorChanges: number;
  sewMm: number;
  travelMm: number;
  /** Travel as a share of all needle movement, 0..1. */
  travelShare: number;
  longestJumpMm: number;
  /** Machine-time estimate at 800 stitches/minute (matches the backend package summary). */
  estMinutes: number;
}

const SPM = 800; // stitches per minute — same constant as the backend summary

/** Distance in mm between two stitch records. */
function dist(a: Stitch, b: Stitch): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Jumps / trims / travel / time for a stitch stream. */
export function streamStats(stitches: Stitch[]): StreamStats {
  let jumps = 0;
  let trims = 0;
  let colorChanges = 0;
  let sewMm = 0;
  let travelMm = 0;
  let longestJumpMm = 0;
  let count = 0;
  let prev: Stitch | null = null;
  for (const s of stitches) {
    if (s.command === 'STITCH') {
      count += 1;
      if (prev) sewMm += dist(prev, s);
    } else if (s.command === 'JUMP') {
      jumps += 1;
      if (prev) {
        const d = dist(prev, s);
        travelMm += d;
        longestJumpMm = Math.max(longestJumpMm, d);
      }
    } else if (s.command === 'TRIM') {
      trims += 1;
    } else if (s.command === 'COLOR_CHANGE') {
      colorChanges += 1;
    }
    prev = s;
  }
  const total = sewMm + travelMm;
  return {
    stitches: count,
    jumps,
    trims,
    colorChanges,
    sewMm,
    travelMm,
    travelShare: total > 0 ? travelMm / total : 0,
    longestJumpMm,
    // Trims and colour changes dominate real machine time far beyond their
    // stitch count: ~2.5s per trim, ~15s per colour change (operator re-thread).
    estMinutes: count / SPM + (trims * 2.5) / 60 + (colorChanges * 15) / 60,
  };
}

export interface HistogramBin {
  /** Inclusive lower edge, mm. */
  from: number;
  to: number;
  count: number;
}

/**
 * Stitch-length histogram in 0.5mm bins up to 7mm (the machine cap is 12.7mm;
 * the digitizer subdivides at 6mm, so a long tail is a defect worth seeing).
 */
export function stitchLengthHistogram(stitches: Stitch[], binMm = 0.5, maxMm = 7): HistogramBin[] {
  const n = Math.ceil(maxMm / binMm);
  const bins: HistogramBin[] = Array.from({ length: n }, (_, i) => ({
    from: i * binMm,
    to: (i + 1) * binMm,
    count: 0,
  }));
  let prev: Stitch | null = null;
  for (const s of stitches) {
    if (s.command === 'STITCH') {
      if (prev?.command === 'STITCH') {
        const d = dist(prev, s);
        const idx = Math.min(n - 1, Math.floor(d / binMm));
        bins[idx].count += 1;
      }
      prev = s;
    } else {
      prev = s.command === 'JUMP' ? s : null;
    }
  }
  return bins;
}

export interface ThreadUsageRow {
  stop: number;
  hex: string;
  name: string;
  /** Thread consumed by this colour block, mm of sewn path. */
  lengthMm: number;
  stitches: number;
}

/** Sewn thread per colour stop, in stream order (COLOR_CHANGE delimits stops). */
export function threadUsage(stitches: Stitch[], colorStops: ColorStop[]): ThreadUsageRow[] {
  const ordered = [...colorStops].sort((a, b) => a.stopNumber - b.stopNumber);
  const rows: ThreadUsageRow[] = ordered.map((c) => ({
    stop: c.stopNumber,
    hex: c.hex,
    name: c.threadName,
    lengthMm: 0,
    stitches: 0,
  }));
  if (rows.length === 0) return rows;
  let idx = 0;
  let prev: Stitch | null = null;
  for (const s of stitches) {
    if (s.command === 'COLOR_CHANGE') {
      idx = Math.min(idx + 1, rows.length - 1);
      prev = null;
      continue;
    }
    if (s.command === 'STITCH') {
      rows[idx].stitches += 1;
      if (prev) rows[idx].lengthMm += dist(prev, s);
      prev = s;
    } else {
      prev = null;
    }
  }
  return rows;
}

/** mm → a human thread length ("4.2 m"). */
export function formatThreadLength(mm: number): string {
  return mm >= 1000 ? `${(mm / 1000).toFixed(1)} m` : `${Math.round(mm)} mm`;
}

/** Minutes → "12m 30s". */
export function formatMinutes(min: number): string {
  const s = Math.round(min * 60);
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
}

/**
 * The capability scoreboard vs the desktop suites — every row traceable to a
 * measured audit in docs/ (COMPETITIVE-GAP-ANALYSIS, COMPETITIVE-BLOCKERS,
 * v2-part24/24b/25 audits). 'us' values are honest: 'yes' only where the
 * feature is generated and tested, 'partial' where a real limitation remains.
 */
export interface CapabilityRow {
  feature: string;
  us: 'yes' | 'partial' | 'no';
  usNote: string;
  competitors: 'yes' | 'partial' | 'no';
}

export const CAPABILITIES: CapabilityRow[] = [
  { feature: 'Auto-digitize from image', us: 'yes', usNote: 'satin / tatami / contour, medial-axis satin', competitors: 'yes' },
  { feature: 'Vector (SVG) import with exact outlines', us: 'yes', usNote: 'exact colours + exact mask; white-on-white works', competitors: 'yes' },
  { feature: 'Per-object fill angle', us: 'yes', usNote: 'principal axis / edge-avoiding auto angle', competitors: 'yes' },
  { feature: 'Curved fills (contour · spiral · radial)', us: 'yes', usNote: 'contour auto on bands; spiral/radial selectable', competitors: 'yes' },
  { feature: 'Underlay auto-selection by width & size', us: 'yes', usNote: 'centre/edge/zigzag + edge+tatami on big fills', competitors: 'yes' },
  { feature: 'Tie-offs + travel routing + long-jump trims', us: 'yes', usNote: 'locks at every cut; in-region jumps become travel', competitors: 'yes' },
  { feature: 'Machine-safety metrics (penetration floor, density)', us: 'yes', usNote: '0 violations corpus-wide, CI-gated — unpublished by competitors', competitors: 'no' },
  { feature: 'Quality score + report in every package', us: 'yes', usNote: '0–100 score, findings, hoop fit', competitors: 'partial' },
  { feature: 'Export formats', us: 'yes', usNote: 'DST/PES/PEC/JEF/EXP/VP3/XXX/U01/CSV', competitors: 'yes' },
  { feature: 'Digitized font library', us: 'partial', usNote: 'TrueType raster path — no hand-digitized glyphs yet', competitors: 'yes' },
  { feature: 'Photo / gradient digitizing', us: 'no', usNote: 'planned — flat colour blocks today', competitors: 'yes' },
  { feature: 'Stitch-level editing', us: 'no', usNote: 'object-level editing only', competitors: 'yes' },
];

/** Convenience bundle for the dashboard. */
export function designAnalytics(design: Design) {
  return {
    stream: streamStats(design.stitches),
    histogram: stitchLengthHistogram(design.stitches),
    usage: threadUsage(design.stitches, design.colorStops),
  };
}
