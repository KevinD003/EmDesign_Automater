import { create } from 'zustand';

export type ToastKind = 'error' | 'success' | 'info';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

/** At most this many toasts visible; pushing beyond drops the OLDEST. */
export const MAX_TOASTS = 5;

/** Auto-dismiss lifetimes per kind (ms) — consumed by the toast UI, not the store. */
export const TOAST_TTL_MS: Record<ToastKind, number> = {
  error: 8000, // errors linger longest so users can read/report them
  success: 4000,
  info: 5000,
};

interface ToastState {
  toasts: Toast[];
  /** Adds a toast and returns its id (or the existing id for a duplicate kind+message). */
  pushToast: (kind: ToastKind, message: string) => number;
  dismissToast: (id: number) => void;
  clearToasts: () => void;
}

// Monotonic id source — never reset, so ids stay unique across clearToasts().
let nextToastId = 1;

/** App-wide toast queue. UI subscribes; non-React code uses toastError/toastSuccess/toastInfo. */
export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  pushToast: (kind, message) => {
    // Dedupe: an identical visible toast of the same kind is not re-added.
    const existing = get().toasts.find((t) => t.kind === kind && t.message === message);
    if (existing) return existing.id;
    const id = nextToastId++;
    set((state) => ({
      toasts: [...state.toasts, { id, kind, message }].slice(-MAX_TOASTS),
    }));
    return id;
  },
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
  clearToasts: () => set({ toasts: [] }),
}));

// Convenience entry points for non-React code (async handlers, api layer).
export const toastError = (message: string): number =>
  useToastStore.getState().pushToast('error', message);

export const toastSuccess = (message: string): number =>
  useToastStore.getState().pushToast('success', message);

export const toastInfo = (message: string): number =>
  useToastStore.getState().pushToast('info', message);
