// src/pages/AnalysesListPage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, ChevronDown, ChevronRight, CheckCircle, XCircle, Clock, Zap, MoreVertical } from 'lucide-react';
import { analyzeApi, AnalysisSummary } from '../api/client';
import './AnalysesListPage.css';

export default function AnalysesListPage() {
  const navigate = useNavigate();
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [filtered, setFiltered] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showFilter, setShowFilter] = useState(false);

  useEffect(() => {
    loadAnalyses();
  }, []);

  useEffect(() => {
    let result = analyses;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(a => a.business_problem.toLowerCase().includes(q));
    }
    if (statusFilter !== 'all') {
      result = result.filter(a => a.status === statusFilter);
    }
    setFiltered(result);
  }, [analyses, search, statusFilter]);

  async function loadAnalyses() {
    try {
      const data = await analyzeApi.list(0, 100);
      setAnalyses(data);
    } catch (err) {
      console.error('Failed to load analyses', err);
    } finally {
      setLoading(false);
    }
  }

  function getStatusBadge(status: string) {
    if (status === 'completed') return <span className="badge badge-success"><CheckCircle size={10} /> Completed</span>;
    if (status === 'failed') return <span className="badge badge-danger"><XCircle size={10} /> Failed</span>;
    return <span className="badge badge-warning"><Clock size={10} className="dot dot-pulse dot-warning" /> Processing</span>;
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  return (
    <div className="analyses-page">
      <div className="page-header">
        <div>
          <h1>All Analyses</h1>
          <p className="text-secondary text-sm">{analyses.length} total analyses</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/analyze/new')}>
          <Zap size={16} /> New Analysis
        </button>
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by business problem..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input"
          />
        </div>
        <div className="filter-group">
          <button className="btn btn-ghost" onClick={() => setShowFilter(!showFilter)}>
            <Filter size={16} /> Filters
            <ChevronDown size={14} />
          </button>
          {showFilter && (
            <div className="filter-dropdown">
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="input input-sm">
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner" style={{ width: 40, height: 40 }} />
          <p>Loading analyses...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <Zap size={48} />
          <h3>No analyses found</h3>
          <p className="text-secondary">{search || statusFilter !== 'all' ? 'Try adjusting your filters' : 'Create your first architecture analysis'}</p>
          {(!search && statusFilter === 'all') && <button className="btn btn-primary" onClick={() => navigate('/analyze/new')}>Create Analysis</button>}
        </div>
      ) : (
        <div className="analyses-table">
          <div className="table-header">
            <span>Analysis</span>
            <span>Status</span>
            <span>Created</span>
            <span>Duration</span>
            <span></span>
          </div>
          {filtered.map(a => (
            <div key={a.id} className="table-row" onClick={() => navigate(`/analyses/${a.id}`)}>
              <div className="col-problem">
                <div className="analysis-icon"><Zap size={16} /></div>
                <div>
                  <div className="problem-text">{a.business_problem.slice(0, 120)}{a.business_problem.length > 120 ? '…' : ''}</div>
                  <div className="problem-id">{a.id.slice(0, 8)}</div>
                </div>
              </div>
              <div className="col-status">{getStatusBadge(a.status)}</div>
              <div className="col-date">{formatDate(a.created_at)}</div>
              <div className="col-duration">{a.analysis_time_seconds ? `${a.analysis_time_seconds.toFixed(1)}s` : '—'}</div>
              <div className="col-actions">
                <MoreVertical size={16} className="text-muted" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}