// src/pages/NewAnalysisPage.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, ArrowLeft, Loader2, CheckCircle, AlertCircle, ChevronRight, Settings, Users, Database, Server, Shield, Zap as ZapIcon, GitBranch, FileText } from 'lucide-react';
import { analyzeApi, AnalysisDetail } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './NewAnalysisPage.css';

const STEPS = [
  { id: 'init', label: 'Initializing', icon: Zap },
  { id: 'requirements', label: 'Requirements', icon: FileText },
  { id: 'architecture', label: 'Architecture', icon: GitBranch },
  { id: 'database', label: 'Database', icon: Database },
  { id: 'api', label: 'API Spec', icon: Server },
  { id: 'deployment', label: 'Deployment', icon: Shield },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'performance', label: 'Performance', icon: ZapIcon },
  { id: 'diagrams', label: 'Diagrams', icon: GitBranch },
  { id: 'done', label: 'Complete', icon: CheckCircle },
];

const STEP_ORDER = STEPS.map(s => s.id);

export default function NewAnalysisPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [businessProblem, setBusinessProblem] = useState('');
  const [scaleEstimates, setScaleEstimates] = useState({ users: '', daily_requests: '', budget: '' });
  const [constraints, setConstraints] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string>('init');
  const [stepStatus, setStepStatus] = useState<Record<string, 'pending' | 'active' | 'done' | 'error'>>({});
  const [events, setEvents] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  const resetForm = useCallback(() => {
    setBusinessProblem('');
    setScaleEstimates({ users: '', daily_requests: '', budget: '' });
    setConstraints('');
    setLoading(false);
    setError('');
    setAnalysisId(null);
    setCurrentStep('init');
    setStepStatus({});
    setEvents([]);
    setCompleted(false);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const updateStepStatus = (stepId: string, status: 'pending' | 'active' | 'done' | 'error') => {
    setStepStatus(prev => ({ ...prev, [stepId]: status }));
    if (status === 'active') setCurrentStep(stepId);
  };

  const startAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!businessProblem.trim()) { setError('Please describe your business problem'); return; }
    setLoading(true);
    setError('');
    resetForm();

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/v1/analyze/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          business_problem: businessProblem,
          scale_estimates: scaleEstimates,
          constraints: constraints.split(',').map(s => s.trim()).filter(Boolean),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Failed to start analysis' }));
        throw new Error(err.detail || 'Failed to start analysis');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += new TextDecoder().decode(value);
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (!data) continue;
            try {
              const parsed = JSON.parse(data);
              handleStreamEvent(parsed);
            } catch {
              setEvents(prev => [...prev, data]);
            }
          }
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis');
      setLoading(false);
    }
  };

  const handleStreamEvent = (event: any) => {
    setEvents(prev => [...prev, JSON.stringify(event)]);
    const step = event.step;
    const message = event.message;

    if (step === 'init') {
      updateStepStatus('init', 'active');
    } else if (step === 'done') {
      if (event.analysis_id) setAnalysisId(event.analysis_id);
      STEP_ORDER.forEach((s, i) => updateStepStatus(s, i < STEP_ORDER.length - 1 ? 'done' : 'active'));
      setCompleted(true);
      setLoading(false);
      setTimeout(() => {
        if (event.analysis_id) navigate(`/analyses/${event.analysis_id}`);
      }, 1500);
    } else if (step === 'error') {
      updateStepStatus(step, 'error');
      setError(message);
      setLoading(false);
    } else {
      const idx = STEP_ORDER.indexOf(step);
      if (idx >= 0) {
        STEP_ORDER.slice(0, idx + 1).forEach(s => updateStepStatus(s, s === step ? 'active' : 'done'));
      }
    }
  };

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="new-analysis-page">
      <div className="page-header fade-in">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dashboard')}>
          <ArrowLeft size={16} /> Back to Dashboard
        </button>
        <div>
          <h1>New Architecture Analysis</h1>
          <p className="text-secondary text-sm">Describe your business problem and let 8 AI agents design your system</p>
        </div>
      </div>

      <div className="grid-2 fade-in">
        {/* Left: Form / Progress */}
        <div className="card">
          {!completed ? (
            <form onSubmit={startAnalysis} className="analysis-form">
              <div className="form-group">
                <label className="form-label">Business Problem <span className="required">*</span></label>
                <textarea
                  className="input textarea"
                  placeholder="e.g., Build a scalable e-commerce platform for 100K daily active users with real-time inventory, payment processing, and multi-region deployment..."
                  value={businessProblem}
                  onChange={e => setBusinessProblem(e.target.value)}
                  rows={5}
                  required
                  disabled={loading}
                />
                <p className="form-hint">Be specific about your domain, scale, and key challenges. The more detail, the better the architecture.</p>
              </div>

              <div className="scale-section">
                <h4 className="scale-title">Scale Estimates (Optional)</h4>
                <div className="scale-grid">
                  <div className="form-group">
                    <label className="form-label">Concurrent Users</label>
                    <input className="input" placeholder="10,000" value={scaleEstimates.users} onChange={e => setScaleEstimates({...scaleEstimates, users: e.target.value})} disabled={loading} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Daily Requests</label>
                    <input className="input" placeholder="1,000,000" value={scaleEstimates.daily_requests} onChange={e => setScaleEstimates({...scaleEstimates, daily_requests: e.target.value})} disabled={loading} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Monthly Budget</label>
                    <input className="input" placeholder="$5,000" value={scaleEstimates.budget} onChange={e => setScaleEstimates({...scaleEstimates, budget: e.target.value})} disabled={loading} />
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Constraints (comma-separated)</label>
                <input
                  className="input"
                  placeholder="e.g., HIPAA compliance, multi-region, vendor lock-in avoidance"
                  value={constraints}
                  onChange={e => setConstraints(e.target.value)}
                  disabled={loading}
                />
                <p className="form-hint">Regulatory, technical, or organizational constraints the agents should consider.</p>
              </div>

              {error && <div className="auth-error"><AlertCircle size={14} /> {error}</div>}

              <button type="submit" className="btn btn-primary btn-lg w-full" disabled={loading || !businessProblem.trim()}>
                {loading ? <Loader2 size={18} className="spin" /> : <>Generate Architecture <Zap size={16} /></>}
              </button>
            </form>
          ) : (
            <div className="success-state">
              <div className="success-icon"><CheckCircle size={48} /></div>
              <h3>Analysis Complete!</h3>
              <p>Your architecture blueprint has been generated in {stepStatus.done ? '~8s' : 'progress'}.</p>
              <button className="btn btn-primary" onClick={() => analysisId && navigate(`/analyses/${analysisId}`)}>
                View Full Report <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Right: Agent Progress */}
        <div className="card progress-panel">
          <div className="progress-header">
            <h3>Agent Collaboration</h3>
            {loading && <span className="live-badge"><span className="dot dot-pulse dot-success" /> Live</span>}
          </div>

          <div className="steps-timeline">
            {STEPS.map((step, idx) => {
              const status = stepStatus[step.id] || 'pending';
              const Icon = step.icon;
              return (
                <div key={step.id} className={`step-item ${status}`}>
                  <div className="step-marker">
                    <div className={`step-dot ${status}`}>
                      {status === 'done' && <CheckCircle size={12} />}
                      {status === 'active' && <Loader2 size={12} className="spin" />}
                      {status === 'error' && <AlertCircle size={12} />}
                      {status === 'pending' && <Icon size={12} />}
                    </div>
                    <div className="step-line" />
                  </div>
                  <div className="step-content">
                    <div className="step-label">{step.label}</div>
                    <div className="step-message">
                      {status === 'active' && 'Working...'}
                      {status === 'done' && 'Complete'}
                      {status === 'error' && 'Failed'}
                      {status === 'pending' && 'Waiting...'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="logs-panel" ref={logsRef}>
            {events.map((e, i) => (
              <div key={i} className="log-line">
                <span className="log-time">[{new Date().toLocaleTimeString()}]</span>
                <span className="log-message">{e}</span>
              </div>
            ))}
            {!loading && events.length === 0 && (
              <div className="log-empty">Agent logs will appear here during analysis...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function handleStreamEvent(event: any) {
  // placeholder - actual handler inside component
}