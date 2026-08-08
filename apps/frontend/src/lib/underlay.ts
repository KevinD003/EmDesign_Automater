/**
 * Underlay choices per stitch family (CTO A5/C5).
 *
 * Every option offered here is dispatched to a real generator by
 * `rebuild_design` — the old dropdown listed one shared set for all types and
 * the backend collapsed any non-NONE choice to a single per-family default,
 * so most selections were silently fake. Runs/manual/appliqué take no
 * underlay at all, so they get no choices (the panel disables the control).
 *
 * A stored value outside the family's list (a legacy save from the old
 * free-for-all dropdown) is still displayed via `underlayOptions`' `extra`
 * handling so the select never renders blank; the backend maps such values to
 * the family default on rebuild.
 */
import { StitchType, UnderlayType } from '../types/design';

export const UNDERLAY_LABEL: Record<string, string> = {
  [UnderlayType.None]: 'None',
  [UnderlayType.CenterWalk]: 'Center walk',
  [UnderlayType.EdgeWalk]: 'Edge walk',
  [UnderlayType.DoubleZigzag]: 'Double zigzag',
  [UnderlayType.Parallel]: 'Edge walk + tatami',
  [UnderlayType.Contour]: 'Contour (legacy)',
};

const SATIN_UNDERLAYS = [
  UnderlayType.None,
  UnderlayType.CenterWalk,
  UnderlayType.DoubleZigzag,
  UnderlayType.EdgeWalk,
];

const FILL_UNDERLAYS = [UnderlayType.None, UnderlayType.EdgeWalk, UnderlayType.Parallel];

const FILL_TYPES: string[] = [
  StitchType.Tatami,
  StitchType.ContourFill,
  StitchType.SpiralFill,
  StitchType.RadialFill,
];

/** The underlay values rebuild genuinely implements for this stitch type. */
export function underlayFamily(stitchType: string): UnderlayType[] {
  if (stitchType === StitchType.Satin) return SATIN_UNDERLAYS;
  if (FILL_TYPES.includes(stitchType)) return FILL_UNDERLAYS;
  return []; // runs / manual / appliqué: no underlay — control disabled
}

/**
 * Options to render for an object: the family list, plus the object's current
 * value appended when it isn't in the list (legacy saves must stay visible
 * and round-trippable — a controlled select with a value not among its
 * options renders blank). A family with no choices still returns the current
 * value so the disabled control displays what the object carries.
 */
export function underlayOptions(stitchType: string, current: string): string[] {
  const family: string[] = underlayFamily(stitchType);
  if (!family.length) return [current];
  return family.includes(current) ? family : [...family, current];
}
