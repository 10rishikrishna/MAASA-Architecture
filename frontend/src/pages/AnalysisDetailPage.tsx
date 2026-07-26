// src/pages/AnalysisDetailPage.tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, Download, CheckCircle, XCircle, Clock, Zap, FileText, Database, Server, Shield, GitBranch, Zap as ZapIcon, Trash2, Share2, MessageSquare } from 'lucide-react';
import { analyzeApi, type AnalysisDetail, chatApi, type ChatMessage } from '../api/client';
import { MermaidDiagram } from '../components/MermaidDiagram';
import './AnalysisDetailPage.css';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Zap },
  { id: 'requirements', label: 'Requirements', icon: FileText },
  { id: 'architecture', label: 'Architecture', icon: GitBranch },
  { id: 'database', label: 'Database', icon: Database },
  { id: 'api', label: 'API Spec', icon: Server },
  { id: 'deployment', label: 'Deployment', icon: Shield },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'performance', label: 'Performance', icon: ZapIcon },
  { id: 'diagrams', label: 'Diagrams', icon: GitBranch },
  { id: 'chat', label: 'Chat', icon: MessageSquare },
];

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed') return <span className="badge badge-success"><CheckCircle size={10} /> Completed</span>;
  if (status === 'failed') return <span className="badge badge-danger"><XCircle size={10} /> Failed</span>;
  return <span className="badge badge-warning"><Clock size={10} className="dot dot-pulse dot-warning" /> Processing</span>;
}

function SectionCard({ title, icon: Icon, children, className }: { title: string; icon: React.ComponentType<any>; children: React.ReactNode; className?: string }) {
  return (
    <div className={`card section-card ${className || ''}`}>
      <div className="section-header">
        <div className="section-icon"><Icon size={18} /></div>
        <h3 className="section-title">{title}</h3>
      </div>
      <div className="section-content">{children}</div>
    </div>
  );
}

function KeyValueRow({ label, value, monospace = false }: { label: string; value: string | number | React.ReactNode; monospace?: boolean }) {
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className={monospace ? 'kv-value mono' : 'kv-value'}>{value}</span>
    </div>
  );
}

function SqlBlock({ sql }: { sql: string }) {
  return <pre className="sql-display"><code>{sql}</code></pre>;
}

function MermaidBlock({ diagram }: { diagram: string }) {
  return <MermaidDiagram diagram={diagram} />;
}

function ChatPanel({ analysisId }: { analysisId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    chatApi.history(analysisId).then(data => setMessages(data.messages)).catch(() => {});
  }, [analysisId]);

  async function handleSend(content: string) {
    if (!content.trim() || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content, timestamp: new Date().toISOString() }]);
    setLoading(true);
    try {
      const res = await chatApi.send(analysisId, content);
      setMessages(prev => [...prev, { role: 'assistant', content: res.response, timestamp: new Date().toISOString() }]);
      setSuggestions(res.follow_up_suggestions);
    } catch (_err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.', timestamp: new Date().toISOString() }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    try {
      await chatApi.clear(analysisId);
      setMessages([]);
      setSuggestions([]);
    } catch {}
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h3>Architecture Discussion</h3>
        <button className="btn btn-ghost btn-sm" onClick={handleClear}>Clear</button>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <MessageSquare size={32} />
            <p>Ask questions about your architecture design</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
            <div className="chat-msg-avatar">{msg.role === 'user' ? 'U' : 'AI'}</div>
            <div className="chat-msg-content" dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }} />
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg-assistant">
            <div className="chat-msg-avatar">AI</div>
            <div className="chat-msg-content"><div className="spinner" style={{ width: 16, height: 16 }} /> Thinking...</div>
          </div>
        )}
      </div>
      {suggestions.length > 0 && !loading && (
        <div className="chat-suggestions">
          {suggestions.map((s, i) => (
            <button key={i} className="suggestion-chip" onClick={() => handleSend(s)}>{s}</button>
          ))}
        </div>
      )}
      <div className="chat-input-bar">
        <input
          className="input"
          placeholder="Ask about your architecture..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend(input)}
          disabled={loading}
        />
        <button className="btn btn-primary" onClick={() => handleSend(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}

export default function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    if (!id) return;
    async function fetchAnalysis() {
      try {
        const data = await analyzeApi.get(id!);
        setAnalysis(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load analysis');
      } finally {
        setLoading(false);
      }
    }
    fetchAnalysis();
  }, [id]);

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleCopyId() {
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      showToast('Analysis ID copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast('Failed to copy', 'error');
    }
  }

  async function handleDownload(format: 'markdown' | 'json') {
    if (!id) return;
    try {
      const url = analyzeApi.exportUrl(id, format);
      const token = localStorage.getItem('maasa_token');
      const res = await fetch(url, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `maasa-export-${id}.${format === 'markdown' ? 'md' : 'json'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
      showToast(`Downloading as ${format}...`);
    } catch {
      showToast('Download failed', 'error');
    }
  }

  function handleShare() {
    if (!id) return;
    const url = `${window.location.origin}/analyses/${id}`;
    navigator.clipboard.writeText(url).then(() => {
      showToast('Share link copied to clipboard');
    }).catch(() => {
      showToast('Failed to copy link', 'error');
    });
  }

  async function handleDelete() {
    if (!id || !confirm('Are you sure you want to delete this analysis? This cannot be undone.')) return;
    try {
      await analyzeApi.delete(id);
      showToast('Analysis deleted');
      navigate('/analyses');
    } catch (_err) {
      showToast('Failed to delete analysis', 'error');
    }
  }

  if (loading) {
    return (
      <div className="detail-loading">
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <p>Loading analysis...</p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="detail-error">
        <XCircle size={48} />
        <h3>Analysis not found</h3>
        <p className="text-secondary">{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/analyses')}>
          <ArrowLeft size={16} /> Back to Analyses
        </button>
      </div>
    );
  }

  const isProcessing = analysis.status === 'processing';

  return (
    <div className="detail-page">
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={14} /> : <XCircle size={14} />}
          {toast.message}
        </div>
      )}

      <div className="detail-header">
        <button className="btn btn-ghost" onClick={() => navigate('/analyses')}>
          <ArrowLeft size={16} /> Back
        </button>
        <div className="header-info">
          <h1 className="detail-title">{analysis.business_problem.slice(0, 100)}</h1>
          <div className="detail-meta">
            <StatusBadge status={analysis.status} />
            <span className="text-muted">|</span>
            <span className="text-sm text-secondary">Created {new Date(analysis.created_at).toLocaleDateString()}</span>
            {analysis.analysis_time_seconds && (
              <>
                <span className="text-muted">|</span>
                <span className="text-sm text-secondary">{analysis.analysis_time_seconds.toFixed(1)}s analysis time</span>
              </>
            )}
          </div>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost btn-sm" title="Copy ID" onClick={handleCopyId}>
            <Copy size={14} /> {copied ? 'Copied!' : 'Copy ID'}
          </button>
          <button className="btn btn-ghost btn-sm" title="Download Markdown" onClick={() => handleDownload('markdown')}>
            <Download size={14} /> .md
          </button>
          <button className="btn btn-ghost btn-sm" title="Download JSON" onClick={() => handleDownload('json')}>
            <Download size={14} /> .json
          </button>
          <button className="btn btn-ghost btn-sm" title="Share" onClick={handleShare}>
            <Share2 size={14} /> Share
          </button>
          <button className="btn btn-danger btn-sm" title="Delete" onClick={handleDelete}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </div>

      <div className="detail-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            disabled={isProcessing && tab.id !== 'overview'}
          >
            <tab.icon size={14} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="detail-content">
        {activeTab === 'overview' && (
          <div className="tab-content">
            <div className="grid-2">
              <SectionCard title="Business Problem" icon={FileText}>
                <p className="problem-text">{analysis.business_problem}</p>
              </SectionCard>
              <SectionCard title="Metadata" icon={Zap}>
                <div className="kv-grid">
                  <KeyValueRow label="Analysis ID" value={analysis.id} monospace />
                  <KeyValueRow label="Status" value={<StatusBadge status={analysis.status} />} />
                  <KeyValueRow label="Created" value={new Date(analysis.created_at).toLocaleString()} />
                  <KeyValueRow label="Duration" value={analysis.analysis_time_seconds ? `${analysis.analysis_time_seconds.toFixed(1)}s` : '—'} />
                </div>
              </SectionCard>
            </div>

            {analysis.diagrams?.mermaid && (
              <SectionCard title="System Architecture Diagram" icon={GitBranch} className="full-width">
                <MermaidBlock diagram={analysis.diagrams.mermaid} />
              </SectionCard>
            )}
          </div>
        )}

        {activeTab === 'requirements' && analysis.requirements && (
          <div className="tab-content">
            <div className="grid-2">
              <SectionCard title="Functional Requirements" icon={CheckCircle}>
                <ul className="req-list">
                  {analysis.requirements.functional?.map((req: string, i: number) => (
                    <li key={i}><span className="req-bullet" />{req}</li>
                  ))}
                </ul>
              </SectionCard>
              <SectionCard title="Non-Functional Requirements" icon={Shield}>
                <ul className="req-list">
                  {analysis.requirements.non_functional?.map((req: string, i: number) => (
                    <li key={i}><span className="req-bullet" />{req}</li>
                  ))}
                </ul>
              </SectionCard>
            </div>
          </div>
        )}

        {activeTab === 'architecture' && analysis.architecture_design && (
          <div className="tab-content">
            <SectionCard title="System Overview" icon={GitBranch} className="full-width">
              <div className="grid-3">
                <KeyValueRow label="System Type" value={analysis.architecture_design.system_type} />
                <KeyValueRow label="Pattern" value={analysis.architecture_design.pattern} />
              </div>
              <p className="mt-2 text-secondary">{analysis.architecture_design.justification}</p>
            </SectionCard>
            {analysis.architecture_design.components && (
              <SectionCard title="Components" icon={Server}>
                <div className="components-grid">
                  {analysis.architecture_design.components.map((comp: any, i: number) => (
                    <div key={i} className="component-card">
                      <h4>{comp.name}</h4>
                      <p className="text-sm text-secondary">{comp.description}</p>
                      <span className="badge badge-accent">{comp.technology}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}
          </div>
        )}

        {activeTab === 'database' && analysis.database_schema && (
          <div className="tab-content">
            <SectionCard title="Database Design" icon={Database} className="full-width">
              <KeyValueRow label="Database Type" value={analysis.database_schema.database_type} />
              <p className="mt-2 text-secondary">{analysis.database_schema.justification}</p>
            </SectionCard>
            {analysis.database_schema.schemas && (
              <SectionCard title="Schemas" icon={FileText}>
                {analysis.database_schema.schemas.map((schema: any, i: number) => (
                  <div key={i} className="schema-block">
                    <h4>{schema.table_name}</h4>
                    <SqlBlock sql={schema.sql} />
                  </div>
                ))}
              </SectionCard>
            )}
            {analysis.database_schema.indexing_strategies && (
              <SectionCard title="Indexing Strategies" icon={ZapIcon}>
                <ul className="req-list">
                  {analysis.database_schema.indexing_strategies.map((idx: string, i: number) => (
                    <li key={i}><span className="req-bullet" />{idx}</li>
                  ))}
                </ul>
              </SectionCard>
            )}
          </div>
        )}

        {activeTab === 'api' && analysis.api_specification && (
          <div className="tab-content">
            <SectionCard title="API Specification" icon={Server} className="full-width">
              <KeyValueRow label="Protocol" value={analysis.api_specification.protocol} />
              {analysis.api_specification.endpoints && (
                <div className="endpoints-list mt-2">
                  {analysis.api_specification.endpoints.map((ep: any, i: number) => (
                    <div key={i} className="endpoint-card">
                      <div className="endpoint-header">
                        <span className={`badge method-${ep.method.toLowerCase()}`}>{ep.method}</span>
                        <code className="endpoint-path">{ep.path}</code>
                      </div>
                      <p className="text-sm text-secondary">{ep.description}</p>
                      {ep.request_body && (
                        <div className="endpoint-body">
                          <span className="kv-label">Request</span>
                          <pre><code>{typeof ep.request_body === 'string' ? ep.request_body : JSON.stringify(ep.request_body, null, 2)}</code></pre>
                        </div>
                      )}
                      {ep.response_body && (
                        <div className="endpoint-body">
                          <span className="kv-label">Response</span>
                          <pre><code>{typeof ep.response_body === 'string' ? ep.response_body : JSON.stringify(ep.response_body, null, 2)}</code></pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        )}

        {activeTab === 'deployment' && analysis.deployment_config && (
          <div className="tab-content">
            <SectionCard title="Infrastructure as Code" icon={Shield} className="full-width">
              <KeyValueRow label="IaC Tool" value={analysis.deployment_config.infrastructure_as_code} />
              <KeyValueRow label="Orchestration" value={analysis.deployment_config.orchestration} />
            </SectionCard>
            {analysis.deployment_config.terraform_sample && (
              <SectionCard title="Terraform Sample" icon={FileText}>
                <pre className="code-block"><code>{analysis.deployment_config.terraform_sample}</code></pre>
              </SectionCard>
            )}
            {analysis.deployment_config.kubernetes_manifest && (
              <SectionCard title="Kubernetes Manifest" icon={GitBranch}>
                <pre className="code-block"><code>{analysis.deployment_config.kubernetes_manifest}</code></pre>
              </SectionCard>
            )}
          </div>
        )}

        {activeTab === 'security' && analysis.security_audit && (
          <div className="tab-content">
            <SectionCard title="Vulnerability Mitigations" icon={Shield}>
              <ul className="req-list">
                {analysis.security_audit.vulnerability_mitigations?.map((v: string, i: number) => (
                  <li key={i}><span className="req-bullet" />{v}</li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title="Compliance" icon={FileText}>
              <p>{analysis.security_audit.compliance}</p>
            </SectionCard>
          </div>
        )}

        {activeTab === 'performance' && analysis.performance_strategies && (
          <div className="tab-content">
            <SectionCard title="Caching Strategy" icon={ZapIcon}>
              <p>{analysis.performance_strategies.caching}</p>
            </SectionCard>
            <SectionCard title="Optimization" icon={Shield}>
              <p>{analysis.performance_strategies.optimization}</p>
            </SectionCard>
          </div>
        )}

        {activeTab === 'diagrams' && analysis.diagrams && (
          <div className="tab-content">
            {analysis.diagrams.mermaid && (
              <SectionCard title="Mermaid Diagram" icon={GitBranch} className="full-width">
                <MermaidBlock diagram={analysis.diagrams.mermaid} />
              </SectionCard>
            )}
            {analysis.diagrams.ascii && (
              <SectionCard title="ASCII Diagram" icon={FileText} className="full-width">
                <pre className="ascii-display">{analysis.diagrams.ascii}</pre>
              </SectionCard>
            )}
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="tab-content">
            <ChatPanel analysisId={analysis.id} />
          </div>
        )}
      </div>
    </div>
  );
}
