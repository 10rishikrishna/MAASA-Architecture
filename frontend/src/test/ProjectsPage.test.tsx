import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProjectsPage from '../pages/ProjectsPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test', email: 't@t.com', plan: 'free' }));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
  projectsApi: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import { projectsApi } from '../api/client';

function renderProjects() {
  localStorage.setItem('maasa_token', 'test-token');
  localStorage.setItem('maasa_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={['/projects']}>
      <AuthProvider><ProjectsPage /></AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('ProjectsPage', () => {
  it('renders title', async () => {
    (projectsApi.list as any).mockResolvedValue([]);
    renderProjects();
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('shows empty state', async () => {
    (projectsApi.list as any).mockResolvedValue([]);
    renderProjects();
    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument();
    });
  });

  it('renders project cards', async () => {
    (projectsApi.list as any).mockResolvedValue([
      { id: 'p1', name: 'My Project', description: 'A test project', tags: ['python'], visibility: 'private', analysis_ids: ['a1'], created_at: '2025-01-01', updated_at: '2025-01-01' },
    ]);
    renderProjects();
    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument();
      expect(screen.getByText('A test project')).toBeInTheDocument();
    });
  });

  it('opens create modal', async () => {
    (projectsApi.list as any).mockResolvedValue([]);
    renderProjects();
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Create First Project'));
    expect(screen.getByRole('heading', { name: 'Create Project' })).toBeInTheDocument();
  });
});
