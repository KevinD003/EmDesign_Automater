import { describe, it, expect } from 'vitest';
import { findingClass, hoopFitLabel, qualityMetricRows, scoreTone } from './quality';
import type { QualityReport } from '../types/design';

const makeReport = (over: Partial<QualityReport> = {}): QualityReport => ({
  score: 95,
  grade: 'A',
  metrics: { stitchCount: 12345, colorChanges: 3, trims: 4, jumpCount: 12, travelMm: 456.78 },
  findings: [],
  ...over,
});

const byLabel = (r: QualityReport) => Object.fromEntries(qualityMetricRows(r).map((m) => [m.label, m.value]));

describe('scoreTone', () => {
  it('maps score bands to tones: ≥90 good, ≥70 warn, else bad', () => {
    expect(scoreTone(100)).toBe('good');
    expect(scoreTone(90)).toBe('good');
    expect(scoreTone(89)).toBe('warn');
    expect(scoreTone(70)).toBe('warn');
    expect(scoreTone(69)).toBe('bad');
    expect(scoreTone(0)).toBe('bad');
  });
});

describe('qualityMetricRows', () => {
  it('formats the base path metrics', () => {
    const rows = byLabel(makeReport());
    expect(rows['Stitches']).toBe((12345).toLocaleString());
    expect(rows['Jumps']).toBe('12');
    expect(rows['Travel']).toBe('456.8 mm');
    expect(rows['Color changes']).toBe('3');
    expect(rows['Trims']).toBe('4');
  });

  it('shows — for extended metrics until the backend provides them', () => {
    const rows = byLabel(makeReport());
    expect(rows['Max stitch']).toBe('—');
    expect(rows['Mean stitch']).toBe('—');
  });

  it('includes jumps/1000 and stitch-length stats when present', () => {
    const rows = byLabel(makeReport({ maxStitchMm: 7.25, meanStitchMm: 2.5, jumpsPer1000: 0.97 }));
    expect(rows['Jumps']).toBe('12 (1/1000)');
    expect(rows['Max stitch']).toBe('7.3 mm');
    expect(rows['Mean stitch']).toBe('2.5 mm');
  });
});

describe('hoopFitLabel', () => {
  it('distinguishes OK / OVERFLOWS / no hoop set / not reported', () => {
    expect(hoopFitLabel(true)).toBe('Hoop fit: OK');
    expect(hoopFitLabel(false)).toBe('Hoop fit: OVERFLOWS');
    expect(hoopFitLabel(null)).toBe('Hoop: no hoop set');
    expect(hoopFitLabel(undefined)).toBeNull();
  });
});

describe('findingClass', () => {
  it('styles error red, warn amber, info muted', () => {
    expect(findingClass('error')).toBe('vr-issue');
    expect(findingClass('warn')).toBe('vr-warn');
    expect(findingClass('info')).toBe('muted');
  });
});
