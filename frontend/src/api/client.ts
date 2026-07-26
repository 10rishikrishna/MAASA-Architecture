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

  updateProfile: (data: { name?: string; profile_picture_url?: string }) =>
    request<UserProfile>('/auth/me', { method: 'PATCH', body: JSON.stringify(data) }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ success: boolean }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
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
  delete: (id: string) => request<void>(`/analyze/${id}`, { method: 'DELETE' }),

  exportUrl: (id: string, format: 'markdown' | 'json' = 'markdown') =>
    `${API_V1}/analyze/${id}/export?format=${format}`,

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

// ── Project Sharing ───────────────────────────────────────

export interface Share {
  id: string; project_id: string; shared_with_email: string; permission: string; created_at: string;
}

export const sharesApi = {
  list:   (projectId: string) => request<Share[]>(`/projects/${projectId}/shares`),
  create: (projectId: string, body: { email: string; permission?: string }) =>
    request<Share>(`/projects/${projectId}/shares`, { method: 'POST', body: JSON.stringify(body) }),
  update: (projectId: string, shareId: string, body: { permission: string }) =>
    request<Share>(`/projects/${projectId}/shares/${shareId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  revoke: (projectId: string, shareId: string) =>
    request<void>(`/projects/${projectId}/shares/${shareId}`, { method: 'DELETE' }),
};

// ── Teams ─────────────────────────────────────────────────

export interface Team {
  id: string; name: string; description?: string; owner_id: string;
  member_count: number; created_at: string; updated_at: string;
}

export interface TeamMember {
  id: string; user_id: string; email: string; name: string; role: string; joined_at: string;
}

export interface TeamDetail extends Team {
  members: TeamMember[];
}

export const teamsApi = {
  list:   () => request<Team[]>('/teams'),
  get:    (id: string) => request<TeamDetail>(`/teams/${id}`),
  create: (body: { name: string; description?: string }) =>
    request<Team>('/teams', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: { name?: string; description?: string }) =>
    request<Team>(`/teams/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/teams/${id}`, { method: 'DELETE' }),
  addMember:    (teamId: string, body: { email: string; role?: string }) =>
    request<TeamMember>(`/teams/${teamId}/members`, { method: 'POST', body: JSON.stringify(body) }),
  updateMember: (teamId: string, userId: string, body: { role: string }) =>
    request<TeamMember>(`/teams/${teamId}/members/${userId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  removeMember: (teamId: string, userId: string) =>
    request<void>(`/teams/${teamId}/members/${userId}`, { method: 'DELETE' }),
};

// ── API Keys ──────────────────────────────────────────────

export interface ApiKey {
  id: string; name: string; key_preview: string;
  created_at: string; expires_at: string | null; last_used_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  full_key: string;
}

export const apiKeysApi = {
  list:    () => request<ApiKey[]>('/api-keys'),
  create:  (body: { name: string }) => request<ApiKeyCreated>('/api-keys', { method: 'POST', body: JSON.stringify(body) }),
  revoke:  (id: string) => request<void>(`/api-keys/${id}`, { method: 'DELETE' }),
};

// ── Audit Logs ────────────────────────────────────────────

export interface AuditLog {
  id: string; user_id: string | null; action: string;
  resource_type: string | null; resource_id: string | null;
  details: Record<string, any> | null; ip_address: string | null; created_at: string;
}

export const auditApi = {
  list: (skip = 0, limit = 50, action?: string) =>
    request<AuditLog[]>(`/audit-logs?skip=${skip}&limit=${limit}${action ? `&action=${action}` : ''}`),
};

// ── Chat ──────────────────────────────────────────────────

export interface ChatMessage {
  role: string; content: string; timestamp: string;
}

export interface ChatResponse {
  response: string;
  follow_up_suggestions: string[];
  conversation_length: number;
}

export const chatApi = {
  send:    (analysisId: string, content: string) =>
    request<ChatResponse>(`/chat/${analysisId}/send`, { method: 'POST', body: JSON.stringify({ content }) }),
  history: (analysisId: string) => request<{ messages: ChatMessage[] }>(`/chat/${analysisId}/history`),
  clear:   (analysisId: string) => request<{ success: boolean }>(`/chat/${analysisId}/clear`, { method: 'POST' }),
};
