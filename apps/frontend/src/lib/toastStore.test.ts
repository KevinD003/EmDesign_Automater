import { describe, it, expect, beforeEach } from 'vitest';
import {
  useToastStore,
  toastError,
  toastSuccess,
  toastInfo,
  MAX_TOASTS,
  TOAST_TTL_MS,
} from '../components/feedback/toastStore';

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe('toastStore', () => {
  it('push adds toasts and returns monotonically increasing ids', () => {
    const a = useToastStore.getState().pushToast('info', 'one');
    const b = useToastStore.getState().pushToast('error', 'two');
    expect(b).toBeGreaterThan(a);
    const { toasts } = useToastStore.getState();
    expect(toasts.map((t) => t.message)).toEqual(['one', 'two']);
    expect(toasts.map((t) => t.id)).toEqual([a, b]);
  });

  it('dismiss removes only the targeted toast', () => {
    const a = useToastStore.getState().pushToast('info', 'keep');
    const b = useToastStore.getState().pushToast('info', 'drop');
    useToastStore.getState().dismissToast(b);
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].id).toBe(a);
  });

  it('dedupes identical kind+message: returns existing id, list does not grow', () => {
    const a = useToastStore.getState().pushToast('error', 'same');
    const b = useToastStore.getState().pushToast('error', 'same');
    expect(b).toBe(a);
    expect(useToastStore.getState().toasts).toHaveLength(1);
    // Same message with a different kind is NOT a duplicate.
    const c = useToastStore.getState().pushToast('info', 'same');
    expect(c).not.toBe(a);
    expect(useToastStore.getState().toasts).toHaveLength(2);
  });

  it('caps at MAX_TOASTS by dropping the oldest', () => {
    for (let i = 0; i < MAX_TOASTS + 2; i++) {
      useToastStore.getState().pushToast('info', `msg-${i}`);
    }
    const { toasts } = useToastStore.getState();
    expect(toasts).toHaveLength(MAX_TOASTS);
    expect(toasts[0].message).toBe('msg-2'); // msg-0 and msg-1 were dropped
    expect(toasts[toasts.length - 1].message).toBe(`msg-${MAX_TOASTS + 1}`);
  });

  it('clearToasts empties the queue and later ids keep increasing', () => {
    const a = useToastStore.getState().pushToast('info', 'x');
    useToastStore.getState().clearToasts();
    expect(useToastStore.getState().toasts).toEqual([]);
    const b = useToastStore.getState().pushToast('info', 'x');
    expect(b).toBeGreaterThan(a);
  });

  it('convenience functions push with the correct kind', () => {
    toastError('e');
    toastSuccess('s');
    toastInfo('i');
    const kinds = useToastStore.getState().toasts.map((t) => t.kind);
    expect(kinds).toEqual(['error', 'success', 'info']);
  });

  it('exports a TTL for every kind', () => {
    expect(TOAST_TTL_MS.error).toBeGreaterThan(0);
    expect(TOAST_TTL_MS.success).toBeGreaterThan(0);
    expect(TOAST_TTL_MS.info).toBeGreaterThan(0);
  });
});
