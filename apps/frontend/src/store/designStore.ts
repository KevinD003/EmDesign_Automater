import { create } from 'zustand';
import type { ColorStop, Design } from '../types/design';

const HISTORY_LIMIT = 50;

interface DesignState {
  design: Design | null;
  /** Currently selected color stop (ColorStop.stopNumber), or null. */
  selectedStop: number | null;
  /** Render stitches up to this index; null = whole design. Driven by the StitchPlayer. */
  playHead: number | null;
  /** Undo/redo history of Design snapshots (most-recent-last in `past`). */
  past: Design[];
  future: Design[];
  setDesign: (design: Design | null) => void;
  selectStop: (stopNumber: number | null) => void;
  setPlayHead: (n: number | null) => void;
  updateColorStop: (stopNumber: number, patch: Partial<ColorStop>) => void;
  undo: () => void;
  redo: () => void;
}

/** Current-design state + undo/redo. Populated by /api/files/parse via the Toolbar. */
export const useDesignStore = create<DesignState>((set) => ({
  design: null,
  selectedStop: null,
  playHead: null,
  past: [],
  future: [],
  setDesign: (design) => set({ design, playHead: null, selectedStop: null, past: [], future: [] }),
  selectStop: (stopNumber) => set({ selectedStop: stopNumber }),
  setPlayHead: (n) => set({ playHead: n }),
  updateColorStop: (stopNumber, patch) =>
    set((state) => {
      if (!state.design) return {};
      const next: Design = {
        ...state.design,
        colorStops: state.design.colorStops.map((cs) =>
          cs.stopNumber === stopNumber ? { ...cs, ...patch } : cs,
        ),
      };
      return { design: next, past: [...state.past, state.design].slice(-HISTORY_LIMIT), future: [] };
    }),
  undo: () =>
    set((state) => {
      if (!state.past.length || !state.design) return {};
      const prev = state.past[state.past.length - 1];
      return { design: prev, past: state.past.slice(0, -1), future: [state.design, ...state.future] };
    }),
  redo: () =>
    set((state) => {
      if (!state.future.length || !state.design) return {};
      const next = state.future[0];
      return { design: next, past: [...state.past, state.design], future: state.future.slice(1) };
    }),
}));
