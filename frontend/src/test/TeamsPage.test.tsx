import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TeamsPage from '../pages/TeamsPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test', email: 't@t.com', plan: 'free' }));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
  teamsApi: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
  },
}));

import { teamsApi } from '../api/client';

function renderTeams() {
  localStorage.setItem('mosaic_token', 'test-token');
  localStorage.setItem('mosaic_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={['/teams']}>
      <AuthProvider><TeamsPage /></AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('TeamsPage', () => {
  it('renders title', async () => {
    (teamsApi.list as any).mockResolvedValue([]);
    renderTeams();
    expect(screen.getByText('Teams')).toBeInTheDocument();
  });

  it('shows empty state', async () => {
    (teamsApi.list as any).mockResolvedValue([]);
    renderTeams();
    await waitFor(() => {
      expect(screen.getByText('No teams yet')).toBeInTheDocument();
    });
  });

  it('renders team cards', async () => {
    (teamsApi.list as any).mockResolvedValue([
      { id: 't1', name: 'Dev Team', description: 'Backend team', owner_id: '1', member_count: 3, created_at: '2025-01-01', updated_at: '2025-01-01' },
    ]);
    renderTeams();
    await waitFor(() => {
      expect(screen.getByText('Dev Team')).toBeInTheDocument();
      expect(screen.getByText('Backend team')).toBeInTheDocument();
    });
  });

  it('opens create modal', async () => {
    (teamsApi.list as any).mockResolvedValue([]);
    renderTeams();
    await waitFor(() => expect(screen.getByText('No teams yet')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Create First Team'));
    expect(screen.getByRole('heading', { name: 'Create Team' })).toBeInTheDocument();
  });
});
