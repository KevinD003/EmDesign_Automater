import { create } from 'zustand';
import type { ColorStop, Design } from '../types/design';

interface DesignState {
  design: Design | null;
  /** Currently selected color stop (ColorStop.stopNumber), or null. */
  selectedStop: number | null;
  /** Render stitches up to this index; null = whole design. Driven by the StitchPlayer. */
  playHead: number | null;
  setDesign: (design: Design | null) => void;
  selectStop: (stopNumber: number | null) => void;
  updateColorStop: (stopNumber: number, patch: Partial<ColorStop>) => void;
  setPlayHead: (n: number | null) => void;
}

/** Current-design state. Populated by /api/files/parse via the Toolbar "Open" button. */
export const useDesignStore = create<DesignState>((set) => ({
  design: null,
  selectedStop: null,
  playHead: null,
  setDesign: (design) => set({ design, playHead: null, selectedStop: null }),
  selectStop: (stopNumber) => set({ selectedStop: stopNumber }),
  updateColorStop: (stopNumber, patch) =>
    set((state) =>
      state.design
        ? {
            design: {
              ...state.design,
              colorStops: state.design.colorStops.map((cs) =>
                cs.stopNumber === stopNumber ? { ...cs, ...patch } : cs,
              ),
            },
          }
        : {},
    ),
  setPlayHead: (n) => set({ playHead: n }),
}));
