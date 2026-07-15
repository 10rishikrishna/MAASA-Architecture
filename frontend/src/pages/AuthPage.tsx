// src/pages/AuthPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cpu, Mail, Lock, User, ArrowRight, AlertCircle } from 'lucide-react';
import { authApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './AuthPage.css';

export default function AuthPage() {
  const [mode,     setMode]     = useState<'login' | 'register'>('login');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [name,     setName]     = useState('');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const { login } = useAuth();
  const navigate  = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = mode === 'login'
        ? await authApi.login(email, password)
        : await authApi.register(email, password, name);
      login(payload);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      {/* Left Panel */}
      <div className="auth-left">
        <div className="auth-left-inner">
          <div className="auth-brand">
            <div className="auth-logo">M</div>
            <span>MAASA</span>
          </div>
          <h1 className="auth-tagline">
            Architecture Intelligence,<br />
            <span className="text-gradient">Automated by AI Agents</span>
          </h1>
          <p className="auth-sub">
            Describe any business problem and watch 8 specialized AI agents
            collaboratively design your entire system architecture in seconds.
          </p>
          <div className="auth-features">
            {['Requirements Analysis', 'Architecture Design', 'Database Schema', 'API Specification',
              'Deployment Config', 'Security Audit'].map(f => (
              <div key={f} className="auth-feature-chip">
                <div className="dot dot-success" />
                {f}
              </div>
            ))}
          </div>
        </div>

        {/* animated bg orbs */}
        <div className="orb orb1" />
        <div className="orb orb2" />
      </div>

      {/* Right Panel */}
      <div className="auth-right">
        <div className="auth-card card fade-in">
          <div className="tab-bar" style={{ marginBottom:'1.5rem' }}>
            <button className={`tab-btn ${mode==='login'?'active':''}`}    onClick={() => { setMode('login');    setError(''); }}>Sign In</button>
            <button className={`tab-btn ${mode==='register'?'active':''}`} onClick={() => { setMode('register'); setError(''); }}>Create Account</button>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {mode === 'register' && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <div className="input-icon-wrap">
                  <User size={16} className="input-icon" />
                  <input id="auth-name" className="input input-with-icon" placeholder="John Smith"
                    value={name} onChange={e => setName(e.target.value)} required />
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email</label>
              <div className="input-icon-wrap">
                <Mail size={16} className="input-icon" />
                <input id="auth-email" type="email" className="input input-with-icon" placeholder="you@company.com"
                  value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <div className="input-icon-wrap">
                <Lock size={16} className="input-icon" />
                <input id="auth-password" type="password" className="input input-with-icon" placeholder="••••••••"
                  value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
              </div>
            </div>

            {error && (
              <div className="auth-error">
                <AlertCircle size={14} />
                {error}
              </div>
            )}

            <button id="auth-submit" type="submit" className="btn btn-primary btn-lg w-full" disabled={loading}>
              {loading ? <div className="spinner" /> : (
                <>{mode === 'login' ? 'Sign In' : 'Create Account'} <ArrowRight size={16} /></>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
