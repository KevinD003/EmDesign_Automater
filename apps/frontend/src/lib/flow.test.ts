/**
 * Stitch Flow angle helper (v2 Part 62).
 *
 * `flowAngleDeg` mirrors the backend's `_flow_line_angle` so the panel shows
 * the user the angle their line actually means at rebuild. These cases pin the
 * shared contract: fold to [0, 180), head/tail symmetry, degenerate → null
 * (the backend falls back to the stored angle in that case).
 */
import { describe, it, expect } from 'vitest';
import { flowAngleDeg } from './flow';

describe('flowAngleDeg', () => {
  it('reads the drawn direction: horizontal 0, vertical 90, diagonal 45', () => {
    expect(flowAngleDeg([{ x: 0, y: 0 }, { x: 10, y: 0 }])).toBe(0);
    expect(flowAngleDeg([{ x: 0, y: 0 }, { x: 0, y: 10 }])).toBe(90);
    expect(flowAngleDeg([{ x: 0, y: 0 }, { x: 10, y: 10 }])).toBeCloseTo(45, 9);
  });

  it('a direction has no head or tail: the reversed line is the same angle', () => {
    const fwd = flowAngleDeg([{ x: 2, y: 3 }, { x: 9, y: -4 }]);
    const rev = flowAngleDeg([{ x: 9, y: -4 }, { x: 2, y: 3 }]);
    expect(fwd).not.toBeNull();
    expect(rev).toBeCloseTo(fwd!, 9);
  });

  it('folds into [0, 180) whichever way the line points', () => {
    // pointing "up-left" in y-down space: atan2 gives a negative raw angle
    const a = flowAngleDeg([{ x: 0, y: 0 }, { x: -10, y: -10 }]);
    expect(a).toBeGreaterThanOrEqual(0);
    expect(a).toBeLessThan(180);
    expect(a).toBeCloseTo(45, 9);
  });

  it('uses the endpoints of a longer polyline, matching the backend', () => {
    expect(
      flowAngleDeg([{ x: 0, y: 0 }, { x: 3, y: 9 }, { x: 10, y: 0 }]),
    ).toBe(0);
  });

  it('degenerate lines are null, never an invented angle', () => {
    expect(flowAngleDeg(null)).toBeNull();
    expect(flowAngleDeg(undefined)).toBeNull();
    expect(flowAngleDeg([])).toBeNull();
    expect(flowAngleDeg([{ x: 5, y: 5 }])).toBeNull();
    expect(flowAngleDeg([{ x: 5, y: 5 }, { x: 5, y: 5 }])).toBeNull();
  });
});
