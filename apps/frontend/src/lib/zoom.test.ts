import { describe, expect, it } from 'vitest';
import {
  ZOOM_MAX,
  ZOOM_MIN,
  ZOOM_STEP,
  clampZoom,
  formatZoomPct,
  wheelZoom,
  zoomIn,
  zoomOut,
} from '../components/canvas/zoom';

describe('clampZoom', () => {
  it('pins values below ZOOM_MIN', () => {
    expect(clampZoom(0)).toBe(ZOOM_MIN);
    expect(clampZoom(0.05)).toBe(ZOOM_MIN);
    expect(clampZoom(-3)).toBe(ZOOM_MIN);
  });

  it('pins values above ZOOM_MAX', () => {
    expect(clampZoom(11)).toBe(ZOOM_MAX);
    expect(clampZoom(1e6)).toBe(ZOOM_MAX);
  });

  it('passes in-range values through untouched', () => {
    expect(clampZoom(1)).toBe(1);
    expect(clampZoom(ZOOM_MIN)).toBe(ZOOM_MIN);
    expect(clampZoom(ZOOM_MAX)).toBe(ZOOM_MAX);
  });

  it('falls back to 1 for non-finite input', () => {
    expect(clampZoom(Number.NaN)).toBe(1);
    expect(clampZoom(Number.POSITIVE_INFINITY)).toBe(1);
  });
});

describe('zoomIn / zoomOut', () => {
  it('steps by ZOOM_STEP in range', () => {
    expect(zoomIn(1)).toBeCloseTo(ZOOM_STEP, 10);
    expect(zoomOut(1)).toBeCloseTo(1 / ZOOM_STEP, 10);
  });

  it('round-trips back to the starting scale', () => {
    expect(zoomOut(zoomIn(2))).toBeCloseTo(2, 10);
    expect(zoomIn(zoomOut(2))).toBeCloseTo(2, 10);
  });

  it('saturates at the bounds', () => {
    expect(zoomIn(ZOOM_MAX)).toBe(ZOOM_MAX);
    expect(zoomIn(ZOOM_MAX * 0.99)).toBe(ZOOM_MAX);
    expect(zoomOut(ZOOM_MIN)).toBe(ZOOM_MIN);
    expect(zoomOut(ZOOM_MIN * 1.01)).toBe(ZOOM_MIN);
  });

  it('is a fixed point at the bound, so buttons can disable on equality', () => {
    expect(zoomIn(ZOOM_MAX) === ZOOM_MAX).toBe(true);
    expect(zoomOut(ZOOM_MIN) === ZOOM_MIN).toBe(true);
    expect(zoomIn(1) === 1).toBe(false);
  });
});

describe('wheelZoom', () => {
  it('shrinks on positive deltaY and grows on negative', () => {
    expect(wheelZoom(1, 120)).toBeCloseTo(0.9, 10);
    expect(wheelZoom(1, -120)).toBeCloseTo(1.1, 10);
  });

  it('treats deltaY of 0 as a grow (matches the old ternary)', () => {
    expect(wheelZoom(1, 0)).toBeCloseTo(1.1, 10);
  });

  it('clamps at both ends', () => {
    expect(wheelZoom(ZOOM_MAX, -120)).toBe(ZOOM_MAX);
    expect(wheelZoom(ZOOM_MIN, 120)).toBe(ZOOM_MIN);
    expect(wheelZoom(500, 120)).toBe(ZOOM_MAX * 0.9);
  });
});

describe('formatZoomPct', () => {
  it('rounds to a whole percent', () => {
    expect(formatZoomPct(1)).toBe('100%');
    expect(formatZoomPct(1.254)).toBe('125%');
    expect(formatZoomPct(0.2)).toBe('20%');
    expect(formatZoomPct(ZOOM_MAX)).toBe('1000%');
  });

  it('clamps out-of-range input before formatting', () => {
    expect(formatZoomPct(50)).toBe('1000%');
    expect(formatZoomPct(0)).toBe('20%');
  });
});
