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
