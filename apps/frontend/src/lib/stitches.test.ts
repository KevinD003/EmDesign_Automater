import { describe, it, expect } from 'vitest';
import { buildRuns, computeBounds } from './stitches';
import type { ColorStop, Stitch, StitchCommand } from '../types/design';

const S = (x: number, y: number, command: StitchCommand = 'STITCH'): Stitch => ({ x, y, command });

const STOPS: ColorStop[] = [
  { stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', stitchCount: 0 },
  { stopNumber: 2, threadBrand: 'M', catalogNumber: '2', threadName: 'Blue', hex: '#0000ff', stitchCount: 0 },
];

describe('computeBounds', () => {
  it('returns zeros for an empty list', () => {
    expect(computeBounds([])).toEqual({ minX: 0, minY: 0, maxX: 0, maxY: 0 });
  });
  it('computes the extent', () => {
    expect(computeBounds([S(1, 2), S(5, 9), S(3, -1)])).toEqual({ minX: 1, minY: -1, maxX: 5, maxY: 9 });
  });
});

describe('buildRuns', () => {
  it('splits on COLOR_CHANGE and assigns stop numbers + colors', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(2, 2), S(0, 0, 'COLOR_CHANGE'), S(3, 3), S(4, 4)], STOPS, null);
    expect(runs).toHaveLength(2);
    expect(runs[0]).toEqual({ points: [0, 0, 1, 1, 2, 2], color: '#ff0000', stop: 1 });
    expect(runs[1]).toEqual({ points: [3, 3, 4, 4], color: '#0000ff', stop: 2 });
  });

  it('breaks a polyline on JUMP/TRIM without advancing the stop', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(0, 0, 'JUMP'), S(5, 5), S(6, 6)], STOPS, null);
    expect(runs).toHaveLength(2);
    expect(runs.every((r) => r.stop === 1)).toBe(true);
  });

  it('respects the limit (stitch-player playback)', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(2, 2), S(3, 3)], STOPS, 2);
    expect(runs).toHaveLength(1);
    expect(runs[0].points).toEqual([0, 0, 1, 1]);
  });

  it('drops runs shorter than one segment', () => {
    const runs = buildRuns([S(0, 0), S(0, 0, 'COLOR_CHANGE'), S(1, 1), S(2, 2)], STOPS, null);
    expect(runs).toHaveLength(1);
    expect(runs[0].stop).toBe(2);
  });

  it('falls back to a palette color when a stop has no hex', () => {
    const runs = buildRuns([S(0, 0), S(1, 1)], [], null);
    expect(runs[0].color).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
