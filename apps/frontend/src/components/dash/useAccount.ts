import { useCallback, useEffect, useState } from 'react';
import { api, type LocalAccount } from '../../api/client';
import { useAuthStore } from '../../store/authStore';

/**
 * The signed-in local account with role/plan, refreshed from the server so an
 * admin's plan change shows up without re-login. Supabase sessions have no
 * local account record; they resolve to null and the UI shows the cloud email.
 */
export function useAccount(): {
  account: LocalAccount | null;
  loading: boolean;
  refresh: () => void;
} {
  const session = useAuthStore((s) => s.session);
  const [account, setAccount] = useState<LocalAccount | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    if (!session || session.provider === 'supabase') {
      setAccount(null);
      return;
    }
    setLoading(true);
    api
      .localMe()
      .then((a) => alive && setAccount(a))
      .catch(() => alive && setAccount(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [session, tick]);

  return { account, loading, refresh };
}
