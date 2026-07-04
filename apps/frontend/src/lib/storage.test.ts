import { describe, it, expect } from 'vitest';
import { deleteDesign, listSaved, loadDesign, saveDesign, type KV } from './storage';
import type { Design } from '../types/design';

const fakeKV = (): KV => {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) };
};

const design = (name: string, sc = 10): Design => ({
  name,
  widthMm: 10,
  heightMm: 10,
  stitchCount: sc,
  version: 1,
  status: 'digitized',
  colorStops: [],
  objects: [],
  stitches: [],
});

describe('storage', () => {
  it('saves, lists, and loads a design round-trip', () => {
    const kv = fakeKV();
    const meta = saveDesign(design('Logo', 42), kv, '2026-07-04T10:00:00Z');
    expect(listSaved(kv)).toHaveLength(1);
    expect(listSaved(kv)[0].name).toBe('Logo');
    const loaded = loadDesign(meta.id, kv);
    expect(loaded?.stitchCount).toBe(42);
    expect(loaded?.id).toBe(meta.id);
  });

  it('lists newest first', () => {
    const kv = fakeKV();
    saveDesign(design('Old'), kv, '2026-07-01T00:00:00Z');
    saveDesign(design('New'), kv, '2026-07-04T00:00:00Z');
    expect(listSaved(kv).map((m) => m.name)).toEqual(['New', 'Old']);
  });

  it('overwrites (not duplicates) when re-saving the same id', () => {
    const kv = fakeKV();
    const meta = saveDesign(design('A', 1), kv, '2026-07-04T10:00:00Z');
    const again = saveDesign({ ...design('A', 999), id: meta.id }, kv, '2026-07-04T11:00:00Z');
    expect(again.id).toBe(meta.id);
    expect(listSaved(kv)).toHaveLength(1);
    expect(loadDesign(meta.id, kv)?.stitchCount).toBe(999);
  });

  it('deletes a design and its index entry', () => {
    const kv = fakeKV();
    const meta = saveDesign(design('Gone'), kv);
    deleteDesign(meta.id, kv);
    expect(listSaved(kv)).toHaveLength(0);
    expect(loadDesign(meta.id, kv)).toBeNull();
  });

  it('returns [] / null on corrupt or missing data', () => {
    const kv = fakeKV();
    expect(listSaved(kv)).toEqual([]);
    expect(loadDesign('nope', kv)).toBeNull();
    kv.setItem('stitchiq:index', 'not json');
    expect(listSaved(kv)).toEqual([]);
  });
});
