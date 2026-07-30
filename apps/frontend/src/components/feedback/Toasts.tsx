import { useEffect } from 'react';
import {
  useToastStore,
  TOAST_TTL_MS,
  type Toast,
  type ToastKind,
} from './toastStore';

// Visual prefix per toast kind — plain glyphs, no icon library dependency.
const KIND_ICON: Record<ToastKind, string> = {
  error: '⚠',
  success: '✓',
  info: 'ℹ',
};

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: number) => void;
}

/** One toast row; owns its auto-dismiss timer so effects stay per-toast. */
function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const { id, kind, message } = toast;

  // Auto-dismiss after the kind's TTL; cancelled if dismissed/unmounted first.
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(id), TOAST_TTL_MS[kind]);
    return () => window.clearTimeout(timer);
  }, [id, kind, onDismiss]);

  return (
    <div className={`toast toast-${kind}`}>
      <span className="toast-icon" aria-hidden="true">
        {KIND_ICON[kind]}
      </span>
      <span className="toast-message">{message}</span>
      <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => onDismiss(id)}>
        ×
      </button>
    </div>
  );
}

/** Fixed bottom-right toast stack; mounted once in the app shell. */
export function Toasts() {
  const toasts = useToastStore((s) => s.toasts);
  const dismissToast = useToastStore((s) => s.dismissToast);

  return (
    <div className="toast-stack" aria-live="polite" role="status">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={dismissToast} />
      ))}
    </div>
  );
}
