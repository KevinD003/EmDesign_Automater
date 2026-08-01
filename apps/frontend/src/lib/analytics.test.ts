import { describe, expect, it } from 'vitest';
import type { ColorStop, Stitch } from '../types/design';
import {
  formatMinutes,
  formatThreadLength,
  stitchLengthHistogram,
  streamStats,
  threadUsage,
} from './analytics';

const st = (x: number, y: number, command: Stitch['command'] = 'STITCH'): Stitch => ({ x, y, command });

describe('streamStats', () => {
  it('separates sewing from travel and finds the longest jump', () => {
    const s = streamStats([
      st(0, 0), st(3, 0), st(6, 0),          // 6mm sewn
      st(6, 0, 'TRIM'), st(26, 0, 'JUMP'),   // 20mm travel
      st(26, 0), st(28, 0),                  // 2mm sewn
      st(28, 0, 'END'),
    ]);
    expect(s.stitches).toBe(5);
    expect(s.sewMm).toBeCloseTo(8);
    expect(s.travelMm).toBeCloseTo(20);
    expect(s.longestJumpMm).toBeCloseTo(20);
    expect(s.trims).toBe(1);
    expect(s.travelShare).toBeCloseTo(20 / 28);
  });

  it('charges trims and colour changes real machine time', () => {
    const quiet = streamStats([st(0, 0), st(1, 0)]);
    const cuts = streamStats([st(0, 0), st(1, 0), st(1, 0, 'TRIM'), st(1, 0, 'COLOR_CHANGE')]);
    expect(cuts.estMinutes).toBeGreaterThan(quiet.estMinutes + 0.25); // 2.5s + 15s
  });

  it('is safe on an empty stream', () => {
    const s = streamStats([]);
    expect(s.stitches).toBe(0);
    expect(s.travelShare).toBe(0);
  });
});

describe('stitchLengthHistogram', () => {
  it('bins consecutive stitch segments only', () => {
    const bins = stitchLengthHistogram([
      st(0, 0), st(0.4, 0),                 // 0.4 -> bin 0
      st(0.4, 0, 'JUMP'), st(10, 0, 'JUMP'), // jumps are not stitch length
      st(10, 0), st(13.2, 0),               // 3.2 -> bin 6
    ]);
    expect(bins[0].count).toBe(1);
    expect(bins[6].count).toBe(1);
    expect(bins.reduce((a, b) => a + b.count, 0)).toBe(2);
  });

  it('clamps the overlong tail into the last bin', () => {
    const bins = stitchLengthHistogram([st(0, 0), st(100, 0)]);
    expect(bins[bins.length - 1].count).toBe(1);
  });
});

describe('threadUsage', () => {
  const stops: ColorStop[] = [
    { stopNumber: 1, threadBrand: 'A', catalogNumber: '', threadName: 'Navy', hex: '#123456', stitchCount: 0 },
    { stopNumber: 2, threadBrand: 'A', catalogNumber: '', threadName: 'Gold', hex: '#ddaa22', stitchCount: 0 },
  ];

  it('attributes sewn length per colour block', () => {
    const rows = threadUsage(
      [st(0, 0), st(10, 0), st(10, 0, 'COLOR_CHANGE'), st(0, 0, 'JUMP'), st(0, 0), st(0, 5)],
      stops,
    );
    expect(rows[0].lengthMm).toBeCloseTo(10);
    expect(rows[1].lengthMm).toBeCloseTo(5);
    expect(rows[0].hex).toBe('#123456');
  });

  it('handles zero stops', () => {
    expect(threadUsage([st(0, 0)], [])).toEqual([]);
  });
});

describe('formatters', () => {
  it('formats thread length', () => {
    expect(formatThreadLength(4230)).toBe('4.2 m');
    expect(formatThreadLength(420)).toBe('420 mm');
  });
  it('formats minutes', () => {
    expect(formatMinutes(2.5)).toBe('2m 30s');
  });
});
