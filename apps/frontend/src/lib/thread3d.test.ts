import { describe, it, expect } from 'vitest';
import { buildThreadScene } from './thread3d';
import type { ColorStop, Stitch, StitchCommand } from '../types/design';

const S = (x: number, y: number, command: StitchCommand = 'STITCH'): Stitch => ({ x, y, command });
const STOPS: ColorStop[] = [
  { stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', stitchCount: 0 },
  { stopNumber: 2, threadBrand: 'M', catalogNumber: '2', threadName: 'Blue', hex: '#0000ff', stitchCount: 0 },
];

describe('buildThreadScene', () => {
  it('returns empty for no stitches', () => {
    expect(buildThreadScene([], STOPS)).toEqual({ paths: [], extent: 1 });
  });

  it('centers at the origin and flips Y', () => {
    // square 0..10 in both axes → center (5,5); point (0,0) → (-5, +5, 0)
    const { paths, extent } = buildThreadScene([S(0, 0), S(10, 0), S(10, 10), S(0, 10)], STOPS);
    expect(extent).toBe(10);
    expect(paths).toHaveLength(1);
    expect(paths[0].points[0]).toEqual([-5, 5, 0]); // y flipped
    expect(paths[0].points[2]).toEqual([5, -5, 0]);
  });

  it('splits into color runs with the right colors', () => {
    const { paths } = buildThreadScene(
      [S(0, 0), S(2, 2), S(0, 0, 'COLOR_CHANGE'), S(4, 4), S(6, 6)],
      STOPS,
    );
    expect(paths.map((p) => [p.stop, p.color])).toEqual([
      [1, '#ff0000'],
      [2, '#0000ff'],
    ]);
  });

  it('drops runs with fewer than 2 points', () => {
    const { paths } = buildThreadScene([S(0, 0), S(0, 0, 'COLOR_CHANGE'), S(1, 1), S(2, 2)], STOPS);
    expect(paths).toHaveLength(1);
    expect(paths[0].stop).toBe(2);
  });
});
