import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AuthPage from '../pages/AuthPage';
import { AuthProvider } from '../context/AuthContext';

vi.mock('../api/client', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
}));

import { authApi } from '../api/client';

function renderWithProviders(ui: React.ReactElement, route = '/login') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('AuthPage', () => {
  it('renders login form by default', () => {
    renderWithProviders(<AuthPage />);
    expect(within(screen.getByRole('form', { name: /authentication/i })).getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/you@company\.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••••••/i)).toBeInTheDocument();
  });

  it('switches to register mode', () => {
    renderWithProviders(<AuthPage />);
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByPlaceholderText(/john smith/i)).toBeInTheDocument();
  });

  it('calls login API on submit', async () => {
    (authApi.login as any).mockResolvedValue({
      access_token: 'tok', user_id: '1', name: 'U', email: 'u@e.com', plan: 'free',
    });
    renderWithProviders(<AuthPage />);

    fireEvent.change(screen.getByPlaceholderText(/you@company\.com/i), { target: { value: 'test@test.com' } });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/i), { target: { value: 'pass123' } });
    fireEvent.click(within(screen.getByRole('form', { name: /authentication/i })).getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith('test@test.com', 'pass123');
    });
  });

  it('displays error message on failed login', async () => {
    (authApi.login as any).mockRejectedValue(new Error('Invalid credentials'));
    renderWithProviders(<AuthPage />);

    fireEvent.change(screen.getByPlaceholderText(/you@company\.com/i), { target: { value: 'bad@test.com' } });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/i), { target: { value: 'wrong' } });
    fireEvent.click(within(screen.getByRole('form', { name: /authentication/i })).getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });
});
