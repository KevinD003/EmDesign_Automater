/**
 * Pure zoom math for the stitch canvas — no React/Konva imports so it is
 * unit-testable in a plain node env.
 */

export const ZOOM_MIN = 0.2; // matches the historic wheel clamp in StitchCanvas
export const ZOOM_MAX = 10; // matches the historic wheel clamp in StitchCanvas
export const ZOOM_STEP = 1.25; // per button press; multiplicative so steps feel even at any scale

// Wheel factors preserve the pre-existing scroll feel (finer than a button step).
const WHEEL_SHRINK = 0.9;
const WHEEL_GROW = 1.1;

/** Clamp to [ZOOM_MIN, ZOOM_MAX]; non-finite input falls back to 1 (unzoomed). */
export function clampZoom(s: number): number {
  if (!Number.isFinite(s)) return 1;
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, s));
}

export function zoomIn(s: number): number {
  return clampZoom(clampZoom(s) * ZOOM_STEP);
}

export function zoomOut(s: number): number {
  return clampZoom(clampZoom(s) / ZOOM_STEP);
}

/** Wheel step: deltaY > 0 (scroll down) shrinks, otherwise grows. */
export function wheelZoom(s: number, deltaY: number): number {
  return clampZoom(clampZoom(s) * (deltaY > 0 ? WHEEL_SHRINK : WHEEL_GROW));
}

/** Readout label, e.g. 1.254 → '125%'. */
export function formatZoomPct(s: number): string {
  return `${Math.round(clampZoom(s) * 100)}%`;
}
