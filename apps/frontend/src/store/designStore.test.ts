import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore } from './designStore';
import type { Design } from '../types/design';

const makeDesign = (): Design => ({
  name: 't',
  widthMm: 10,
  heightMm: 10,
  stitchCount: 0,
  version: 1,
  status: 'digitized',
  colorStops: [{ stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', penetrationCount: 0 }],
  objects: [],
  stitches: [],
});

beforeEach(() => {
  useDesignStore.setState({ design: null, selectedStop: null, playHead: null, past: [], future: [] });
});

describe('designStore', () => {
  it('setDesign resets selection and history', () => {
    useDesignStore.getState().selectStop(1);
    useDesignStore.getState().setDesign(makeDesign());
    const s = useDesignStore.getState();
    expect(s.design?.name).toBe('t');
    expect(s.selectedStop).toBeNull();
    expect(s.past).toEqual([]);
  });

  it('updateColorStop changes the hex and records history', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateColorStop(1, { hex: '#00ff00' });
    const s = useDesignStore.getState();
    expect(s.design?.colorStops[0].hex).toBe('#00ff00');
    expect(s.past).toHaveLength(1);
    expect(s.future).toEqual([]);
  });

  it('undo restores the previous state; redo re-applies', () => {
    const st = useDesignStore.getState();
    st.setDesign(makeDesign());
    st.updateColorStop(1, { hex: '#00ff00' });

    useDesignStore.getState().undo();
    expect(useDesignStore.getState().design?.colorStops[0].hex).toBe('#ff0000');
    expect(useDesignStore.getState().future).toHaveLength(1);

    useDesignStore.getState().redo();
    expect(useDesignStore.getState().design?.colorStops[0].hex).toBe('#00ff00');
    expect(useDesignStore.getState().future).toEqual([]);
  });

  it('a new edit clears the redo stack', () => {
    const st = useDesignStore.getState();
    st.setDesign(makeDesign());
    st.updateColorStop(1, { hex: '#00ff00' });
    useDesignStore.getState().undo();
    useDesignStore.getState().updateColorStop(1, { hex: '#0000ff' });
    expect(useDesignStore.getState().future).toEqual([]);
    expect(useDesignStore.getState().design?.colorStops[0].hex).toBe('#0000ff');
  });

  it('reorderStop moves a stop, records history, and selection follows', () => {
    const d: Design = {
      ...makeDesign(),
      colorStops: [
        { stopNumber: 1, threadBrand: 'M', catalogNumber: 'a', threadName: 'Red', hex: '#ff0000', penetrationCount: 0 },
        { stopNumber: 2, threadBrand: 'M', catalogNumber: 'b', threadName: 'Blue', hex: '#0000ff', penetrationCount: 0 },
      ],
      stitches: [
        { x: 0, y: 0, command: 'STITCH' },
        { x: 1, y: 1, command: 'STITCH' },
        { x: 1, y: 1, command: 'COLOR_CHANGE' },
        { x: 2, y: 2, command: 'STITCH' },
        { x: 3, y: 3, command: 'END' },
      ],
    };
    useDesignStore.getState().setDesign(d);
    useDesignStore.getState().selectStop(2);
    useDesignStore.getState().reorderStop(2, 'up');
    const s = useDesignStore.getState();
    expect(s.design?.colorStops.map((c) => c.threadName)).toEqual(['Blue', 'Red']);
    expect(s.selectedStop).toBe(1);
    expect(s.past).toHaveLength(1);
  });

  it('reorderStop is a no-op at the boundary (no history)', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().reorderStop(1, 'up');
    expect(useDesignStore.getState().past).toEqual([]);
  });

  it('updateObject patches the object and records history', () => {
    const d: Design = {
      ...makeDesign(),
      objects: [
        {
          sequenceOrder: 1,
          name: 'Fill 1',
          stitchType: 'TATAMI' as Design['objects'][0]['stitchType'],
          colorStop: 1,
          density: 1.67,
          stitchAngle: 0,
          underlayType: 'NONE' as Design['objects'][0]['underlayType'],
          pullCompensation: 0,
          connectMethod: 'TRIM' as Design['objects'][0]['connectMethod'],
          penetrationCount: 10,
        },
      ],
    };
    useDesignStore.getState().setDesign(d);
    useDesignStore.getState().updateObject(1, { density: 0.8, stitchAngle: 45 });
    const s = useDesignStore.getState();
    expect(s.design?.objects[0].density).toBe(0.8);
    expect(s.design?.objects[0].stitchAngle).toBe(45);
    expect(s.past).toHaveLength(1);
  });

  it('replaceDesign keeps selection and records history (undo restores)', () => {
    const d = makeDesign();
    useDesignStore.getState().setDesign(d);
    useDesignStore.getState().selectStop(1);
    const rebuilt: Design = { ...d, stitchCount: 999 };
    useDesignStore.getState().replaceDesign(rebuilt);
    let s = useDesignStore.getState();
    expect(s.design?.stitchCount).toBe(999);
    expect(s.selectedStop).toBe(1); // selection preserved
    expect(s.past).toHaveLength(1);
    useDesignStore.getState().undo();
    s = useDesignStore.getState();
    expect(s.design?.stitchCount).toBe(0); // back to pre-rebuild
  });

  it('setQuality stores a report; setDesign clears it (report belongs to the old design)', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().setQuality({
      score: 88,
      grade: 'B',
      metrics: { stitchCount: 10, colorChanges: 1, trims: 0, jumpCount: 2, travelMm: 5 },
      findings: [],
    });
    expect(useDesignStore.getState().quality?.score).toBe(88);
    useDesignStore.getState().setDesign(makeDesign());
    expect(useDesignStore.getState().quality).toBeNull();
  });

  it('selectObject also selects its color stop', () => {
    const d: Design = {
      ...makeDesign(),
      objects: [
        {
          sequenceOrder: 3,
          name: 'Satin 3',
          stitchType: 'SATIN' as Design['objects'][0]['stitchType'],
          colorStop: 1,
          density: 2.5,
          stitchAngle: -45,
          underlayType: 'NONE' as Design['objects'][0]['underlayType'],
          pullCompensation: 0,
          connectMethod: 'TRIM' as Design['objects'][0]['connectMethod'],
          penetrationCount: 40,
        },
      ],
    };
    useDesignStore.getState().setDesign(d);
    useDesignStore.getState().selectObject(3);
    const s = useDesignStore.getState();
    expect(s.selectedObject).toBe(3);
    expect(s.selectedStop).toBe(1);
  });
});

describe('global busy flag + epoch (CTO A15/N6)', () => {
  it('beginOp claims exclusively; endOp releases', () => {
    useDesignStore.setState({ busyOp: null });
    const s = useDesignStore.getState();
    expect(s.beginOp('rebuild')).toBe(true);
    // a second mutation must be refused while the first is mid-flight
    expect(useDesignStore.getState().beginOp('optimize')).toBe(false);
    expect(useDesignStore.getState().busyOp).toBe('rebuild');
    useDesignStore.getState().endOp();
    expect(useDesignStore.getState().busyOp).toBeNull();
    expect(useDesignStore.getState().beginOp('optimize')).toBe(true);
    useDesignStore.getState().endOp();
  });

  it('loading a design bumps the epoch; in-place replace does not', () => {
    const d = { name: 'a', widthMm: 1, heightMm: 1, stitchCount: 0, version: 1,
                status: 'digitized', objects: [], colorStops: [], stitches: [] } as never;
    const e0 = useDesignStore.getState().epoch;
    useDesignStore.getState().setDesign(d);
    const e1 = useDesignStore.getState().epoch;
    expect(e1).toBe(e0 + 1); // a different design: stale async responses must drop
    useDesignStore.getState().replaceDesign(d);
    expect(useDesignStore.getState().epoch).toBe(e1); // same design, new stitches: keep
  });
});
