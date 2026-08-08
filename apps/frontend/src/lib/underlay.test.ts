/**
 * Underlay honesty (CTO A5/C5): the panel may only offer choices the backend
 * genuinely dispatches to a distinct generator on rebuild. These pin the
 * per-family lists, the no-underlay families, and the legacy-value handling
 * that keeps an out-of-family stored value visible instead of blanking the
 * select.
 */
import { describe, expect, it } from 'vitest';

import { StitchType, UnderlayType } from '../types/design';
import { UNDERLAY_LABEL, underlayFamily, underlayOptions } from './underlay';

describe('underlayFamily', () => {
  it('offers satin exactly the generators rebuild implements for satin', () => {
    expect(underlayFamily(StitchType.Satin)).toEqual([
      UnderlayType.None,
      UnderlayType.CenterWalk,
      UnderlayType.DoubleZigzag,
      UnderlayType.EdgeWalk,
    ]);
  });

  it('offers every fill family edge walk and edge+tatami only', () => {
    for (const t of [
      StitchType.Tatami,
      StitchType.ContourFill,
      StitchType.SpiralFill,
      StitchType.RadialFill,
    ]) {
      expect(underlayFamily(t)).toEqual([
        UnderlayType.None,
        UnderlayType.EdgeWalk,
        UnderlayType.Parallel,
      ]);
    }
  });

  it('offers no underlay for runs, manual and applique', () => {
    for (const t of [
      StitchType.RunningSingle,
      StitchType.RunningDouble,
      StitchType.RunningTriple,
      StitchType.Manual,
      StitchType.Applique,
    ]) {
      expect(underlayFamily(t)).toEqual([]);
    }
  });

  it('never offers CONTOUR — no generator exists for it', () => {
    for (const t of Object.values(StitchType)) {
      expect(underlayFamily(t)).not.toContain(UnderlayType.Contour);
    }
  });
});

describe('underlayOptions', () => {
  it('returns the family list when the current value belongs to it', () => {
    expect(underlayOptions(StitchType.Satin, UnderlayType.CenterWalk)).toEqual(
      underlayFamily(StitchType.Satin),
    );
  });

  it('appends a legacy out-of-family value so the select cannot blank', () => {
    const opts = underlayOptions(StitchType.Satin, UnderlayType.Parallel);
    expect(opts.slice(0, -1)).toEqual(underlayFamily(StitchType.Satin));
    expect(opts.at(-1)).toBe(UnderlayType.Parallel);
  });

  it('shows the stored value alone for a no-underlay stitch type', () => {
    expect(underlayOptions(StitchType.RunningSingle, UnderlayType.None)).toEqual([
      UnderlayType.None,
    ]);
  });

  it('labels every offered value in user language', () => {
    for (const t of Object.values(StitchType)) {
      for (const u of underlayFamily(t)) {
        expect(UNDERLAY_LABEL[u]).toBeTruthy();
      }
    }
  });
});
