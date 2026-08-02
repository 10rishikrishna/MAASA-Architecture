import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test User', email: 't@t.com', plan: 'pro' }));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
}));

describe('Sidebar', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    localStorage.setItem('mosaic_token', 'test-token');
    localStorage.setItem('mosaic_user', JSON.stringify(mockUser));
  });

  it('renders Mosaic Studio branding', async () => {
    const { authApi } = await import('../api/client');
    (authApi.me as any).mockResolvedValue(mockUser);

    render(
      <MemoryRouter>
        <AuthProvider><Sidebar /></AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByText('Mosaic Studio')).toBeInTheDocument();
  });

  it('renders navigation links', async () => {
    const { authApi } = await import('../api/client');
    (authApi.me as any).mockResolvedValue(mockUser);

    render(
      <MemoryRouter>
        <AuthProvider><Sidebar /></AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('New Analysis')).toBeInTheDocument();
    expect(screen.getByText('Analyses')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('Teams')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('shows user name', async () => {
    const { authApi } = await import('../api/client');
    (authApi.me as any).mockResolvedValue(mockUser);

    render(
      <MemoryRouter>
        <AuthProvider><Sidebar /></AuthProvider>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
  });

  it('renders logout button', async () => {
    const { authApi } = await import('../api/client');
    (authApi.me as any).mockResolvedValue(mockUser);

    render(
      <MemoryRouter>
        <AuthProvider><Sidebar /></AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });
});
