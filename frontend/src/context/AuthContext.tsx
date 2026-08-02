// src/context/AuthContext.tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authApi, type UserProfile, type AuthPayload } from '../api/client';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  refreshToken: string | null;
  loading: boolean;
  login: (payload: AuthPayload) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('mosaic_token');
    const storedRefresh = localStorage.getItem('mosaic_refresh_token');
    if (stored) {
      setToken(stored);
      setRefreshToken(storedRefresh);
      authApi.me()
        .then(setUser)
        .catch(async () => {
          // Try refresh token if access token expired
          if (storedRefresh) {
            try {
              const payload = await authApi.refresh(storedRefresh);
              login(payload);
            } catch {
              localStorage.removeItem('mosaic_token');
              localStorage.removeItem('mosaic_refresh_token');
              localStorage.removeItem('mosaic_user');
            }
          } else {
            localStorage.removeItem('mosaic_token');
            localStorage.removeItem('mosaic_refresh_token');
            localStorage.removeItem('mosaic_user');
          }
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  function login(payload: AuthPayload) {
    localStorage.setItem('mosaic_token', payload.access_token);
    localStorage.setItem('mosaic_refresh_token', payload.refresh_token);
    setToken(payload.access_token);
    setRefreshToken(payload.refresh_token);
    setUser({
      user_id: payload.user_id,
      name: payload.name,
      email: payload.email,
      plan: payload.plan,
    });
  }

  async function logout() {
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Ignore logout API errors
      }
    }
    localStorage.removeItem('mosaic_token');
    localStorage.removeItem('mosaic_refresh_token');
    localStorage.removeItem('mosaic_user');
    setToken(null);
    setRefreshToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, refreshToken, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() { return useContext(AuthContext); }
