/**
 * Dashboard data + formatting (pure, unit-tested).
 *
 * The studio has no metrics backend yet (revenue/users/conversion arrive with Phase 6
 * accounts/billing), so those KPIs are honestly `null` → rendered as "—". Recent activity,
 * however, is REAL today: it's derived from the locally saved designs in `lib/storage.ts`.
 * Keeping all of this here (not in the component) means no hardcoded numbers leak into the UI.
 */
import { browserKV, listSaved, type KV, type SavedMeta } from './storage';

/** A metric with no data source yet is `null` (never a fake 0). */
export type MetricValue = number | null;

export interface DashboardData {
  revenueCents: MetricValue;
  users: MetricValue;
  conversionRate: MetricValue; // 0..1
  activity: ActivityItem[];
}

export interface ActivityItem {
  id: string;
  name: string;
  savedAt: string; // ISO
  stitchCount: number;
}

export interface StatCard {
  key: 'revenue' | 'users' | 'conversion';
  label: string;
  value: string; // preformatted, "—" when no source
  hint: string;
}

const PLACEHOLDER = '—';
const NO_SOURCE = 'No metrics source yet';

/** US-dollar string from integer cents; null → "—". */
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
  return [
    { key: 'revenue', label: 'Revenue', value: formatCurrency(data.revenueCents), hint: NO_SOURCE },
    { key: 'users', label: 'Users', value: formatCount(data.users), hint: NO_SOURCE },
    { key: 'conversion', label: 'Conversion rate', value: formatPercent(data.conversionRate), hint: NO_SOURCE },
  ];
}

/** True when there's nothing at all to show (all KPIs null AND no activity). */
export function isDashboardEmpty(data: DashboardData): boolean {
  return (
    data.revenueCents == null &&
    data.users == null &&
    data.conversionRate == null &&
    data.activity.length === 0
  );
}

/**
 * Load the dashboard. Async so react-query drives real loading/error states, and so a future
 * Phase-6 metrics endpoint can slot in here without touching the component. Today: KPIs are
 * null (no source), activity comes from locally saved designs.
 */
export async function fetchDashboard(kv: KV = browserKV()): Promise<DashboardData> {
  return {
    revenueCents: null,
    users: null,
    conversionRate: null,
    activity: buildActivity(listSaved(kv)),
  };
}
