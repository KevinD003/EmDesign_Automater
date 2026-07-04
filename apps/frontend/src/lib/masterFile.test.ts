import { describe, it, expect } from 'vitest';
import { isMasterFilename, parseMasterDesign } from './masterFile';

const validMaster = JSON.stringify({
  name: 'Logo',
  widthMm: 40,
  heightMm: 30,
  stitchCount: 500,
  version: 2,
  status: 'digitized',
  colorStops: [{ stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', stitchCount: 500 }],
  objects: [{ sequenceOrder: 1, name: 'Fill 1', stitchType: 'TATAMI', colorStop: 1, density: 1.67, stitchAngle: 0, underlayType: 'EDGE_WALK', pullCompensation: 0.2, connectMethod: 'TRIM', stitchCount: 500, contour: [{ x: 0, y: 0 }] }],
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

describe('isMasterFilename', () => {
  it('matches .json and .stiq.json, not embroidery formats', () => {
    expect(isMasterFilename('logo.stiq.json')).toBe(true);
    expect(isMasterFilename('design.json')).toBe(true);
    expect(isMasterFilename('logo.dst')).toBe(false);
    expect(isMasterFilename('logo.pes')).toBe(false);
  });
});
