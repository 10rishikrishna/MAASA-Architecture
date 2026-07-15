// src/pages/DashboardPage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Clock, CheckCircle, XCircle, ArrowRight, BarChart2, FolderOpen } from 'lucide-react';
import { analyzeApi, AnalysisSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './DashboardPage.css';

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed') return <span className="badge badge-success"><CheckCircle size={10} /> Completed</span>;
  if (status === 'failed')    return <span className="badge badge-danger"><XCircle size={10} /> Failed</span>;
  return <span className="badge badge-warning"><div className="dot dot-pulse dot-warning" /> Processing</span>;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate  = useNavigate();
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    analyzeApi.list(0, 10)
      .then(setAnalyses)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const completed  = analyses.filter(a => a.status === 'completed').length;
  const processing = analyses.filter(a => a.status === 'processing').length;

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header dash-header">
        <div>
          <h1>Welcome back, <span className="text-gradient">{user?.name?.split(' ')[0]}</span> 👋</h1>
          <p className="text-secondary text-sm">Your AI architecture workspace is ready.</p>
        </div>
        <button id="new-analysis-btn" className="btn btn-primary btn-lg" onClick={() => navigate('/analyze/new')}>
          <Zap size={18} /> New Analysis
        </button>
      </div>

      {/* Stats */}
      <div className="grid-4" style={{ marginBottom:'2rem' }}>
        <StatCard icon={<BarChart2 size={22} />} label="Total Analyses" value={analyses.length} color="accent" />
        <StatCard icon={<CheckCircle size={22} />} label="Completed"    value={completed}        color="success" />
        <StatCard icon={<Clock size={22} />}       label="Processing"   value={processing}       color="warning" />
        <StatCard icon={<FolderOpen size={22} />}  label="Plan"         value={user?.plan ?? 'free'} color="info" isText />
      </div>

      {/* Recent Analyses */}
      <div className="card">
        <div className="flex items-center justify-between" style={{ marginBottom:'1.25rem' }}>
          <h2 className="text-lg" style={{ fontWeight:600 }}>Recent Analyses</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/analyses')}>
            View all <ArrowRight size={14} />
          </button>
        </div>

        {loading ? (
          <div style={{ display:'flex', justifyContent:'center', padding:'2rem' }}>
            <div className="spinner" style={{ width:32, height:32 }} />
          </div>
        ) : analyses.length === 0 ? (
          <EmptyState onNew={() => navigate('/analyze/new')} />
        ) : (
          <div className="analysis-list">
            {analyses.map(a => (
              <div key={a.id} className="analysis-row" onClick={() => navigate(`/analyses/${a.id}`)}>
                <div className="analysis-row-left">
                  <div className="analysis-icon"><Zap size={16} /></div>
                  <div>
                    <div className="analysis-title">{a.business_problem.slice(0, 80)}{a.business_problem.length > 80 ? '…' : ''}</div>
                    <div className="text-xs text-muted">{new Date(a.created_at).toLocaleDateString()}{a.analysis_time_seconds ? ` • ${a.analysis_time_seconds}s` : ''}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={a.status} />
                  <ArrowRight size={14} className="text-muted" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color, isText }: any) {
  return (
    <div className={`card stat-card stat-card--${color}`}>
      <div className={`stat-icon stat-icon--${color}`}>{icon}</div>
      <div className="stat-value">{isText ? <span className="badge badge-accent">{value}</span> : value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Zap size={32} /></div>
      <h3>No analyses yet</h3>
      <p className="text-secondary text-sm">Describe a business problem and let the AI agents design your architecture.</p>
      <button className="btn btn-primary" onClick={onNew}><Zap size={16} /> Start First Analysis</button>
    </div>
  );
}
