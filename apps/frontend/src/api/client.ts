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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init?.headers ?? {}) },
    ...init,
  });
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

  /** Build the full production package (ZIP: machine file + master + worksheet + color card + preview + summary). */
  exportPackage: async (design: Design, format = 'dst'): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/export/package?format=${encodeURIComponent(format)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

  /** Nearest catalog thread to a target hex color (CIE Lab distance). */
  matchThread: (hex: string) =>
    request<Thread>(`/api/threads/match?hex=${encodeURIComponent(hex)}`, { method: 'POST' }),

  // ── Auth (spec §8) — thin proxy over Supabase GoTrue ──
  signup: (email: string, password: string) =>
    request<Session>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<Session>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

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
};

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
