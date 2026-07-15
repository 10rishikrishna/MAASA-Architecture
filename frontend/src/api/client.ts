// src/api/client.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const API_V1  = `${API_URL}/api/v1`;

function getToken(): string | null {
  return localStorage.getItem('maasa_token');
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token
    ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...options?.headers },
  });

  if (res.status === 401) {
    localStorage.removeItem('maasa_token');
    localStorage.removeItem('maasa_user');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────

export interface AuthPayload { access_token: string; user_id: string; name: string; email: string; plan: string; }
export interface UserProfile  { user_id: string; email: string; name: string; plan: string; profile_picture_url?: string; }

export const authApi = {
  register: (email: string, password: string, name: string) =>
    request<AuthPayload>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, name }) }),

  login: (email: string, password: string) =>
    request<AuthPayload>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  me: () => request<UserProfile>('/auth/me'),
};

// ── Analysis ──────────────────────────────────────────────

export interface AnalysisSummary {
  id: string; business_problem: string; status: string;
  analysis_time_seconds: number | null; created_at: string;
}
export interface AnalysisDetail extends AnalysisSummary {
  requirements?:          { functional: string[]; non_functional: string[] };
  architecture_design?:   { system_type: string; pattern: string; justification: string; components: any[] };
  database_schema?:       { database_type: string; justification: string; schemas: any[]; indexing_strategies: string[] };
  api_specification?:     { protocol: string; endpoints: any[] };
  deployment_config?:     { infrastructure_as_code: string; orchestration: string; terraform_sample: string; kubernetes_manifest: string };
  security_audit?:        { vulnerability_mitigations: string[]; compliance: string };
  performance_strategies?:{ caching: string; optimization: string };
  diagrams?:              { mermaid: string; ascii: string };
}

export const analyzeApi = {
  list:   (skip = 0, limit = 20) => request<AnalysisSummary[]>(`/analyze?skip=${skip}&limit=${limit}`),
  get:    (id: string)            => request<AnalysisDetail>(`/analyze/${id}`),
  start:  (body: { business_problem: string; scale_estimates?: Record<string,string>; constraints?: string[] }) =>
    request<AnalysisSummary>('/analyze', { method: 'POST', body: JSON.stringify(body) }),

  /** Returns a raw EventSource-ready URL for the SSE stream */
  streamUrl: () => `${API_V1}/analyze/stream`,
};

// ── Projects ──────────────────────────────────────────────

export interface Project {
  id: string; name: string; description?: string; tags: string[];
  visibility: string; analysis_ids: string[]; created_at: string; updated_at: string;
}

export const projectsApi = {
  list:   (skip = 0, limit = 20) => request<Project[]>(`/projects?skip=${skip}&limit=${limit}`),
  get:    (id: string)            => request<Project>(`/projects/${id}`),
  create: (body: { name: string; description?: string; tags?: string[]; visibility?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: Partial<Project>) =>
    request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
};
