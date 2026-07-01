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
});
