import { describe, it, expect } from 'vitest';
import { buildManualDesign, isImportedNotEditable, minPointsFor } from './manual';
import { ConnectMethod, StitchType, UnderlayType, type Design } from '../types/design';

const pts = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 10 },
];

describe('minPointsFor', () => {
  it('run needs 2, area tools need 3', () => {
    expect(minPointsFor('run')).toBe(2);
    expect(minPointsFor('fill')).toBe(3);
    expect(minPointsFor('satin')).toBe(3);
  });
});

describe('isImportedNotEditable', () => {
  const base = { name: 'x', widthMm: 0, heightMm: 0, stitchCount: 0, version: 1, status: 'draft', colorStops: [], objects: [], stitches: [] };
  it('true for imported (stitches, no objects), false otherwise', () => {
    expect(isImportedNotEditable(null)).toBe(false);
    expect(isImportedNotEditable({ ...base } as Design)).toBe(false);
    expect(isImportedNotEditable({ ...base, stitches: [{ x: 0, y: 0, command: 'STITCH' }] } as Design)).toBe(true);
    expect(
      isImportedNotEditable({ ...base, stitches: [{ x: 0, y: 0, command: 'STITCH' }], objects: [{ sequenceOrder: 1 } as never] } as Design),
    ).toBe(false);
  });
});

describe('buildManualDesign', () => {
  it('starts a fresh design with a default color stop + one object', () => {
    const d = buildManualDesign(null, 'fill', pts, null);
    expect(d.colorStops).toHaveLength(1);
    expect(d.objects).toHaveLength(1);
    const o = d.objects[0];
    expect(o.stitchType).toBe(StitchType.Tatami);
    expect(o.colorStop).toBe(1);
    expect(o.contour).toEqual(pts);
    expect(o.sequenceOrder).toBe(1);
  });

  it('run tool → RUNNING_DOUBLE with no fill density', () => {
    const o = buildManualDesign(null, 'run', pts, null).objects[0];
    expect(o.stitchType).toBe(StitchType.RunningDouble);
    expect(o.density).toBe(0);
  });

  it('appends to an existing design, next sequence order, into the selected stop', () => {
    const existing: Design = {
      name: 'd', widthMm: 40, heightMm: 40, stitchCount: 10, version: 1, status: 'digitized',
      colorStops: [
        { stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#f00', stitchCount: 10 },
        { stopNumber: 2, threadBrand: 'M', catalogNumber: '2', threadName: 'Blue', hex: '#00f', stitchCount: 0 },
      ],
      objects: [{ sequenceOrder: 1, name: 'Fill 1', stitchType: StitchType.Tatami, colorStop: 1, density: 1.4, stitchAngle: 0, underlayType: UnderlayType.EdgeWalk, pullCompensation: 0, connectMethod: ConnectMethod.Trim, stitchCount: 10, contour: pts }],
      stitches: [{ x: 0, y: 0, command: 'STITCH' }],
    };
    const d = buildManualDesign(existing, 'satin', pts, 2);
    expect(d.objects).toHaveLength(2);
    expect(d.colorStops).toHaveLength(2); // no new stop added
    const added = d.objects[1];
    expect(added.sequenceOrder).toBe(2);
    expect(added.colorStop).toBe(2); // used the selected stop
    expect(added.stitchType).toBe(StitchType.Satin);
  });
});
