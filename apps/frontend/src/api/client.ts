/**
 * Typed API client for the STITCHIQ backend. Stubs map 1:1 to the FastAPI routers;
 * most return 501 until implemented. In dev, Vite proxies /api and /health to :8000.
 */
import type {
  ConvertRequest,
  ConvertResponse,
  Design,
  OptimizeResult,
  QualityReport,
  Thread,
  ValidationReport,
  Worksheet,
} from '../types/design';
import type { Session } from '../lib/auth';
import { exportQuery, type TrimProfile } from '../lib/exportOptions';

export interface DesignStats {
  designCount: number;
  totalStitches: number;
  totalColors: number;
  recent: { id: string; name: string; stitchCount: number; savedAt: string }[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

// Bearer token for authenticated calls (design CRUD, /auth/me). Set on login/logout.
let authToken: string | null = null;
export function setAuthToken(token: string | null): void {
  authToken = token;
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

/**
 * 401 recovery hook (CTO A15/N5). GoTrue access tokens live ~an hour; before
 * this nothing handled a 401, so cloud save silently broke mid-session while
 * the UI kept showing "signed in". The auth store registers a handler that
 * tries the refresh grant once and clears the session on failure; request()
 * retries the original call exactly once with the renewed token.
 */
let unauthorizedHandler: (() => Promise<string | null>) | null = null;
export function setUnauthorizedHandler(fn: (() => Promise<string | null>) | null): void {
  unauthorizedHandler = fn;
}

async function recoverAuth(): Promise<string | null> {
  if (!unauthorizedHandler || !authToken) return null; // anonymous 401s are real
  return unauthorizedHandler();
}

/** Extract a useful message from a JSON error body ({detail: ...}) when present. */
async function errorMessage(res: Response, path: string): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === 'string') return body.detail;
  } catch {
    /* no JSON body */
  }
  return `${res.status} ${res.statusText} — ${path}`;
}

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init?.headers ?? {}) },
    ...init,
  });
  if (res.status === 401 && !retried) {
    const renewed = await recoverAuth();
    if (renewed) return request<T>(path, init, true);
  }
  if (!res.ok) {
    throw new Error(await errorMessage(res, path));
  }
  if (res.status === 204) return undefined as T;
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

  /** Encode a Design to a machine file (.dst/.pes/...) and return the bytes as a Blob for download.
   *  `trimProfile` is the Part 59 machine-aware trim setting; the default is
   *  omitted from the URL so an untouched control sends the request unchanged. */
  exportDesign: async (design: Design, format = 'dst', trimProfile?: TrimProfile): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/export?${exportQuery(format, trimProfile)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(design),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — export`);
    return res.blob();
  },

  /** Build the full production package (ZIP: machine file + master + worksheet + color card + preview + summary). */
  exportPackage: async (design: Design, format = 'dst', trimProfile?: TrimProfile): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/export/package?${exportQuery(format, trimProfile)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(design),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — package`);
    return res.blob();
  },

  worksheet: (design: Design) =>
    request<Worksheet>('/api/worksheet', { method: 'POST', body: JSON.stringify(design) }),

  /** Render the production worksheet to a PDF Blob for download. */
  worksheetPdf: async (design: Design): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/worksheet/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
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

  /** Nearest catalog thread to a target hex color (CIE Lab distance). */
  matchThread: (hex: string) =>
    request<Thread>(`/api/threads/match?hex=${encodeURIComponent(hex)}`, { method: 'POST' }),

  // ── Auth (spec §8) — thin proxy over Supabase GoTrue ──
  signup: (email: string, password: string) =>
    request<Session>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<Session>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  /** Exchange a refresh token for a fresh session (CTO A15/N5). */
  refresh: (refreshToken: string) =>
    request<Session>('/api/auth/refresh', { method: 'POST', body: JSON.stringify({ refreshToken }) }),

  // ── Cloud design persistence (authenticated, per-user) ──
  listDesigns: () => request<Design[]>('/api/designs'),
  designStats: () => request<DesignStats>('/api/designs/stats'),
  getDesign: (id: string) => request<Design>(`/api/designs/${encodeURIComponent(id)}`),
  createDesign: (design: Design) =>
    request<Design>('/api/designs', { method: 'POST', body: JSON.stringify(design) }),
  deleteCloudDesign: (id: string) =>
    request<void>(`/api/designs/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  /** Regenerate all stitches from object contours + current params (digitized designs only). */
  rebuild: (design: Design) =>
    request<Design>('/api/designs/rebuild', { method: 'POST', body: JSON.stringify(design) }),

  // ── Phase 8: optimization engine ──
  /** Reorder objects within each color (nearest-neighbour) to cut travel/jumps. */
  optimizePath: (design: Design) =>
    request<OptimizeResult>('/api/optimize/path', { method: 'POST', body: JSON.stringify(design) }),
  /** Score the design (0..100) + itemized quality findings. */
  analyzeQuality: (design: Design) =>
    request<QualityReport>('/api/optimize/quality', { method: 'POST', body: JSON.stringify(design) }),

  /** Text → embroidery Design (spec §4.10). Spacing is sent snake_case per the API contract. */
  lettering: (text: string, heightMm = 20, fabricType = 'cotton', letterSpacingMm = 0) =>
    request<Design>('/api/lettering', {
      method: 'POST',
      body: JSON.stringify({ text, heightMm, fabricType, letter_spacing_mm: letterSpacingMm }),
    }),

  // ── Local accounts (v2 Part 35): profile, recovery, admin ──
  localMe: () => request<LocalAccount>('/api/auth/local/me'),
  setAccountEmail: (email: string) =>
    request<LocalAccount>('/api/auth/local/email', { method: 'POST', body: JSON.stringify({ email }) }),
  /** Always resolves — the server never reveals whether the address exists. */
  forgotPassword: (email: string) =>
    request<{ sent: boolean }>('/api/auth/local/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPin: string) =>
    request<{ ok: boolean; username: string }>('/api/auth/local/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_pin: newPin }),
    }),
  adminUsers: () => request<AdminUser[]>('/api/admin/users'),
  adminSetPlan: (userId: string, plan: string) =>
    request<AdminUser>(`/api/admin/users/${encodeURIComponent(userId)}/plan`, {
      method: 'POST',
      body: JSON.stringify({ plan }),
    }),
  adminSetRole: (userId: string, role: string) =>
    request<AdminUser>(`/api/admin/users/${encodeURIComponent(userId)}/role`, {
      method: 'POST',
      body: JSON.stringify({ role }),
    }),
  adminStats: () => request<AdminStats>('/api/admin/stats'),

  // ── Image prep (v2 Part 36) ──
  analyzeImage: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<ImageAnalysis>('/api/image/analyze', { method: 'POST', body: form, headers: {} });
  },
  /** Apply the edit chain server-side; resolves to a PNG Blob for preview/digitizing. */
  editImage: async (file: File, params: Record<string, string | number | boolean>): Promise<Blob> => {
    const form = new FormData();
    form.append('file', file);
    for (const [k, v] of Object.entries(params)) form.append(k, String(v));
    const res = await fetch(`${API_BASE}/api/image/edit`, { method: 'POST', body: form, headers: authHeaders() });
    if (!res.ok) throw new Error(await errorMessage(res, '/api/image/edit'));
    return res.blob();
  },

  // ── Thread editor (v2 Part 36) ──
  listCustomThreads: () => request<CustomThread[]>('/api/threads/custom'),
  addCustomThread: (t: { brand: string; name: string; code?: string; hex: string }) =>
    request<CustomThread>('/api/threads/custom', { method: 'POST', body: JSON.stringify(t) }),
  updateCustomThread: (id: string, patch: Partial<CustomThread>) =>
    request<CustomThread>(`/api/threads/custom/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  deleteCustomThread: (id: string) =>
    request<void>(`/api/threads/custom/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  listPalettes: () => request<SavedPalette[]>('/api/threads/palettes'),
  savePalette: (name: string, colors: { hex: string; name?: string; brand?: string; code?: string }[]) =>
    request<SavedPalette>('/api/threads/palettes', { method: 'POST', body: JSON.stringify({ name, colors }) }),
  deletePalette: (id: string) =>
    request<void>(`/api/threads/palettes/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  // ── Stitch (DST) editor (v2 Part 36) ──
  editStitches: (design: Design, ops: StitchOp[]) =>
    request<{ design: Design; notes: string[]; stats: StreamStatsWire }>('/api/stitches/edit', {
      method: 'POST',
      body: JSON.stringify({ design, ops }),
    }),
  stitchStats: (design: Design) =>
    request<StreamStatsWire>('/api/stitches/stats', { method: 'POST', body: JSON.stringify(design) }),
};

export interface ImageAnalysis {
  measurements: { contrastSpan: number; detailVariance: number; meanSaturation: number; colourCells: number };
  tips: string[];
  suggested: { autoLevels: boolean; sharpen: number; denoise: number; posterize: number };
}

export interface CustomThread {
  id: string;
  brand: string;
  name: string;
  code: string;
  hex: string;
  custom: boolean;
  createdAt: string;
}

export interface SavedPalette {
  id: string;
  name: string;
  colors: { hex: string; name: string; brand: string; code: string }[];
  createdAt: string;
}

export type StitchOp =
  | { op: 'delete'; start: number; end: number }
  | { op: 'setCommand'; start: number; end: number; command: string }
  | { op: 'insert'; index: number; x: number; y: number; command?: string }
  | { op: 'movePoint'; index: number; x: number; y: number }
  | { op: 'transform'; start: number; end: number; dx?: number; dy?: number; scale?: number; rotateDeg?: number; mirrorX?: boolean; mirrorY?: boolean }
  | { op: 'splitColor'; index: number }
  | { op: 'removeTrims'; start: number; end: number };

export interface StreamStatsWire {
  total: number;
  stitches: number;
  jumps: number;
  trims: number;
  colorChanges: number;
  longestMm: number;
  overLimit: number;
}

export interface LocalAccount {
  userId: string;
  username: string;
  email: string | null;
  role: 'user' | 'admin';
  plan: 'free' | 'pro' | 'studio';
}

export interface AdminUser {
  userId: string;
  username: string;
  hasPin: boolean;
  createdAt: string;
  email: string | null;
  role: string;
  plan: string;
}

export interface AdminStats {
  users: number;
  admins: number;
  byPlan: Record<string, number>;
  enforcing: boolean;
  features: Record<string, string>;
  planDescriptions: Record<string, string>;
}
