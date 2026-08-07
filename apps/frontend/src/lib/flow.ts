/**
 * Stitch Flow display helpers (v2 Part 62).
 *
 * The backend owns the real behaviour — `_flow_line_angle` in the digitizer
 * derives the fill angle from the stored line at rebuild. This mirror exists so
 * the UI can show the user the angle their line means, with the SAME semantics:
 * y-down design space, folded to [0, 180), degenerate lines mean "no angle".
 * A unit test pins the fold and the degenerate cases against the backend's
 * documented contract.
 */
import type { Point } from '../types/design';

/** Angle in degrees [0, 180) of a two-point flow line, or null if degenerate. */
export function flowAngleDeg(line: Point[] | null | undefined): number | null {
  if (!line || line.length < 2) return null;
  const a = line[0];
  const b = line[line.length - 1];
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9) return null;
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  return ((deg % 180) + 180) % 180;
}

/** True when a divide line is usable: two distinct endpoints (v2 Part 63). */
export function flowDivideValid(divide: Point[] | null | undefined): boolean {
  if (!divide || divide.length < 2) return false;
  const a = divide[0];
  const b = divide[divide.length - 1];
  return Math.abs(b.x - a.x) > 1e-9 || Math.abs(b.y - a.y) > 1e-9;
}

/**
 * Signed side of a point relative to the divide (cross product sign), matching
 * the backend's `_flow_side`: > 0 and < 0 are the two flow regions, 0 is on
 * the line itself.
 */
export function flowSide(divide: Point[], p: Point): number {
  const a = divide[0];
  const b = divide[divide.length - 1];
  return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
}

const mid = (line: Point[]): Point => ({
  x: (line[0].x + line[line.length - 1].x) / 2,
  y: (line[0].y + line[line.length - 1].y) / 2,
});

/**
 * Per-side display angles for a divided object, mirroring the backend's
 * `_flow_side_angles`: each of flowLine/flowLineB claims the side its midpoint
 * lies on, first claim wins, and null means "automatic" for that side.
 */
export function flowSideAngles(
  divide: Point[],
  lineA: Point[] | null | undefined,
  lineB: Point[] | null | undefined,
): { pos: number | null; neg: number | null } {
  const out: { pos: number | null; neg: number | null } = { pos: null, neg: null };
  for (const line of [lineA, lineB]) {
    if (!line || line.length < 2) continue;
    const s = flowSide(divide, mid(line));
    if (s === 0) continue;
    const key = s > 0 ? 'pos' : 'neg';
    if (out[key] === null) out[key] = flowAngleDeg(line);
  }
  return out;
}

/**
 * Which field a freshly drawn direction line should land in (v2 Part 63).
 * Without a valid divide everything is Part 62: the one line is `flowLine`.
 * With one, the new line belongs to the side its midpoint is on: it replaces
 * the existing line on that side, else fills the empty slot, else (both slots
 * taken by the other side / ambiguous midpoint) replaces `flowLine`.
 */
export function flowLineSlot(
  obj: { flowDivide?: Point[] | null; flowLine?: Point[] | null; flowLineB?: Point[] | null },
  newLine: Point[],
): 'flowLine' | 'flowLineB' {
  const divide = obj.flowDivide;
  if (!flowDivideValid(divide)) return 'flowLine';
  const s = flowSide(divide!, mid(newLine));
  if (s !== 0) {
    if (obj.flowLine && obj.flowLine.length >= 2 && flowSide(divide!, mid(obj.flowLine)) * s > 0) {
      return 'flowLine';
    }
    if (obj.flowLineB && obj.flowLineB.length >= 2 && flowSide(divide!, mid(obj.flowLineB)) * s > 0) {
      return 'flowLineB';
    }
  }
  if (!obj.flowLine || obj.flowLine.length < 2) return 'flowLine';
  if (!obj.flowLineB || obj.flowLineB.length < 2) return 'flowLineB';
  return 'flowLine';
}
