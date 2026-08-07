/**
 * Stitch Flow angle helper (v2 Part 62).
 *
 * `flowAngleDeg` mirrors the backend's `_flow_line_angle` so the panel shows
 * the user the angle their line actually means at rebuild. These cases pin the
 * shared contract: fold to [0, 180), head/tail symmetry, degenerate → null
 * (the backend falls back to the stored angle in that case).
 */
import { describe, it, expect } from 'vitest';
import { flowAngleDeg, flowDivideValid, flowLineSlot, flowSide, flowSideAngles } from './flow';

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

// The divided-flow helpers mirror the backend's `_flow_divide_valid`,
// `_flow_side` and `_flow_side_angles` (v2 Part 63); the same fixtures the
// backend tests use, so the two sides cannot drift apart silently.
const DIVIDE = [{ x: 20, y: -5 }, { x: 20, y: 25 }]; // vertical, pointing +y
const LEFT_LINE = [{ x: 10, y: 5 }, { x: 10, y: 15 }]; // midpoint left, 90°
const RIGHT_LINE = [{ x: 25, y: 10 }, { x: 35, y: 10 }]; // midpoint right, 0°

describe('flowDivideValid', () => {
  it('needs two distinct endpoints', () => {
    expect(flowDivideValid(null)).toBe(false);
    expect(flowDivideValid(undefined)).toBe(false);
    expect(flowDivideValid([])).toBe(false);
    expect(flowDivideValid([{ x: 5, y: 5 }])).toBe(false);
    expect(flowDivideValid([{ x: 5, y: 5 }, { x: 5, y: 5 }])).toBe(false);
    expect(flowDivideValid(DIVIDE)).toBe(true);
  });
});

describe('flowSide / flowSideAngles', () => {
  it('left of the +y divide is the positive side', () => {
    expect(flowSide(DIVIDE, { x: 10, y: 10 })).toBeGreaterThan(0);
    expect(flowSide(DIVIDE, { x: 30, y: 10 })).toBeLessThan(0);
    expect(flowSide(DIVIDE, { x: 20, y: 10 })).toBe(0);
  });

  it('each side gets the line whose midpoint lies on it', () => {
    expect(flowSideAngles(DIVIDE, LEFT_LINE, RIGHT_LINE)).toEqual({ pos: 90, neg: 0 });
    expect(flowSideAngles(DIVIDE, RIGHT_LINE, LEFT_LINE)).toEqual({ pos: 90, neg: 0 });
  });

  it('an unclaimed side is null (automatic), and first claim wins', () => {
    expect(flowSideAngles(DIVIDE, LEFT_LINE, null)).toEqual({ pos: 90, neg: null });
    const left2 = [{ x: 5, y: 5 }, { x: 15, y: 5 }];
    expect(flowSideAngles(DIVIDE, LEFT_LINE, left2)).toEqual({ pos: 90, neg: null });
  });

  it('a midpoint exactly on the divide claims nothing', () => {
    const onDivide = [{ x: 15, y: 10 }, { x: 25, y: 10 }];
    expect(flowSideAngles(DIVIDE, onDivide, null)).toEqual({ pos: null, neg: null });
  });
});

describe('flowLineSlot', () => {
  it('without a divide everything is Part 62: the one slot is flowLine', () => {
    expect(flowLineSlot({}, LEFT_LINE)).toBe('flowLine');
    expect(flowLineSlot({ flowLine: RIGHT_LINE }, LEFT_LINE)).toBe('flowLine');
  });

  it('a new line replaces the existing line on its own side', () => {
    const obj = { flowDivide: DIVIDE, flowLine: LEFT_LINE, flowLineB: RIGHT_LINE };
    expect(flowLineSlot(obj, [{ x: 5, y: 2 }, { x: 15, y: 2 }])).toBe('flowLine');
    expect(flowLineSlot(obj, [{ x: 26, y: 2 }, { x: 36, y: 2 }])).toBe('flowLineB');
  });

  it('a line on the empty side fills the empty slot', () => {
    const obj = { flowDivide: DIVIDE, flowLine: LEFT_LINE };
    expect(flowLineSlot(obj, RIGHT_LINE)).toBe('flowLineB');
    const objB = { flowDivide: DIVIDE, flowLineB: RIGHT_LINE };
    expect(flowLineSlot(objB, LEFT_LINE)).toBe('flowLine');
  });
});
