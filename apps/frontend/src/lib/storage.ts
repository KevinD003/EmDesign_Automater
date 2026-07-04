import type { Design } from '../types/design';

/**
 * Client-side design persistence via localStorage. This is a local convenience so work
 * survives a refresh — NOT cloud sync (that's Phase 6 / Supabase). The store backend is
 * injectable (KV) so the logic is unit-tested without a browser.
 */
export interface KV {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface SavedMeta {
  id: string;
  name: string;
  savedAt: string; // ISO
  stitchCount: number;
}

const INDEX_KEY = 'stitchiq:index';
const designKey = (id: string) => `stitchiq:design:${id}`;

/** The real browser backend. Throws if called where localStorage is unavailable. */
export function browserKV(): KV {
  return localStorage;
}

function readIndex(kv: KV): SavedMeta[] {
  try {
    const raw = kv.getItem(INDEX_KEY);
    return raw ? (JSON.parse(raw) as SavedMeta[]) : [];
  } catch {
    return [];
  }
}

function writeIndex(kv: KV, index: SavedMeta[]): void {
  kv.setItem(INDEX_KEY, JSON.stringify(index));
}

function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `id-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

/** Saved designs, newest first. */
export function listSaved(kv: KV): SavedMeta[] {
  return readIndex(kv).sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}

/** Save (or overwrite by id if the design already has a known id). Returns the metadata. */
export function saveDesign(design: Design, kv: KV, now: string = new Date().toISOString()): SavedMeta {
  const existing = readIndex(kv);
  const id = design.id && existing.some((m) => m.id === design.id) ? design.id : newId();
  const meta: SavedMeta = { id, name: design.name || 'Untitled', savedAt: now, stitchCount: design.stitchCount };
  kv.setItem(designKey(id), JSON.stringify({ ...design, id }));
  writeIndex(kv, [meta, ...existing.filter((m) => m.id !== id)]);
  return meta;
}

export function loadDesign(id: string, kv: KV): Design | null {
  try {
    const raw = kv.getItem(designKey(id));
    return raw ? (JSON.parse(raw) as Design) : null;
  } catch {
    return null;
  }
}

export function deleteDesign(id: string, kv: KV): void {
  kv.removeItem(designKey(id));
  writeIndex(kv, readIndex(kv).filter((m) => m.id !== id));
}
