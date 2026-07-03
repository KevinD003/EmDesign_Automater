/**
 * Typed API client for the STITCHIQ backend. Stubs map 1:1 to the FastAPI routers;
 * most return 501 until implemented. In dev, Vite proxies /api and /health to :8000.
 */
import type {
  ConvertRequest,
  ConvertResponse,
  Design,
  Thread,
  ValidationReport,
  Worksheet,
} from '../types/design';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} — ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  /** Upload an embroidery file (.DST/.PES/...) → Design. (First endpoint to implement.) */
  parseFile: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<Design>('/api/files/parse', { method: 'POST', body: form, headers: {} });
  },

  convert: (body: ConvertRequest) =>
    request<ConvertResponse>('/api/convert', { method: 'POST', body: JSON.stringify(body) }),

  digitize: (file: File, fabricType = 'cotton', hoopSize = '100x100', maxColors = 6) => {
    const form = new FormData();
    form.append('file', file);
    form.append('fabric_type', fabricType);
    form.append('hoop_size', hoopSize);
    form.append('max_colors', String(maxColors));
    return request<Design>('/api/digitize', { method: 'POST', body: form, headers: {} });
  },

  /** Encode a Design to a machine file (.dst/.pes/...) and return the bytes as a Blob for download. */
  exportDesign: async (design: Design, format = 'dst'): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/export?format=${encodeURIComponent(format)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(design),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — export`);
    return res.blob();
  },

  worksheet: (design: Design) =>
    request<Worksheet>('/api/worksheet', { method: 'POST', body: JSON.stringify(design) }),

  /** Render the production worksheet to a PDF Blob for download. */
  worksheetPdf: async (design: Design): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/worksheet/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(design),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — worksheet pdf`);
    return res.blob();
  },

  validate: (design: Design) =>
    request<ValidationReport>('/api/export/validate', {
      method: 'POST',
      body: JSON.stringify(design),
    }),

  listThreads: (brand?: string) =>
    request<Thread[]>(`/api/threads${brand ? `?brand=${encodeURIComponent(brand)}` : ''}`),

  listDesigns: () => request<Design[]>('/api/designs'),

  /** Regenerate all stitches from object contours + current params (digitized designs only). */
  rebuild: (design: Design) =>
    request<Design>('/api/designs/rebuild', { method: 'POST', body: JSON.stringify(design) }),

  /** Text → embroidery Design (spec §4.10). */
  lettering: (text: string, heightMm = 20, fabricType = 'cotton') =>
    request<Design>('/api/lettering', {
      method: 'POST',
      body: JSON.stringify({ text, heightMm, fabricType }),
    }),
};
