import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SettingsPage from '../pages/SettingsPage';
import { AuthProvider } from '../context/AuthContext';

const mockUser = vi.hoisted(() => ({ user_id: '1', name: 'Test User', email: 'test@test.com', plan: 'pro' }));

vi.mock('../api/client', () => ({
  authApi: {
    me: vi.fn().mockResolvedValue(mockUser),
    updateProfile: vi.fn().mockResolvedValue(mockUser),
    changePassword: vi.fn().mockResolvedValue({ success: true }),
  },
  apiKeysApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: 'k1', name: 'test-key', key_preview: 'mosaic_123...', full_key: 'mosaic_abc123',
      created_at: '2025-01-01', expires_at: null, last_used_at: null,
    }),
    revoke: vi.fn(),
  },
}));

import { authApi } from '../api/client';

function renderSettings() {
  localStorage.setItem('mosaic_token', 'test-token');
  localStorage.setItem('mosaic_user', JSON.stringify(mockUser));
  return render(
    <MemoryRouter initialEntries={['/settings']}>
      <AuthProvider><SettingsPage /></AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('SettingsPage', () => {
  it('renders settings title', async () => {
    renderSettings();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('displays profile section', async () => {
    renderSettings();
    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Change Password' })).toBeInTheDocument();
    expect(screen.getByText('API Keys')).toBeInTheDocument();
  });

  it('shows user name in input', async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test User')).toBeInTheDocument();
    });
  });

  it('saves profile changes', async () => {
    renderSettings();
    await waitFor(() => expect(screen.getByDisplayValue('Test User')).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue('Test User'), { target: { value: 'New Name' } });
    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => {
      expect(authApi.updateProfile).toHaveBeenCalledWith({ name: 'New Name' });
    });
  });

  it('shows API key creation form', async () => {
    renderSettings();
    expect(screen.getByPlaceholderText(/key name/i)).toBeInTheDocument();
  });
});
