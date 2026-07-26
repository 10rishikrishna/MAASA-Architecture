// src/pages/AnalysesListPage.tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, ChevronDown, CheckCircle, XCircle, Clock, Zap, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import { analyzeApi, type AnalysisSummary } from '../api/client';
import './AnalysesListPage.css';

const PAGE_SIZE = 10;

export default function AnalysesListPage() {
  const navigate = useNavigate();
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showFilter, setShowFilter] = useState(false);
  const [page, setPage] = useState(0);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => { loadAnalyses(); }, []);

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function loadAnalyses() {
    try {
      const data = await analyzeApi.list(0, 200);
      setAnalyses(data);
    } catch (err) {
      console.error('Failed to load analyses', err);
    } finally {
      setLoading(false);
    }
  }

  const filtered = analyses.filter(a => {
    const matchSearch = !search || a.business_problem.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'all' || a.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (!confirm('Delete this analysis?')) return;
    try {
      await analyzeApi.delete(id);
      setAnalyses(prev => prev.filter(a => a.id !== id));
      showToast('Analysis deleted');
    } catch (_err) {
      showToast('Failed to delete', 'error');
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
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={14} /> : <XCircle size={14} />}
          {toast.message}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1>All Analyses</h1>
          <p className="text-secondary text-sm">{filtered.length} analyses{search || statusFilter !== 'all' ? ' (filtered)' : ''}</p>
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
            onChange={e => { setSearch(e.target.value); setPage(0); }}
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
              <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(0); }} className="input input-sm">
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
        <>
          <div className="analyses-table">
            <div className="table-header">
              <span>Analysis</span>
              <span>Status</span>
              <span>Created</span>
              <span>Duration</span>
              <span></span>
            </div>
            {paginated.map(a => (
              <div key={a.id} className="table-row" onClick={() => navigate(`/analyses/${a.id}`)}>
                <div className="col-problem">
                  <div className="analysis-icon"><Zap size={16} /></div>
                  <div>
                    <div className="problem-text">{a.business_problem.slice(0, 120)}{a.business_problem.length > 120 ? '...' : ''}</div>
                    <div className="problem-id">{a.id.slice(0, 8)}</div>
                  </div>
                </div>
                <div className="col-status">{getStatusBadge(a.status)}</div>
                <div className="col-date">{formatDate(a.created_at)}</div>
                <div className="col-duration">{a.analysis_time_seconds ? `${a.analysis_time_seconds.toFixed(1)}s` : '—'}</div>
                <div className="col-actions">
                  <button className="icon-btn-sm" onClick={e => handleDelete(e, a.id)} title="Delete">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
                <ChevronLeft size={14} /> Previous
              </button>
              <span className="text-sm text-secondary">
                Page {page + 1} of {totalPages}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
