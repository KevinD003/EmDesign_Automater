import { describe, it, expect } from 'vitest';
import { buildRuns, computeBounds, reorderColorStop } from './stitches';
import type { ColorStop, Design, Stitch, StitchCommand } from '../types/design';

const S = (x: number, y: number, command: StitchCommand = 'STITCH'): Stitch => ({ x, y, command });

const STOPS: ColorStop[] = [
  { stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', penetrationCount: 0 },
  { stopNumber: 2, threadBrand: 'M', catalogNumber: '2', threadName: 'Blue', hex: '#0000ff', penetrationCount: 0 },
];

describe('computeBounds', () => {
  it('returns zeros for an empty list', () => {
    expect(computeBounds([])).toEqual({ minX: 0, minY: 0, maxX: 0, maxY: 0 });
  });
  it('computes the extent', () => {
    expect(computeBounds([S(1, 2), S(5, 9), S(3, -1)])).toEqual({ minX: 1, minY: -1, maxX: 5, maxY: 9 });
  });
});

describe('buildRuns', () => {
  it('splits on COLOR_CHANGE and assigns stop numbers + colors', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(2, 2), S(0, 0, 'COLOR_CHANGE'), S(3, 3), S(4, 4)], STOPS, null);
    expect(runs).toHaveLength(2);
    expect(runs[0]).toEqual({ points: [0, 0, 1, 1, 2, 2], color: '#ff0000', stop: 1 });
    expect(runs[1]).toEqual({ points: [3, 3, 4, 4], color: '#0000ff', stop: 2 });
  });

  it('breaks a polyline on JUMP/TRIM without advancing the stop', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(0, 0, 'JUMP'), S(5, 5), S(6, 6)], STOPS, null);
    expect(runs).toHaveLength(2);
    expect(runs.every((r) => r.stop === 1)).toBe(true);
  });

  it('respects the limit (stitch-player playback)', () => {
    const runs = buildRuns([S(0, 0), S(1, 1), S(2, 2), S(3, 3)], STOPS, 2);
    expect(runs).toHaveLength(1);
    expect(runs[0].points).toEqual([0, 0, 1, 1]);
  });

  it('drops runs shorter than one segment', () => {
    const runs = buildRuns([S(0, 0), S(0, 0, 'COLOR_CHANGE'), S(1, 1), S(2, 2)], STOPS, null);
    expect(runs).toHaveLength(1);
    expect(runs[0].stop).toBe(2);
  });

  it('falls back to a palette color when a stop has no hex', () => {
    const runs = buildRuns([S(0, 0), S(1, 1)], [], null);
    expect(runs[0].color).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

const design3 = (): Design => ({
  name: 'd',
  widthMm: 6,
  heightMm: 6,
  stitchCount: 6,
  version: 1,
  status: 'digitized',
  objects: [],
  colorStops: [
    { stopNumber: 1, threadBrand: 'M', catalogNumber: 'a', threadName: 'Red', hex: '#ff0000', penetrationCount: 2 },
    { stopNumber: 2, threadBrand: 'M', catalogNumber: 'b', threadName: 'Green', hex: '#00ff00', penetrationCount: 2 },
    { stopNumber: 3, threadBrand: 'M', catalogNumber: 'c', threadName: 'Blue', hex: '#0000ff', penetrationCount: 2 },
  ],
  stitches: [
    S(0, 0), S(1, 1), S(1, 1, 'COLOR_CHANGE'),
    S(2, 2), S(3, 3), S(3, 3, 'COLOR_CHANGE'),
    S(4, 4), S(5, 5), S(5, 5, 'END'),
  ],
});

describe('reorderColorStop', () => {
  it('moves a stop up: reorders blocks, renumbers, keeps END last', () => {
    const r = reorderColorStop(design3(), 2, 'up');
    expect(r.colorStops.map((c) => c.threadName)).toEqual(['Green', 'Red', 'Blue']);
    expect(r.colorStops.map((c) => c.stopNumber)).toEqual([1, 2, 3]);
    expect(r.stitches[0]).toEqual({ x: 2, y: 2, command: 'STITCH' }); // green block now first
    expect(r.stitches[r.stitches.length - 1].command).toBe('END');
    expect(r.stitches.filter((s) => s.command === 'COLOR_CHANGE')).toHaveLength(2);
  });

  it('moving a stop up then that same stop back down restores the order', () => {
    // move Green (stop 2) up → it becomes stop 1; move stop 1 back down → original order
    const r = reorderColorStop(reorderColorStop(design3(), 2, 'up'), 1, 'down');
    expect(r.colorStops.map((c) => c.threadName)).toEqual(['Red', 'Green', 'Blue']);
  });

  it('no-ops at boundaries and on stitch/stop mismatch (same reference)', () => {
    const d = design3();
    expect(reorderColorStop(d, 1, 'up')).toBe(d);
    expect(reorderColorStop(d, 3, 'down')).toBe(d);
    expect(reorderColorStop({ ...d, stitches: [S(0, 0), S(1, 1)] }, 2, 'up').colorStops).toHaveLength(3);
    expect(reorderColorStop({ ...d, stitches: [S(0, 0), S(1, 1)] }, 2, 'up').stitches).toHaveLength(2);
  });

  it('remaps object colorStop bindings across the swap (CTO A15/N1)', () => {
    // Pre-N1 the objects kept their old numbers, so after ▲/▼ every object
    // pointed at the OTHER color's stop; the next rebuild sewed each region
    // in the other region's thread and Save persisted the corruption.
    const obj = (seq: number, stop: number): Design['objects'][number] =>
      ({ sequenceOrder: seq, colorStop: stop, name: `o${seq}` }) as Design['objects'][number];
    const d = { ...design3(), objects: [obj(1, 1), obj(2, 2), obj(3, 3)] };
    const r = reorderColorStop(d, 2, 'up');
    // Green is now stop 1, Red is stop 2; the green object must follow it.
    const byName = Object.fromEntries(r.objects.map((o) => [o.name, o.colorStop]));
    expect(byName).toEqual({ o1: 2, o2: 1, o3: 3 });
    // Round trip restores the original bindings.
    const back = reorderColorStop(r, 1, 'down');
    expect(back.objects.map((o) => o.colorStop)).toEqual([1, 2, 3]);
  });
});
