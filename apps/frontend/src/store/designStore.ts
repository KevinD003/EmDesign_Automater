import { create } from 'zustand';
import type { ColorStop, Design, DesignObject, Point, QualityReport } from '../types/design';
import { reorderColorStop } from '../lib/stitches';

const HISTORY_LIMIT = 50;

/** Manual digitizing tool. 'select' = normal edit/pan; others = draw mode. */
export type Tool = 'select' | 'run' | 'satin' | 'fill' | 'flow' | 'divide';
/** The manual DRAW tools. 'flow' and 'divide' are not ones: each captures two
 *  clicks for the selected object's Stitch Flow metadata and never creates an
 *  object ('flow' = a direction line, 'divide' = the Part 63 divide line). */
export const MANUAL_TOOLS = ['run', 'satin', 'fill'] as const;

interface DesignState {
  design: Design | null;
  /** Monotonic design identity (CTO A15/N6): bumped whenever a different
   *  design is LOADED (setDesign). Async flows capture it before awaiting and
   *  drop responses whose epoch no longer matches — a rebuild that lands after
   *  the user opened another file must not clobber the new design. */
  epoch: number;
  /** The one in-flight server mutation ('rebuild' | 'optimize' | 'digitize' |
   *  ...), or null. ONE flag across Apply/Optimize/Open/Load (N6): before it,
   *  each component kept a private busy state and two mutations could
   *  interleave, racing their replaceDesign calls. */
  busyOp: string | null;
  /** Claim the busy flag; false = something else is already running. */
  beginOp: (op: string) => boolean;
  endOp: () => void;
  /** Currently selected color stop (ColorStop.stopNumber), or null. */
  selectedStop: number | null;
  /** Currently selected object (DesignObject.sequenceOrder), or null. Digitized designs only. */
  selectedObject: number | null;
  /** Render stitches up to this index; null = whole design. Driven by the StitchPlayer. */
  playHead: number | null;
  /** Active manual-digitizing tool + the points drawn so far (design-mm). */
  activeTool: Tool;
  draft: Point[];
  /** Latest quality report for the current design (auto after digitize/lettering, or the Quality button). */
  quality: QualityReport | null;
  past: Design[];
  future: Design[];
  setDesign: (design: Design | null) => void;
  /** Set the current design's id (after a local save) WITHOUT touching undo history. */
  setDesignId: (id: string) => void;
  /** Swap in a server-modified design (e.g. after /designs/rebuild), KEEPING selection + history. */
  replaceDesign: (design: Design) => void;
  selectStop: (stopNumber: number | null) => void;
  selectObject: (sequenceOrder: number | null) => void;
  setPlayHead: (n: number | null) => void;
  updateColorStop: (stopNumber: number, patch: Partial<ColorStop>) => void;
  updateObject: (sequenceOrder: number, patch: Partial<DesignObject>) => void;
  reorderStop: (stopNumber: number, direction: 'up' | 'down') => void;
  setQuality: (report: QualityReport | null) => void;
  setTool: (tool: Tool) => void;
  addDraftPoint: (p: Point) => void;
  undoDraftPoint: () => void;
  clearDraft: () => void;
  undo: () => void;
  redo: () => void;
}

const push = (past: Design[], d: Design) => [...past, d].slice(-HISTORY_LIMIT);

/** Current-design state + undo/redo. Populated by /api/files/parse or /api/digitize. */
export const useDesignStore = create<DesignState>((set, get) => ({
  design: null,
  epoch: 0,
  busyOp: null,
  beginOp: (op) => {
    if (get().busyOp) return false;
    set({ busyOp: op });
    return true;
  },
  endOp: () => set({ busyOp: null }),
  selectedStop: null,
  selectedObject: null,
  playHead: null,
  activeTool: 'select',
  draft: [],
  quality: null,
  past: [],
  future: [],
  setDesign: (design) =>
    // Also drop any in-progress manual draw — a stale tool/draft must never leak onto a
    // freshly loaded design (Open/Load/Digitize/CloudOpen all route through here).
    // The quality report belongs to the outgoing design, so it goes too.
    set((state) => ({
      design,
      epoch: state.epoch + 1,
      playHead: null,
      selectedStop: null,
      selectedObject: null,
      activeTool: 'select',
      draft: [],
      quality: null,
      past: [],
      future: [],
    })),
  setDesignId: (id) => set((state) => (state.design ? { design: { ...state.design, id } } : {})),
  replaceDesign: (design) =>
    set((state) => (state.design ? { design, past: push(state.past, state.design), future: [] } : { design })),
  selectStop: (stopNumber) => set({ selectedStop: stopNumber, selectedObject: null }),
  selectObject: (sequenceOrder) =>
    set((state) => {
      const obj = state.design?.objects.find((o) => o.sequenceOrder === sequenceOrder) ?? null;
      return { selectedObject: sequenceOrder, selectedStop: obj ? obj.colorStop : state.selectedStop };
    }),
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
      return { design: next, past: push(state.past, state.design), future: [] };
    }),
  updateObject: (sequenceOrder, patch) =>
    set((state) => {
      if (!state.design) return {};
      const next: Design = {
        ...state.design,
        objects: state.design.objects.map((o) =>
          o.sequenceOrder === sequenceOrder ? { ...o, ...patch } : o,
        ),
      };
      return { design: next, past: push(state.past, state.design), future: [] };
    }),
  reorderStop: (stopNumber, direction) =>
    set((state) => {
      if (!state.design) return {};
      const next = reorderColorStop(state.design, stopNumber, direction);
      if (next === state.design) return {}; // boundary / structure mismatch → no-op
      const movedTo = direction === 'up' ? stopNumber - 1 : stopNumber + 1;
      return {
        design: next,
        selectedStop: state.selectedStop === stopNumber ? movedTo : state.selectedStop,
        past: push(state.past, state.design),
        future: [],
      };
    }),
  setQuality: (report) => set({ quality: report }),
  setTool: (tool) => set({ activeTool: tool, draft: [] }),
  addDraftPoint: (p) => set((state) => ({ draft: [...state.draft, p] })),
  undoDraftPoint: () => set((state) => ({ draft: state.draft.slice(0, -1) })),
  clearDraft: () => set({ draft: [] }),
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
