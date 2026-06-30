import { create } from 'zustand';
import type { Design } from '../types/design';

interface DesignState {
  design: Design | null;
  selectedObjectId: string | null;
  setDesign: (design: Design | null) => void;
  selectObject: (id: string | null) => void;
  // TODO: updateObject, addColorStop, reorderObjects, undo/redo (spec §3).
}

/** Current-design state. Populated by /api/files/parse once that endpoint is implemented. */
export const useDesignStore = create<DesignState>((set) => ({
  design: null,
  selectedObjectId: null,
  setDesign: (design) => set({ design }),
  selectObject: (id) => set({ selectedObjectId: id }),
}));
