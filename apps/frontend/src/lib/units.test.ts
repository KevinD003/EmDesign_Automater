import { describe, it, expect } from 'vitest';
import { mmToPx, pxToMm, tenthToMm } from './units';

describe('units', () => {
  it('converts pyembroidery tenths to mm', () => {
    expect(tenthToMm(500)).toBe(50);
  });
  it('converts mm↔px and round-trips', () => {
    expect(mmToPx(10, 4)).toBe(40);
    expect(pxToMm(40, 4)).toBe(10);
    expect(pxToMm(mmToPx(7.5, 3), 3)).toBeCloseTo(7.5);
  });
});
