// src/context/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, UserProfile, AuthPayload } from '../api/client';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login:  (payload: AuthPayload) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,    setUser]    = useState<UserProfile | null>(null);
  const [token,   setToken]   = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('maasa_token');
    if (stored) {
      setToken(stored);
      authApi.me()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('maasa_token');
          localStorage.removeItem('maasa_user');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  function login(payload: AuthPayload) {
    localStorage.setItem('maasa_token', payload.access_token);
    setToken(payload.access_token);
    setUser({
      user_id: payload.user_id,
      name:    payload.name,
      email:   payload.email,
      plan:    payload.plan,
    });
  }

  function logout() {
    localStorage.removeItem('maasa_token');
    localStorage.removeItem('maasa_user');
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() { return useContext(AuthContext); }
