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
  colorStops: [{ stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', stitchCount: 0 }],
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
        { stopNumber: 1, threadBrand: 'M', catalogNumber: 'a', threadName: 'Red', hex: '#ff0000', stitchCount: 0 },
        { stopNumber: 2, threadBrand: 'M', catalogNumber: 'b', threadName: 'Blue', hex: '#0000ff', stitchCount: 0 },
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
});
