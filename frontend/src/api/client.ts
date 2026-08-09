// src/api/client.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const API_V1  = `${API_URL}/api/v1`;

function getToken(): string | null {
  return localStorage.getItem('mosaic_token');
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token
    ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_V1}${path}`, {
      ...options,
      headers: { ...authHeaders(), ...options?.headers },
    });
  } catch (e) {
    throw new Error('Unable to connect to the server. Please ensure the backend is running at ' + API_URL);
  }

  if (res.status === 401) {
    localStorage.removeItem('mosaic_token');
    localStorage.removeItem('mosaic_user');
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

export interface AuthPayload { access_token: string; refresh_token: string; user_id: string; name: string; email: string; plan: string; }
export interface UserProfile  { user_id: string; email: string; name: string; plan: string; profile_picture_url?: string; }

export const authApi = {
  register: (email: string, password: string, name: string) =>
    request<AuthPayload>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, name }) }),

  login: (email: string, password: string) =>
    request<AuthPayload>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  refresh: (refresh_token: string) =>
    request<AuthPayload>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token }) }),

  logout: (refresh_token: string) =>
    request<{ success: boolean }>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token }) }),

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

// ── Canonical architecture model ──────────────────────────

export interface Workload {
  avg_requests_per_second?: number | null;
  peak_requests_per_second?: number | null;
  expected_concurrency?: number | null;
  users?: number | null;
  read_write_ratio?: string;
  assumptions?: Array<{ label?: string; text?: string } | string>;
  calculated_from?: string;
  complexity_score?: number;
}

export interface ArchitectureComponent {
  id?: string;
  name: string;
  type: string;
  technology?: string;
  responsibility?: string;
  internal_or_external?: string;
  dependencies?: string[];
  scaling_strategy?: string;
  failure_behavior?: string;
  security_considerations?: string;
  alternatives?: string[];
  reason?: string;
}

export interface Decision {
  decision?: string; reason?: string; alternatives?: string[];
  rejected_alternatives?: string[]; rejected_reason?: string; tradeoff?: string; confidence?: number;
}

export interface Ambiguity {
  question?: string; suggested_assumption?: string; confidence?: string; impact?: string;
}

export interface DiagramLevel {
  title?: string; description?: string; mermaid?: string; ascii?: string;
  node_map?: Record<string, string>;
}

export interface ArchitectureAlternative {
  key: string;
  name: string;
  recommended: boolean;
  description: string;
  flow: string[];
  components: Array<{ name: string; type: string; technology: string; responsibility: string }>;
  pros: string[];
  cons: string[];
  when_to_use: string;
}

export interface ArchitectureModel {
  version?: number;
  business_problem?: string;
  domain?: string;
  architecture_tier?: string;
  status?: string;
  correction_iterations?: number;
  overview?: string;
  overview_explained?: Array<{ key: string; title: string; icon?: string; paragraphs: string[] }>;
  requirements?: {
    functional?: any[]; non_functional?: any[]; actors?: string[]; constraints?: any[];
    assumptions?: any[]; ambiguities?: Ambiguity[]; business_rules?: any[];
    dependencies?: any[]; scale_requirements?: Record<string, any>;
    availability_requirement?: string; security_requirements?: any[];
  };
  architecture?: {
    system_type?: string; style?: string; pattern?: string; justification?: string;
    components?: ArchitectureComponent[]; relationships?: any[]; technologies?: any[];
    decisions?: Decision[]; building_blocks?: string[];
    explanation_modes?: {
      story?: string; brief?: string; long?: string; detailed?: string;
      terms?: any[]; analogies?: any[];
    };
    alternatives?: ArchitectureAlternative[];
  };
  database?: Record<string, any>;
  api?: Record<string, any>;
  deployment?: Record<string, any>;
  security?: Record<string, any>;
  performance?: { workload?: Workload; [k: string]: any };
  failure_scenarios?: any[];
  risks?: any[];
  review?: {
    overall_score?: number | null; categories?: Record<string, number>;
    critical_issues?: string[]; warnings?: string[]; recommendations?: string[];
    missing_information?: string[];
  };
  diagrams?: {
    level1?: DiagramLevel; level2?: DiagramLevel; level3?: DiagramLevel; legacy?: { mermaid?: string; ascii?: string };
  };
  validation?: { issue_count?: number; issues?: Array<{ severity: string; category: string; message: string }> };
  analysis_time_seconds?: number;
}

export interface ValidationSummary {
  error_count: number; warning_count: number;
  errors: Array<{ severity: string; category: string; message: string }>;
  warnings: Array<{ severity: string; category: string; message: string }>;
  passes: boolean;
}

export interface AnalysisDetail extends AnalysisSummary {
  requirements?:          { functional: string[]; non_functional: string[] };
  architecture_design?:   { system_type: string; pattern: string; justification: string; components: any[]; story_mode?: string; eli5_terms?: { term: string; symbol: string; meaning: string; analogy: string }[]; explanations?: { brief: string; long: string; detailed: string; overview_explained?: Array<{ key: string; title: string; icon?: string; paragraphs: string[] }> }; alternatives?: ArchitectureAlternative[] };
  database_schema?:       { database_type: string; justification: string; schemas: any[]; indexing_strategies: string[] };
  api_specification?:     { protocol: string; endpoints: any[] };
  deployment_config?:     { infrastructure_as_code: string; orchestration: string; terraform_sample: string; kubernetes_manifest: string };
  security_audit?:        { vulnerability_mitigations: string[]; compliance: string; scores?: { security: number; scalability: number; cost: number } };
  performance_strategies?:{ caching: string; optimization: string };
  diagrams?:              { mermaid: string; ascii: string };
  architecture_model?:    ArchitectureModel;
}

export const analyzeApi = {
  list:   (skip = 0, limit = 20) => request<AnalysisSummary[]>(`/analyze?skip=${skip}&limit=${limit}`),
  get:    (id: string)            => request<AnalysisDetail>(`/analyze/${id}`),
  start:  (body: { business_problem: string; scale_estimates?: Record<string,string>; constraints?: string[] }) =>
    request<AnalysisSummary>('/analyze', { method: 'POST', body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/analyze/${id}`, { method: 'DELETE' }),
  validate: (id: string) => request<ValidationSummary>(`/analyze/${id}/validation`),

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
  role: string; content: string; timestamp: string; explanation_level?: string;
  modification_applied?: boolean; modified_sections?: string[];
}

export interface ChatResponse {
  response: string;
  follow_up_suggestions: string[];
  conversation_length: number;
  explanation_level: string;
  modification_applied?: boolean;
  modified_sections?: string[];
}

export const chatApi = {
  send:    (analysisId: string, content: string, explanationLevel: string = 'brief') =>
    request<ChatResponse>(`/chat/${analysisId}/send`, {
      method: 'POST',
      body: JSON.stringify({ content, explanation_level: explanationLevel }),
    }),
  history: (analysisId: string) => request<{ messages: ChatMessage[] }>(`/chat/${analysisId}/history`),
  clear:   (analysisId: string) => request<{ success: boolean }>(`/chat/${analysisId}/clear`, { method: 'POST' }),
};
