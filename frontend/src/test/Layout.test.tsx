import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../components/Layout';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test User', email: 't@t.com', plan: 'free' }));

vi.mock('../api/client', () => ({
  authApi: { me: vi.fn().mockResolvedValue(mockUser) },
}));

describe('Layout', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('redirects to login when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider><Layout /></AuthProvider>
      </MemoryRouter>
    );
    // Should redirect to /login
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
  });

  it('renders sidebar and outlet when authenticated', async () => {
    localStorage.setItem('mosaic_token', 'test-token');
    localStorage.setItem('mosaic_user', JSON.stringify(mockUser));
    const { authApi } = await import('../api/client');
    (authApi.me as any).mockResolvedValue(mockUser);

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider><Layout /></AuthProvider>
      </MemoryRouter>
    );
    // Layout should render sidebar with Mosaic Studio branding
    await waitFor(() => {
      expect(screen.getByText('Mosaic Studio')).toBeInTheDocument();
    });
  });
});
