import { describe, it, expect } from 'vitest';
import {
  DIGITIZE_STAGES,
  LETTERING_STAGES,
  PROGRESS_CAP,
  progressAt,
  type ProgressStage,
} from '../components/feedback/progressStages';

const ALL_STAGE_SETS: Array<[string, ProgressStage[]]> = [
  ['DIGITIZE_STAGES', DIGITIZE_STAGES],
  ['LETTERING_STAGES', LETTERING_STAGES],
];

describe.each(ALL_STAGE_SETS)('progressAt (%s)', (_name, stages) => {
  it('starts on the first stage with zero fraction', () => {
    const p = progressAt(stages, 0);
    expect(p.label).toBe(stages[0].label);
    expect(p.fraction).toBe(0);
  });

  it('clamps negative elapsed to stage 0 / fraction 0', () => {
    const p = progressAt(stages, -5000);
    expect(p.label).toBe(stages[0].label);
    expect(p.fraction).toBe(0);
  });

  it('switches label exactly at each startMs boundary', () => {
    for (let i = 1; i < stages.length; i += 1) {
      const boundary = stages[i].startMs;
      expect(progressAt(stages, boundary - 1).label).toBe(stages[i - 1].label);
      expect(progressAt(stages, boundary).label).toBe(stages[i].label);
    }
  });

  it('sticks on the last stage for huge elapsed', () => {
    const last = stages[stages.length - 1].label;
    expect(progressAt(stages, 60_000).label).toBe(last);
    expect(progressAt(stages, 3_600_000).label).toBe(last);
  });

  it('is monotone and capped across a sampled ramp', () => {
    let prev = -1;
    for (let t = 0; t <= 30_000; t += 250) {
      const { fraction } = progressAt(stages, t);
      expect(fraction).toBeGreaterThanOrEqual(prev);
      expect(fraction).toBeLessThanOrEqual(PROGRESS_CAP);
      expect(fraction).toBeLessThan(1);
      prev = fraction;
    }
  });

  it('never exceeds the cap even at absurd elapsed', () => {
    expect(progressAt(stages, 1e9).fraction).toBeLessThanOrEqual(PROGRESS_CAP);
    expect(progressAt(stages, 1e9).fraction).toBeCloseTo(PROGRESS_CAP, 6);
  });

  it('makes visible headway within the first few seconds', () => {
    expect(progressAt(stages, 3000).fraction).toBeGreaterThan(0.2);
  });
});

describe('stage table shape', () => {
  it.each(ALL_STAGE_SETS)('%s starts at 0 and ascends', (_name, stages) => {
    expect(stages.length).toBeGreaterThan(0);
    expect(stages[0].startMs).toBe(0);
    for (let i = 1; i < stages.length; i += 1) {
      expect(stages[i].startMs).toBeGreaterThan(stages[i - 1].startMs);
    }
  });

  it('handles an empty stage list without throwing', () => {
    expect(progressAt([], 1000)).toEqual({ label: '', fraction: expect.any(Number) });
  });
});
