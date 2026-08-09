// src/pages/AnalysisDetailPage.tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, Download, CheckCircle, XCircle, Clock, Zap, FileText, Database, Server, Shield, GitBranch, Trash2, Share2, MessageSquare, BookOpen, Film, HelpCircle, Info, AlertTriangle } from 'lucide-react';
import { analyzeApi, type AnalysisDetail, chatApi, type ChatMessage, type ValidationSummary, type ArchitectureComponent } from '../api/client';
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
  { id: 'performance', label: 'Performance', icon: Zap },
  { id: 'diagrams', label: 'Diagrams', icon: GitBranch },
  { id: 'chat', label: 'Chat with Sulaiman AI 👳🏽‍♂️', icon: MessageSquare },
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

function renderMarkdown(text: string): string {
  return (text || '')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\n)- /g, '$1• ')
    .replace(/`([^`]*)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>');
}

function reqText(r: any): string {
  if (typeof r === 'string') return r;
  if (r && typeof r === 'object') return r.description || r.requirement || r.id || JSON.stringify(r);
  return String(r ?? '');
}

function reqBadge(r: any): string | null {
  if (r && typeof r === 'object' && (r.priority || r.category)) {
    return [r.priority, r.category].filter(Boolean).join(' · ');
  }
  return null;
}

function ChatPanel({ analysisId }: { analysisId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    chatApi.history(analysisId).then(data => setMessages(data.messages)).catch(() => { });
  }, [analysisId]);

  async function handleSend(content: string) {
    if (!content.trim() || loading) return;
    const userMsg = content;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date().toISOString() }]);
    setLoading(true);

    try {
      const [res] = await Promise.all([
        chatApi.send(analysisId, userMsg),
        new Promise(resolve => setTimeout(resolve, 1200))
      ]);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.response + (res.modification_applied ? `\n\n_✅ Applied: ${(res.modified_sections || []).join(', ')} updated._` : ''),
        timestamp: new Date().toISOString(),
        modification_applied: res.modification_applied,
        modified_sections: res.modified_sections,
      }]);
      setSuggestions(res.follow_up_suggestions);
    } catch (_err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Deyy, cheriya signal issue. Try typing again! 😄', timestamp: new Date().toISOString() }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    try {
      await chatApi.clear(analysisId);
      setMessages([]);
      setSuggestions([]);
    } catch { }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-title-group">
          <h3>Sulaiman AI 👳🏽‍♂️</h3>
          <span className="text-xs text-muted">Your AI Architecture Assistant (Confident & Helpful)</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={handleClear}>Clear History</button>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <MessageSquare size={36} className="text-accent" />
            <h4>Njan Sulaiman AI! 😄</h4>
            <p>Njan Sulaiman alla... Hanuman aanu. Pande ennod Thamarassery Churam erangiyappo chodichathaa. Ningal sheriaya sthalath aanu vannirikkunnath, doubt okke namukku fix cheyyam! Ask me anything about your system architecture!</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
            <div className="chat-msg-avatar">{msg.role === 'user' ? 'U' : '👳🏽‍♂️'}</div>
            <div className="chat-msg-content" dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }} />
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg-assistant">
            <div className="chat-msg-avatar">👳🏽‍♂️</div>
            <div className="chat-msg-content typing-indicator">
              <div className="spinner" style={{ width: 14, height: 14 }} />
              <span>Sulaiman AI is typing... 💬</span>
            </div>
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
          placeholder="Ask Sulaiman AI about components, Redis, endpoints, security..."
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
  const [validation, setValidation] = useState<ValidationSummary | null>(null);
  const [selectedNode, setSelectedNode] = useState<ArchitectureComponent | null>(null);
  const [activeDiagramLevel, setActiveDiagramLevel] = useState<'level1' | 'level2' | 'level3'>('level2');

  // Explanation Controls State
  const [explanationMode, setExplanationMode] = useState<'technical' | 'story'>('technical');

  const [explanationLevel, setExplanationLevel] = useState<'basic' | 'intermediate'>('basic');
  useEffect(() => {
    if (!id) return;
    async function fetchAnalysis() {
      try {
        const data = await analyzeApi.get(id!);
        setAnalysis(data);
        if (data.architecture_model) {
          analyzeApi.validate(id!).then(setValidation).catch(() => { });
        }
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
      const token = localStorage.getItem('mosaic_token');
      const res = await fetch(url, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `mosaic-export-${id}.${format === 'markdown' ? 'md' : 'json'}`;
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
  const archDesign = analysis.architecture_design ?? ({} as NonNullable<AnalysisDetail['architecture_design']>);

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

      {/* Validation / cross-tab consistency banner */}
      {!isProcessing && analysis.architecture_model && (
        <div className={`validation-banner ${validation ? (validation.passes ? 'validation-ok' : 'validation-warn') : 'validation-loading'}`}>
          <AlertTriangle size={16} />
          <span>
            {!validation
              ? 'Running cross-tab consistency checks...'
              : validation.passes
                ? 'Cross-tab consistency checks passed — no contradictions between tabs.'
                : `${validation.error_count} error(s) and ${validation.warning_count} warning(s) found. ${validation.errors.map(e => e.message).join(' ')}`}
          </span>
        </div>
      )}

      {/* Explanation Controls Bar for Overview and Architecture tabs */}
      {(activeTab === 'overview' || activeTab === 'architecture' || activeTab === 'diagrams') && (
        <div className="explanation-controls-bar fade-in">
          <div className="control-group">
            <span className="control-label"><BookOpen size={14} /> Explanation Mode:</span>
            <button className={`mode-btn ${explanationMode === 'technical' ? 'active' : ''}`} onClick={() => setExplanationMode('technical')}>
              📘 Technical
            </button>
            <button className={`mode-btn ${explanationMode === 'story' ? 'active' : ''}`} onClick={() => setExplanationMode('story')}>
              🎭 Story Mode
            </button>
          </div>

          <div className="control-group">
            <span className="control-label"><Info size={14} /> Detail Level:</span>
            <button className={`level-btn ${explanationLevel === 'basic' ? 'active' : ''}`} onClick={() => setExplanationLevel('basic')}>
              🟢 Basic (ELI5 Terms & Symbols)
            </button>
            <button className={`level-btn ${explanationLevel === 'intermediate' ? 'active' : ''}`} onClick={() => setExplanationLevel('intermediate')}>
              🟡 Intermediate
            </button>
          </div>
        </div>
      )}

      <div className="detail-content">
        {activeTab === 'overview' && (
          <div className="tab-content">
            {/* Story Mode Card if enabled */}
            {explanationMode === 'story' && archDesign.story_mode && (
              <SectionCard title="Architecture Story Mode 🎬" icon={Film} className="full-width story-card fade-in">
                <div className="story-content" dangerouslySetInnerHTML={{ __html: archDesign.story_mode.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }} />
              </SectionCard>
            )}

            {/* Basic ELI5 Terms & Symbols Decoder Grid */}
            {explanationLevel === 'basic' && archDesign.eli5_terms && (
              <SectionCard title="Terms & Diagram Symbols Decoder 🟢 (ELI5 Beginner Guide)" icon={HelpCircle} className="full-width eli5-card fade-in">
                <p className="text-sm text-secondary mb-3">Here is what every term, arrow, shape, and symbol in your architecture diagram means:</p>
                <div className="eli5-grid">
                  {archDesign.eli5_terms.map((item: any, i: number) => (
                    <div key={i} className="eli5-item">
                      <div className="eli5-item-header">
                        <span className="eli5-term">{item.term}</span>
                        <span className="badge badge-accent">{item.symbol}</span>
                      </div>
                      <p className="eli5-meaning"><strong>Meaning:</strong> {item.meaning}</p>
                      <p className="eli5-analogy"><strong>Analogy:</strong> {item.analogy}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

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

            {analysis.architecture_model && (
              <>
                <div className="grid-2">
                  <SectionCard title="Domain & Architecture" icon={GitBranch}>
                    <div className="kv-grid">
                      <KeyValueRow label="Domain" value={analysis.architecture_model.domain || '—'} />
                      <KeyValueRow label="Pattern" value={analysis.architecture_model.architecture?.pattern || '—'} />
                      <KeyValueRow label="System Type" value={analysis.architecture_model.architecture?.system_type || '—'} />
                      <KeyValueRow label="Tier" value={analysis.architecture_model.architecture_tier || '—'} />
                      <KeyValueRow label="Corrections" value={analysis.architecture_model.correction_iterations ?? 0} />
                    </div>
                  </SectionCard>
                  <SectionCard title="Workload & Review" icon={Zap}>
                    <div className="kv-grid">
                      <KeyValueRow label="Avg Throughput" value={`${analysis.architecture_model.performance?.workload?.avg_requests_per_second ?? '—'} req/s`} />
                      <KeyValueRow label="Peak Throughput" value={`${analysis.architecture_model.performance?.workload?.peak_requests_per_second ?? '—'} req/s`} />
                      <KeyValueRow label="Concurrency" value={analysis.architecture_model.performance?.workload?.expected_concurrency ?? '—'} />
                      <KeyValueRow label="Complexity" value={`${analysis.architecture_model.performance?.workload?.complexity_score ?? '—'}/100`} />
                      <KeyValueRow label="Review Score" value={analysis.architecture_model.review?.overall_score != null ? `${analysis.architecture_model.review.overall_score}/100` : '—'} />
                    </div>
                  </SectionCard>
                </div>
                {analysis.architecture_model.overview && (
                  <SectionCard title="Executive Overview" icon={BookOpen} className="full-width">
                    <p className="problem-text">{analysis.architecture_model.overview}</p>
                  </SectionCard>
                )}
              </>
            )}

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
                  {analysis.requirements.functional?.map((req: any, i: number) => (
                    <li key={i}>
                      <span className="req-bullet" />
                      <div>
                        {reqText(req)}
                        {reqBadge(req) && <span className="badge badge-accent req-priority">{reqBadge(req)}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              </SectionCard>
              <SectionCard title="Non-Functional Requirements" icon={Shield}>
                <ul className="req-list">
                  {analysis.requirements.non_functional?.map((req: any, i: number) => (
                    <li key={i}>
                      <span className="req-bullet" />
                      <div>
                        {reqText(req)}
                        {reqBadge(req) && <span className="badge badge-accent req-priority">{reqBadge(req)}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </div>
          </div>
        )}

        {activeTab === 'architecture' && analysis.architecture_design && (
          <div className="tab-content">
            {/* Story Mode Narrative */}
            {explanationMode === 'story' && archDesign.story_mode && (
              <SectionCard title="Architecture Story Mode 🎬" icon={Film} className="full-width story-card fade-in">
                <div className="story-content" dangerouslySetInnerHTML={{ __html: archDesign.story_mode.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }} />
              </SectionCard>
            )}

            {/* Basic ELI5 Terms Decoder */}
            {explanationLevel === 'basic' && archDesign.eli5_terms && (
              <SectionCard title="Terms & Diagram Symbols Decoder 🟢" icon={HelpCircle} className="full-width eli5-card fade-in">
                <div className="eli5-grid">
                  {archDesign.eli5_terms.map((item: any, i: number) => (
                    <div key={i} className="eli5-item">
                      <div className="eli5-item-header">
                        <span className="eli5-term">{item.term}</span>
                        <span className="badge badge-accent">{item.symbol}</span>
                      </div>
                      <p className="eli5-meaning"><strong>Meaning:</strong> {item.meaning}</p>
                      <p className="eli5-analogy"><strong>Analogy:</strong> {item.analogy}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            <SectionCard title="System Overview" icon={GitBranch} className="full-width">
              <div className="grid-3">
                <KeyValueRow label="System Type" value={analysis.architecture_design.system_type} />
                <KeyValueRow label="Pattern" value={analysis.architecture_design.pattern} />
              </div>
              <p className="mt-2 text-secondary">{analysis.architecture_design.justification}</p>
            </SectionCard>

            {/* Alternative Architectures (2-Tier / 3-Tier / Current) */}
            {(() => {
              const alternatives =
                analysis.architecture_model?.architecture?.alternatives ??
                analysis.architecture_design?.alternatives ??
                [];
              if (!alternatives.length) return null;
              return (
                <SectionCard title="Alternative Architectures (2-Tier & 3-Tier comparison)" icon={GitBranch} className="full-width">
                  <p className="text-sm text-secondary mb-3">
                    The same business problem can be built in several shapes. Below are the current design and the two
                    classic alternatives — 2-tier and 3-tier — each with the full request flow so you can compare them.
                  </p>
                  <div className="alternatives-list">
                    {alternatives.map((alt: any, i: number) => (
                      <div key={i} className={`alternative-card ${alt.recommended ? 'alternative-recommended' : ''}`}>
                        <div className="alternative-header">
                          <h4>{alt.name}</h4>
                          {alt.recommended && <span className="badge badge-success">✓ Current & Recommended</span>}
                        </div>
                        <p className="alternative-desc">{alt.description}</p>

                        {alt.components && (
                          <div className="alternative-components">
                            <strong>Components:</strong>
                            <div className="alt-comp-grid">
                              {alt.components.map((c: any, j: number) => (
                                <div key={j} className="alt-comp">
                                  <span className="alt-comp-name">{c.name}</span>
                                  <span className="badge badge-accent">{c.technology}</span>
                                  <span className="alt-comp-resp">{c.responsibility}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {alt.flow && (
                          <div className="alternative-flow">
                            <strong>Detailed request flow:</strong>
                            <ol className="flow-list">
                              {alt.flow.map((step: string, j: number) => (
                                <li key={j}>{step}</li>
                              ))}
                            </ol>
                          </div>
                        )}

                        <div className="alt-pros-cons">
                          <div className="alt-pros">
                            <strong>Pros</strong>
                            <ul>{alt.pros?.map((p: string, j: number) => <li key={j}>{p}</li>)}</ul>
                          </div>
                          <div className="alt-cons">
                            <strong>Cons</strong>
                            <ul>{alt.cons?.map((c: string, j: number) => <li key={j}>{c}</li>)}</ul>
                          </div>
                        </div>

                        {alt.when_to_use && (
                          <p className="alt-when"><strong>When to use it:</strong> {alt.when_to_use}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </SectionCard>
              );
            })()}

            {analysis.architecture_design.components && (
              <SectionCard title="Components" icon={Server}>
                <div className="components-grid">
                  {analysis.architecture_design.components.map((comp: any, i: number) => (
                    <div key={i} className="component-card">
                      <h4>{comp.name}</h4>
                      <p className="text-sm text-secondary">{comp.description}</p>
                      <span className="badge badge-accent">{comp.technology}</span>
                      {comp.reason && <p className="text-xs text-muted mt-2"><strong>Reason:</strong> {comp.reason}</p>}
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
              <SectionCard title="Indexing Strategies" icon={Zap}>
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
            <SectionCard title="Caching Strategy" icon={Zap}>
              <p>{analysis.performance_strategies.caching}</p>
            </SectionCard>
            <SectionCard title="Optimization" icon={Shield}>
              <p>{analysis.performance_strategies.optimization}</p>
            </SectionCard>
          </div>
        )}

        {activeTab === 'diagrams' && (
          <div className="tab-content">
            {analysis.architecture_model?.diagrams ? (
              <>
                <div className="diagram-level-selector">
                  {(['level1', 'level2', 'level3'] as const).map(level => {
                    const meta = analysis.architecture_model!.diagrams![level];
                    return (
                      <button
                        key={level}
                        className={`level-btn ${activeDiagramLevel === level ? 'active' : ''}`}
                        onClick={() => setActiveDiagramLevel(level)}
                      >
                        {meta?.title || level}
                      </button>
                    );
                  })}
                </div>
                {(() => {
                  const meta = analysis.architecture_model!.diagrams![activeDiagramLevel];
                  const level = activeDiagramLevel.toUpperCase();
                  return (
                    <>
                      {meta?.description && <p className="text-sm text-secondary diagram-desc">{meta.description}</p>}
                      {meta?.mermaid ? (
                        <SectionCard title={`Diagram — ${meta.title || level}`} icon={GitBranch} className="full-width">
                          <MermaidDiagram
                            chart={meta.mermaid}
                            nodeMap={meta.node_map}
                            onNodeClick={(nodeId, name) => {
                              const comp = analysis.architecture_model!.architecture?.components?.find(
                                c => c.name === name || c.id === nodeId
                              );
                              setSelectedNode(comp || {
                                name, type: 'component', technology: '—', responsibility: 'See the architecture tab for details.',
                              } as ArchitectureComponent);
                            }}
                          />
                        </SectionCard>
                      ) : (
                        <SectionCard title={`Diagram — ${level}`} icon={GitBranch} className="full-width">
                          <p className="text-secondary">No mermaid diagram for {level}.</p>
                        </SectionCard>
                      )}
                      {meta?.ascii && (
                        <SectionCard title={`ASCII Layout — ${level}`} icon={FileText} className="full-width">
                          <pre className="ascii-display">{meta.ascii}</pre>
                        </SectionCard>
                      )}
                    </>
                  );
                })()}
                {selectedNode && (
                  <SectionCard title="Selected Component" icon={Info} className="full-width fade-in">
                    <div className="kv-grid">
                      <KeyValueRow label="Name" value={selectedNode.name} />
                      <KeyValueRow label="Type" value={selectedNode.type} />
                      <KeyValueRow label="Technology" value={selectedNode.technology || '—'} />
                      <KeyValueRow label="Scope" value={selectedNode.internal_or_external || '—'} />
                      <KeyValueRow label="Responsibility" value={selectedNode.responsibility || '—'} />
                      <KeyValueRow label="Scaling" value={selectedNode.scaling_strategy || '—'} />
                      <KeyValueRow label="Failure behavior" value={selectedNode.failure_behavior || '—'} />
                      <KeyValueRow label="Security" value={selectedNode.security_considerations || '—'} />
                    </div>
                  </SectionCard>
                )}
              </>
            ) : (
              <>
            {/* Deep-Dive Overview: everything explained */}
            {(() => {
              const explained =
                analysis.architecture_model?.overview_explained ??
                analysis.architecture_design?.explanations?.overview_explained ??
                [];
              if (!explained.length) return null;
              return (
                <SectionCard title="Deep-Dive Overview: Everything Explained" icon={BookOpen} className="full-width fade-in">
                  <p className="text-sm text-secondary mb-3">
                    A guided walkthrough of every part of the design — pattern, scale, components, data, API,
                    security, deployment, performance, review and risks — in plain language.
                  </p>
                  <div className="deep-overview">
                    {explained.map((sec: any, i: number) => (
                      <div key={i} className="deep-section">
                        <h4>{sec.title}</h4>
                        {sec.paragraphs.map((p: string, j: number) => (
                          <p key={j} className="deep-para"
                             dangerouslySetInnerHTML={{ __html: renderMarkdown(p) }} />
                        ))}
                      </div>
                    ))}
                  </div>
                </SectionCard>
              );
            })()}

            {analysis.diagrams?.mermaid && (
                  <SectionCard title="Mermaid Diagram" icon={GitBranch} className="full-width">
                    <MermaidBlock diagram={analysis.diagrams.mermaid} />
                  </SectionCard>
                )}
                {analysis.diagrams?.ascii && (
                  <SectionCard title="ASCII Diagram" icon={FileText} className="full-width">
                    <pre className="ascii-display">{analysis.diagrams.ascii}</pre>
                  </SectionCard>
                )}
              </>
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
