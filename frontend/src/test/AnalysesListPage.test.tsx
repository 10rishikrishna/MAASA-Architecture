import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AnalysesListPage from '../pages/AnalysesListPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test User', email: 'test@test.com', plan: 'free' }));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
  analyzeApi: {
    list: vi.fn().mockResolvedValue([]),
    delete: vi.fn(),
  },
}));

import { analyzeApi } from '../api/client';

function renderList() {
  localStorage.setItem('mosaic_token', 'test-token');
  localStorage.setItem('mosaic_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={['/analyses']}>
      <AuthProvider>
        <AnalysesListPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('AnalysesListPage', () => {
  it('renders page title', async () => {
    renderList();
    expect(screen.getByText('All Analyses')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    renderList();
    expect(screen.getByText('Loading analyses...')).toBeInTheDocument();
  });

  it('shows empty state when no analyses', async () => {
    (analyzeApi.list as any).mockResolvedValue([]);
    renderList();
    await waitFor(() => {
      expect(screen.getByText('No analyses found')).toBeInTheDocument();
    });
  });

  it('renders analyses when data exists', async () => {
    (analyzeApi.list as any).mockResolvedValue([
      { id: 'a1', business_problem: 'E-commerce platform', status: 'completed', analysis_time_seconds: 5.2, created_at: '2025-01-01T00:00:00Z' },
    ]);
    renderList();
    await waitFor(() => {
      expect(screen.getByText('E-commerce platform')).toBeInTheDocument();
    });
  });

  it('search input works', async () => {
    (analyzeApi.list as any).mockResolvedValue([
      { id: 'a1', business_problem: 'E-commerce', status: 'completed', analysis_time_seconds: 1, created_at: '2025-01-01' },
      { id: 'a2', business_problem: 'Chat app', status: 'completed', analysis_time_seconds: 1, created_at: '2025-01-01' },
    ]);
    renderList();
    await waitFor(() => expect(screen.getByText('E-commerce')).toBeInTheDocument());

    const searchInput = screen.getByPlaceholderText(/search by business problem/i);
    fireEvent.change(searchInput, { target: { value: 'chat' } });

    expect(screen.queryByText('E-commerce')).not.toBeInTheDocument();
    expect(screen.getByText('Chat app')).toBeInTheDocument();
  });
});
