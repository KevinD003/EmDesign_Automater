import type { Design } from '../types/design';

/**
 * Parse a STITCHIQ master file (.stiq.json — the full editable Design exported in the
 * production package). Unlike a machine format (.dst/.pes), the master preserves objects
 * and contours, so re-importing one restores full editability/regenerability.
 * Pure — unit-tested. Throws on anything that isn't a plausible master.
 */
export function parseMasterDesign(text: string): Design {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error('Not valid JSON.');
  }
  if (!raw || typeof raw !== 'object') {
    throw new Error('Not a STITCHIQ master file.');
  }
  const d = raw as Record<string, unknown>;
  if (!Array.isArray(d.stitches) || !Array.isArray(d.colorStops) || !Array.isArray(d.objects)) {
    throw new Error('Missing stitches / colorStops / objects — not a STITCHIQ master (.stiq.json).');
  }
  const num = (v: unknown, fallback = 0) => (Number.isFinite(Number(v)) ? Number(v) : fallback);
  const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

  return {
    id: str(d.id),
    name: str(d.name) ?? 'Imported master',
    widthMm: num(d.widthMm),
    heightMm: num(d.heightMm),
    hoopSize: str(d.hoopSize),
    fabricType: str(d.fabricType),
    stitchCount: num(d.stitchCount, (d.stitches as unknown[]).length),
    colorStops: d.colorStops as Design['colorStops'],
    objects: d.objects as Design['objects'],
    stitches: d.stitches as Design['stitches'],
    version: num(d.version, 1),
    status: (str(d.status) ?? 'draft') as Design['status'],
    createdAt: str(d.createdAt),
  };
}

/** True if a filename looks like a STITCHIQ master / JSON design (not an embroidery format). */
export function isMasterFilename(name: string): boolean {
  return /\.(stiq\.)?json$/i.test(name);
}

/** Serialize a Design to a master .stiq.json string. Round-trips through parseMasterDesign. */
export function serializeMasterDesign(design: Design): string {
  return JSON.stringify(design, null, 2);
}
