/**
 * Pure presentation logic for the Quality panel (Phase 8): score→tone mapping,
 * metric-grid formatting and the hoop-fit line. Kept UI-free so it's testable.
 */
import type { QualityFinding, QualityReport } from '../types/design';

/** Traffic-light tone for a 0..100 score: ≥90 good (green), ≥70 warn (amber), else bad (red). */
export type ScoreTone = 'good' | 'warn' | 'bad';

export function scoreTone(score: number): ScoreTone {
  if (score >= 90) return 'good';
  if (score >= 70) return 'warn';
  return 'bad';
}

/** One cell of the compact metrics grid. */
export interface MetricRow {
  label: string;
  value: string;
}

/** Round to 1 decimal and suffix 'mm'; '—' when the backend didn't report the value. */
function mm(v: number | undefined): string {
  return v == null ? '—' : `${Math.round(v * 10) / 10} mm`;
}

/** Build the metrics grid. Extended fields (max/mean stitch, jumps/1000) show '—' until present. */
export function qualityMetricRows(report: QualityReport): MetricRow[] {
  const m = report.metrics;
  const per1000 = report.jumpsPer1000;
  return [
    { label: 'Stitches', value: m.stitchCount.toLocaleString() },
    {
      label: 'Jumps',
      value: per1000 == null ? String(m.jumpCount) : `${m.jumpCount} (${Math.round(per1000 * 10) / 10}/1000)`,
    },
    { label: 'Travel', value: mm(m.travelMm) },
    { label: 'Color changes', value: String(m.colorChanges) },
    { label: 'Trims', value: String(m.trims) },
    { label: 'Max stitch', value: mm(report.maxStitchMm) },
    { label: 'Mean stitch', value: mm(report.meanStitchMm) },
  ];
}

/** Hoop-fit line. null (report field) = design has no hoop set; undefined = backend didn't report → no line. */
export function hoopFitLabel(fit: boolean | null | undefined): string | null {
  if (fit === undefined) return null;
  if (fit === null) return 'Hoop: no hoop set';
  return fit ? 'Hoop fit: OK' : 'Hoop fit: OVERFLOWS';
}

/** CSS class for a finding row — reuses the validation-report palette (info renders muted). */
export function findingClass(severity: QualityFinding['severity']): string {
  if (severity === 'error') return 'vr-issue';
  if (severity === 'warn') return 'vr-warn';
  return 'muted';
}
