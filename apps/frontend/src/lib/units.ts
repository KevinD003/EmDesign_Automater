/**
 * Unit helpers. Embroidery works in millimetres; pyembroidery stores 1/10 mm
 * internally; Konva renders in pixels. Centralize all conversions here.
 */

export const MM_PER_TENTH = 0.1; // pyembroidery internal unit -> mm
export const DEFAULT_PX_PER_MM = 4; // canvas zoom baseline

export function tenthToMm(value: number): number {
  return value * MM_PER_TENTH;
}

export function mmToPx(mm: number, pxPerMm: number = DEFAULT_PX_PER_MM): number {
  return mm * pxPerMm;
}

export function pxToMm(px: number, pxPerMm: number = DEFAULT_PX_PER_MM): number {
  return px / pxPerMm;
}
