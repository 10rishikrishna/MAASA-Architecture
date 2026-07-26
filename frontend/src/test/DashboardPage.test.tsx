import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test User', email: 'test@test.com', plan: 'pro' }));

vi.mock('../api/client', () => ({
  authApi: {
    me: vi.fn().mockResolvedValue(mockUser),
    login: vi.fn(),
    register: vi.fn(),
  },
  analyzeApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}));

import { analyzeApi } from '../api/client';

function renderDashboard() {
  localStorage.setItem('maasa_token', 'test-token');
  localStorage.setItem('maasa_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('DashboardPage', () => {
  it('renders welcome message', async () => {
    (analyzeApi.list as any).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
    });
  });

  it('displays stats cards', async () => {
    (analyzeApi.list as any).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('Total Analyses')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('Processing')).toBeInTheDocument();
    });
  });

  it('shows empty state when no analyses', async () => {
    (analyzeApi.list as any).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('No analyses yet')).toBeInTheDocument();
    });
  });

  it('renders analyses list when data exists', async () => {
    (analyzeApi.list as any).mockResolvedValue([
      { id: 'a1', business_problem: 'Build an e-commerce platform', status: 'completed', analysis_time_seconds: 5.2, created_at: '2025-01-01T00:00:00Z' },
      { id: 'a2', business_problem: 'Design a chat system', status: 'processing', analysis_time_seconds: null, created_at: '2025-01-02T00:00:00Z' },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('Build an e-commerce platform')).toBeInTheDocument();
      expect(screen.getByText('Design a chat system')).toBeInTheDocument();
    });
  });

  it('has New Analysis button', async () => {
    (analyzeApi.list as any).mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('New Analysis')).toBeInTheDocument();
    });
  });
});
