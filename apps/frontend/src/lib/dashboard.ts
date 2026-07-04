/**
 * Dashboard data + formatting (pure where it can be; unit-tested).
 *
 * The dashboard shows the SIGNED-IN user's real studio metrics — design count, total
 * stitches, colors used — pulled from their Supabase cloud account. Signed out, it falls
 * back to what's saved in THIS browser (localStorage); colors have no local source, so
 * that tile honestly shows "—". All formatting/decisions live here, not in the component,
 * so no hardcoded numbers leak into the UI.
 */
import { api, type DesignStats } from '../api/client';
import { browserKV, listSaved, type KV, type SavedMeta } from './storage';

/** A metric with no data source is `null` (never a fake 0). */
export type MetricValue = number | null;

export type DashboardSource = 'cloud' | 'local';

export interface DashboardData {
  designCount: MetricValue;
  totalStitches: MetricValue;
  totalColors: MetricValue;
  activity: ActivityItem[];
  source: DashboardSource;
}

export interface ActivityItem {
  id: string;
  name: string;
  savedAt: string; // ISO
  stitchCount: number;
}

export interface StatCard {
  key: 'designs' | 'stitches' | 'colors';
  label: string;
  value: string; // preformatted, "—" when no source
  hint: string;
}

const PLACEHOLDER = '—';

/** US-dollar string from integer cents; null → "—". (Retained for future billing tiles.) */
export function formatCurrency(cents: MetricValue): string {
  if (cents == null || !Number.isFinite(cents)) return PLACEHOLDER;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
}

/** Grouped integer count; null → "—". */
export function formatCount(n: MetricValue): string {
  if (n == null || !Number.isFinite(n)) return PLACEHOLDER;
  return new Intl.NumberFormat('en-US').format(Math.round(n));
}

/** Fraction (0..1) → percent with one decimal; null → "—". */
export function formatPercent(fraction: MetricValue): string {
  if (fraction == null || !Number.isFinite(fraction)) return PLACEHOLDER;
  return `${(fraction * 100).toFixed(1)}%`;
}

/** Compact "just now / 5m ago / 3h ago / 2d ago / YYYY-MM-DD" from an ISO timestamp. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '';
  const secs = Math.max(0, Math.round((now.getTime() - then) / 1000));
  if (secs < 45) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return iso.slice(0, 10);
}

/** Saved-design metadata → activity feed (newest first; already sorted by listSaved). */
export function buildActivity(saved: SavedMeta[]): ActivityItem[] {
  return saved.map((m) => ({ id: m.id, name: m.name, savedAt: m.savedAt, stitchCount: m.stitchCount }));
}

/** KPI values → display cards. Formatting decisions live here, not in JSX. */
export function buildStatCards(data: DashboardData): StatCard[] {
  const src = data.source === 'cloud' ? 'From your cloud account' : 'Saved in this browser';
  return [
    { key: 'designs', label: 'My designs', value: formatCount(data.designCount), hint: src },
    { key: 'stitches', label: 'Total stitches', value: formatCount(data.totalStitches), hint: src },
    {
      key: 'colors',
      label: 'Colors used',
      value: formatCount(data.totalColors),
      hint: data.totalColors == null ? 'Sign in to track colors' : src,
    },
  ];
}

/** True when there's nothing to show (no designs AND no activity). */
export function isDashboardEmpty(data: DashboardData): boolean {
  return (!data.designCount || data.designCount === 0) && data.activity.length === 0;
}

function localDashboard(kv: KV | null): DashboardData {
  const saved = kv ? listSaved(kv) : [];
  return {
    designCount: saved.length,
    totalStitches: saved.reduce((sum, m) => sum + (m.stitchCount || 0), 0),
    totalColors: null, // no local source for colors
    activity: buildActivity(saved),
    source: 'local',
  };
}

function statsToDashboard(s: DesignStats): DashboardData {
  return {
    designCount: s.designCount,
    totalStitches: s.totalStitches,
    totalColors: s.totalColors,
    activity: s.recent,
    source: 'cloud',
  };
}

/**
 * Load the dashboard. When signed in, use the real cloud stats endpoint; if that fails
 * (offline / transient), fall back to local. Signed out → local only.
 */
export async function fetchDashboard(
  opts: { loggedIn?: boolean; kv?: KV | null } = {},
): Promise<DashboardData> {
  const kv = opts.kv === undefined ? safeKV() : opts.kv;
  if (opts.loggedIn) {
    try {
      return statsToDashboard(await api.designStats());
    } catch {
      /* fall through to local */
    }
  }
  return localDashboard(kv);
}

function safeKV(): KV | null {
  try {
    return browserKV();
  } catch {
    return null;
  }
}
