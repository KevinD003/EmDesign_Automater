import { describe, it, expect } from 'vitest';
import {
  buildActivity,
  buildStatCards,
  fetchDashboard,
  formatCount,
  formatCurrency,
  formatPercent,
  isDashboardEmpty,
  relativeTime,
  type DashboardData,
} from './dashboard';
import type { KV, SavedMeta } from './storage';

const fakeKV = (): KV => {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) };
};

const meta = (name: string, savedAt: string, sc = 10): SavedMeta => ({ id: name, name, savedAt, stitchCount: sc });

describe('dashboard formatters', () => {
  it('formats currency from cents, "—" for null/NaN', () => {
    expect(formatCurrency(123456)).toBe('$1,234.56');
    expect(formatCurrency(0)).toBe('$0.00');
    expect(formatCurrency(null)).toBe('—');
    expect(formatCurrency(NaN)).toBe('—');
  });

  it('formats counts, "—" for null', () => {
    expect(formatCount(1500)).toBe('1,500');
    expect(formatCount(null)).toBe('—');
  });

  it('formats a 0..1 fraction as a percent, "—" for null', () => {
    expect(formatPercent(0.1234)).toBe('12.3%');
    expect(formatPercent(0)).toBe('0.0%');
    expect(formatPercent(null)).toBe('—');
  });
});

describe('relativeTime', () => {
  const now = new Date('2026-07-04T12:00:00Z');
  it('buckets recent times', () => {
    expect(relativeTime('2026-07-04T11:59:40Z', now)).toBe('just now');
    expect(relativeTime('2026-07-04T11:30:00Z', now)).toBe('30m ago');
    expect(relativeTime('2026-07-04T09:00:00Z', now)).toBe('3h ago');
    expect(relativeTime('2026-07-02T12:00:00Z', now)).toBe('2d ago');
  });
  it('falls back to a date for old / invalid input', () => {
    expect(relativeTime('2026-06-01T12:00:00Z', now)).toBe('2026-06-01');
    expect(relativeTime('not-a-date', now)).toBe('');
  });
});

describe('activity + cards + empty', () => {
  it('maps saved metadata to activity items', () => {
    const act = buildActivity([meta('Logo', '2026-07-04T10:00:00Z', 42)]);
    expect(act).toEqual([{ id: 'Logo', name: 'Logo', savedAt: '2026-07-04T10:00:00Z', stitchCount: 42 }]);
  });

  it('builds three studio KPI cards; colors "—" with no local source', () => {
    const data: DashboardData = {
      designCount: 3,
      totalStitches: 1500,
      totalColors: null,
      activity: [],
      source: 'local',
    };
    const cards = buildStatCards(data);
    expect(cards.map((c) => c.key)).toEqual(['designs', 'stitches', 'colors']);
    expect(cards.map((c) => c.value)).toEqual(['3', '1,500', '—']);
    expect(cards[2].hint).toMatch(/sign in/i);
  });

  it('reports empty only when there are no designs and no activity', () => {
    const base = { totalStitches: null, totalColors: null, source: 'local' as const };
    expect(isDashboardEmpty({ designCount: 0, activity: [], ...base })).toBe(true);
    expect(isDashboardEmpty({ designCount: null, activity: [], ...base })).toBe(true);
    expect(isDashboardEmpty({ designCount: 0, activity: [meta('a', 'x')], ...base })).toBe(false);
    expect(isDashboardEmpty({ designCount: 2, activity: [], ...base })).toBe(false);
  });
});

describe('fetchDashboard (signed out → local)', () => {
  it('derives counts + activity from saved designs; colors have no local source', async () => {
    const kv = fakeKV();
    kv.setItem(
      'stitchiq:index',
      JSON.stringify([meta('Recent', '2026-07-04T10:00:00Z', 5), meta('Older', '2026-07-01T10:00:00Z', 8)]),
    );
    const data = await fetchDashboard({ loggedIn: false, kv });
    expect(data.source).toBe('local');
    expect(data.designCount).toBe(2);
    expect(data.totalStitches).toBe(13);
    expect(data.totalColors).toBeNull();
    expect(data.activity.map((a) => a.name)).toEqual(['Recent', 'Older']); // newest first
  });

  it('yields an empty dashboard when nothing is saved', async () => {
    const data = await fetchDashboard({ loggedIn: false, kv: fakeKV() });
    expect(isDashboardEmpty(data)).toBe(true);
  });
});
