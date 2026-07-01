import { create } from 'zustand';
import type { Design } from '../types/design';

interface DesignState {
  design: Design | null;
  selectedObjectId: string | null;
  /** Render stitches up to this index; null = show the whole design. Driven by the StitchPlayer. */
  playHead: number | null;
  setDesign: (design: Design | null) => void;
  selectObject: (id: string | null) => void;
  setPlayHead: (n: number | null) => void;
  // TODO (Phase 2): updateObject, addColorStop, reorder, undo/redo.
}

/** Current-design state. Populated by /api/files/parse via the Toolbar "Open" button. */
export const useDesignStore = create<DesignState>((set) => ({
  design: null,
  selectedObjectId: null,
  playHead: null,
  setDesign: (design) => set({ design, playHead: null, selectedObjectId: null }),
  selectObject: (id) => set({ selectedObjectId: id }),
  setPlayHead: (n) => set({ playHead: n }),
}));
