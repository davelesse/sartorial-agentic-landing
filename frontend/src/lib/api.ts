/**
 * ═══════════════════════════════════════════════════════════
 * SARTORIAL AGENTIC — API Client
 * Typed fetch wrapper with JWT auth.
 * ═══════════════════════════════════════════════════════════
 */

const API_BASE = '/api';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = 'ApiError';
  }
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('sa_token');
}

export function setToken(token: string) {
  localStorage.setItem('sa_token', token);
}

export function clearToken() {
  localStorage.removeItem('sa_token');
}

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' && payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  return !isTokenExpired(token);
}

const _pending = new Map<string, Promise<unknown>>();

async function _request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Erreur ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {}

    if (response.status === 401) {
      clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return null as T;
  return response.json();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET') return _request<T>(path, options);

  const existing = _pending.get(path);
  if (existing) return existing as Promise<T>;

  const promise = _request<T>(path, options).finally(() => _pending.delete(path));
  _pending.set(path, promise);
  return promise;
}

// ─── Types ───

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: 'atelier' | 'manufacture' | 'maison';
  sectors: string[];
  subscription_status: 'trialing' | 'active' | 'past_due' | 'canceled';
  trial_ends_at: string | null;
  executions_used: number;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  sector: string;
  category: string;
  min_plan: string;
  is_active: boolean;
  version: string;
}

export interface TenantAgent {
  id: string;
  agent: Agent;
  is_enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

export interface Task {
  id: string;
  tenant_id: string;
  agent_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error_message: string | null;
  tokens_used: number;
  cost_cents: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ─── Auth ───

export const auth = {
  register: (data: {
    email: string;
    password: string;
    full_name?: string;
    tenant_name: string;
    affiliate_code?: string;
  }) =>
    request<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/auth/me'),
};

// ─── Tenant ───

export const tenants = {
  me: () => request<Tenant>('/tenants/me'),

  update: (data: Partial<Pick<Tenant, 'name' | 'sectors'>> & { settings?: Record<string, unknown> }) =>
    request<Tenant>('/tenants/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

// ─── Agents ───

export const agents = {
  catalog: (sector?: string) => {
    const q = sector ? `?sector=${encodeURIComponent(sector)}` : '';
    return request<Agent[]>(`/agents/catalog${q}`);
  },

  mine: () => request<TenantAgent[]>('/agents/mine'),

  activate: (agent_id: string, config: Record<string, unknown> = {}) =>
    request<TenantAgent>('/agents/activate', {
      method: 'POST',
      body: JSON.stringify({ agent_id, config }),
    }),

  update: (tenant_agent_id: string, data: { is_enabled?: boolean; config?: Record<string, unknown> }) =>
    request<TenantAgent>(`/agents/${tenant_agent_id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deactivate: (tenant_agent_id: string) =>
    request<null>(`/agents/${tenant_agent_id}`, { method: 'DELETE' }),
};

// ─── Tasks ───

export const tasks = {
  create: (agent_slug: string, input_data: Record<string, unknown>) =>
    request<Task>('/tasks/', {
      method: 'POST',
      body: JSON.stringify({ agent_slug, input_data }),
    }),

  list: (params: { status?: string; page?: number; page_size?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set('status', params.status);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    return request<{ items: Task[]; total: number; page: number; page_size: number }>(
      `/tasks/?${qs.toString()}`
    );
  },

  get: (id: string) => request<Task>(`/tasks/${id}`),
};

// ─── Stripe ───

export const stripe = {
  plans: () => request<{ plans: Array<{ plan_id: string; name: string; description: string; price_eur_cents: number; price_display: string; features: Record<string, string> }> }>('/stripe/plans'),

  checkout: (data: { plan_id: string; email: string; tenant_id: string; locale?: string; affiliate_code?: string }) =>
    request<{ checkout_url: string }>('/stripe/checkout', {
      method: 'POST',
      body: JSON.stringify({ locale: 'fr', ...data }),
    }),

  portal: (stripe_customer_id: string) =>
    request<{ portal_url: string }>('/stripe/portal', {
      method: 'POST',
      body: JSON.stringify({ stripe_customer_id }),
    }),
};

// ─── Waitlist ───

export const waitlist = {
  join: (email: string, source = 'landing') =>
    request<{ success: boolean; message: string }>('/waitlist/', {
      method: 'POST',
      body: JSON.stringify({ email, source }),
    }),
};
