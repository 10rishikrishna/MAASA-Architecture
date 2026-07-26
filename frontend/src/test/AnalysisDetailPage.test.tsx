import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AnalysisDetailPage from '../pages/AnalysisDetailPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test', email: 't@t.com', plan: 'free' }));

const mockAnalysis = vi.hoisted(() => ({
  id: 'a1',
  business_problem: 'Build an e-commerce platform',
  status: 'completed',
  analysis_time_seconds: 5.2,
  created_at: '2025-01-01T00:00:00Z',
  requirements: { functional: ['User auth', 'Payment'], non_functional: ['99.9% uptime'] },
  architecture_design: { system_type: 'Web', pattern: 'Microservices', justification: 'Scale', components: [{ name: 'API', description: 'REST API', technology: 'Node.js' }] },
  database_schema: { database_type: 'PostgreSQL', justification: 'ACID', schemas: [{ table_name: 'users', sql: 'CREATE TABLE users (id UUID PRIMARY KEY)' }], indexing_strategies: ['B-tree on email'] },
  api_specification: { protocol: 'REST', endpoints: [{ method: 'GET', path: '/api/users', description: 'List users' }] },
  deployment_config: { infrastructure_as_code: 'Terraform', orchestration: 'Kubernetes', terraform_sample: 'resource "aws_instance" {}', kubernetes_manifest: 'apiVersion: v1' },
  security_audit: { vulnerability_mitigations: ['Input validation'], compliance: 'SOC2' },
  performance_strategies: { caching: 'Redis', optimization: 'CDN' },
  diagrams: { mermaid: 'graph TD; A-->B', ascii: 'A --> B' },
}));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
  analyzeApi: {
    get: vi.fn().mockResolvedValue(mockAnalysis),
    delete: vi.fn(),
    exportUrl: vi.fn().mockReturnValue('http://test/export'),
  },
  chatApi: {
    history: vi.fn().mockResolvedValue({ messages: [] }),
    send: vi.fn(),
    clear: vi.fn(),
  },
}));

import { analyzeApi } from '../api/client';

function renderDetail(id = 'a1') {
  localStorage.setItem('maasa_token', 'test-token');
  localStorage.setItem('maasa_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={[`/analyses/${id}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/analyses/:id" element={<AnalysisDetailPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('AnalysisDetailPage', () => {
  it('shows loading state', () => {
    renderDetail();
    expect(screen.getByText('Loading analysis...')).toBeInTheDocument();
  });

  it('renders analysis details', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Build an e-commerce platform' })).toBeInTheDocument();
      expect(screen.getAllByText(/completed/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders tabs', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Requirements')).toBeInTheDocument();
      expect(screen.getByText('Architecture')).toBeInTheDocument();
      expect(screen.getByText('Database')).toBeInTheDocument();
      expect(screen.getByText('API Spec')).toBeInTheDocument();
      expect(screen.getByText('Chat')).toBeInTheDocument();
    });
  });

  it('shows mermaid diagram on overview', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('System Architecture Diagram')).toBeInTheDocument();
    });
  });

  it('shows error state for non-existent analysis', async () => {
    (analyzeApi.get as any).mockRejectedValue(new Error('Not found'));
    renderDetail('nonexistent');
    await waitFor(() => {
      expect(screen.getByText('Analysis not found')).toBeInTheDocument();
    });
  });
});
