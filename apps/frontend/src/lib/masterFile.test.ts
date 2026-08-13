import { describe, it, expect } from 'vitest';
import { isMasterFilename, parseMasterDesign, serializeMasterDesign } from './masterFile';
import type { Design } from '../types/design';

const validMaster = JSON.stringify({
  name: 'Logo',
  widthMm: 40,
  heightMm: 30,
  stitchCount: 500,
  version: 2,
  status: 'digitized',
  colorStops: [{ stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', penetrationCount: 500 }],
  objects: [{ sequenceOrder: 1, name: 'Fill 1', stitchType: 'TATAMI', colorStop: 1, density: 1.67, stitchAngle: 0, underlayType: 'EDGE_WALK', pullCompensation: 0.2, connectMethod: 'TRIM', penetrationCount: 500, contour: [{ x: 0, y: 0 }] }],
  stitches: [{ x: 0, y: 0, command: 'STITCH' }, { x: 2, y: 0, command: 'STITCH' }],
});

describe('parseMasterDesign', () => {
  it('parses a valid master, preserving objects + contours', () => {
    const d = parseMasterDesign(validMaster);
    expect(d.name).toBe('Logo');
    expect(d.stitchCount).toBe(500);
    expect(d.objects).toHaveLength(1);
    expect(d.objects[0].contour).toEqual([{ x: 0, y: 0 }]);
    expect(d.colorStops[0].hex).toBe('#ff0000');
  });

  it('defaults name/stitchCount when absent', () => {
    const d = parseMasterDesign(JSON.stringify({ colorStops: [], objects: [], stitches: [{ x: 0, y: 0, command: 'STITCH' }] }));
    expect(d.name).toBe('Imported master');
    expect(d.stitchCount).toBe(1); // falls back to stitches.length
    expect(d.version).toBe(1);
  });

  it('throws on invalid JSON', () => {
    expect(() => parseMasterDesign('{not json')).toThrow(/JSON/);
  });

  it('throws when required arrays are missing', () => {
    expect(() => parseMasterDesign(JSON.stringify({ name: 'x' }))).toThrow(/master/i);
    expect(() => parseMasterDesign(JSON.stringify({ stitches: [], colorStops: {} }))).toThrow();
  });
});

describe('serializeMasterDesign', () => {
  it('round-trips through parseMasterDesign, preserving objects + contours', () => {
    const original = parseMasterDesign(validMaster);
    const round = parseMasterDesign(serializeMasterDesign(original));
    expect(round.name).toBe(original.name);
    expect(round.stitchCount).toBe(original.stitchCount);
    expect(round.version).toBe(original.version);
    expect(round.objects).toEqual(original.objects); // contours, density, etc. preserved
    expect(round.colorStops).toEqual(original.colorStops);
    expect(round.stitches).toEqual(original.stitches);
  });

  it('produces valid parseable JSON for a minimal design', () => {
    const d: Design = {
      name: 'X', widthMm: 5, heightMm: 5, stitchCount: 0, version: 1, status: 'draft',
      colorStops: [], objects: [], stitches: [],
    };
    expect(() => parseMasterDesign(serializeMasterDesign(d))).not.toThrow();
  });
});

describe('isMasterFilename', () => {
  it('matches .json and .stiq.json, not embroidery formats', () => {
    expect(isMasterFilename('logo.stiq.json')).toBe(true);
    expect(isMasterFilename('design.json')).toBe(true);
    expect(isMasterFilename('logo.dst')).toBe(false);
    expect(isMasterFilename('logo.pes')).toBe(false);
  });
});
