// src/pages/ProjectsPage.tsx
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Plus, FolderOpen, ArrowLeft, Edit, Trash2, Users, Globe, Lock } from 'lucide-react';
import { projectsApi, type Project } from '../api/client';
import './ProjectsPage.css';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showProject, setShowProject] = useState<Project | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '', tags: '', visibility: 'private' });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await projectsApi.list(0, 50);
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      const newProject = await projectsApi.create({
        name: formData.name,
        description: formData.description || undefined,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
        visibility: formData.visibility,
      });
      setProjects(prev => [newProject, ...prev]);
      setShowCreate(false);
      setFormData({ name: '', description: '', tags: '', visibility: 'private' });
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(projectId: string) {
    if (!confirm('Delete this project? This action cannot be undone.')) return;
    try {
      await projectsApi.delete(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
      if (showProject?.id === projectId) setShowProject(null);
    } catch (err) {
      console.error('Failed to delete project', err);
    }
  }

  function getVisibilityBadge(vis: string) {
    if (vis === 'public') return <span className="badge badge-success"><Globe size={10} /> Public</span>;
    if (vis === 'team') return <span className="badge badge-info"><Users size={10} /> Team</span>;
    return <span className="badge badge-accent"><Lock size={10} /> Private</span>;
  }

  if (id && !showProject) {
    const project = projects.find(p => p.id === id);
    if (project) setShowProject(project);
  }

  if (showProject) {
    return (
      <div className="project-detail">
        <div className="detail-header">
          <button className="btn btn-ghost" onClick={() => { setShowProject(null); navigate('/projects'); }}>
            <ArrowLeft size={16} /> Back
          </button>
          <div>
            <h1>{showProject.name}</h1>
            <p className="text-secondary text-sm">{showProject.description || 'No description'}</p>
          </div>
          <div className="detail-actions">
            {getVisibilityBadge(showProject.visibility)}
            <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/projects/${showProject.id}`)}>
              <Edit size={14} /> Edit
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => handleDelete(showProject.id)}>
              <Trash2 size={14} /> Delete
            </button>
          </div>
        </div>

        <div className="project-meta">
          <div className="meta-item"><span className="meta-label">ID</span><span className="meta-value mono">{showProject.id}</span></div>
          <div className="meta-item"><span className="meta-label">Created</span><span className="meta-value">{new Date(showProject.created_at).toLocaleDateString()}</span></div>
          <div className="meta-item"><span className="meta-label">Updated</span><span className="meta-value">{new Date(showProject.updated_at).toLocaleDateString()}</span></div>
          <div className="meta-item"><span className="meta-label">Analyses</span><span className="meta-value">{showProject.analysis_ids?.length || 0}</span></div>
        </div>

        {showProject.tags.length > 0 && (
          <div className="tags-section">
            <h4>Tags</h4>
            <div className="tags-list">
              {showProject.tags.map(t => <span key={t} className="tag">{t}</span>)}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="projects-page">
      <div className="page-header">
        <div>
          <h1>Projects</h1>
          <p className="text-secondary text-sm">{projects.length} projects</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} /> New Project
        </button>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create Project</h3>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Name <span className="required">*</span></label>
                <input className="input" placeholder="My Awesome Project" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} required />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea className="input textarea" placeholder="Project description..." value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} rows={3} />
              </div>
              <div className="form-group">
                <label className="form-label">Tags (comma-separated)</label>
                <input className="input" placeholder="backend, api, microservices" value={formData.tags} onChange={e => setFormData({...formData, tags: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Visibility</label>
                <select className="input" value={formData.visibility} onChange={e => setFormData({...formData, visibility: e.target.value})}>
                  <option value="private">Private</option>
                  <option value="team">Team</option>
                  <option value="public">Public</option>
                </select>
              </div>
              {error && <div className="auth-error">{error}</div>}
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>{creating ? 'Creating...' : 'Create Project'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-state"><div className="spinner" style={{ width: 40, height: 40 }} /><p>Loading projects...</p></div>
      ) : projects.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={48} />
          <h3>No projects yet</h3>
          <p className="text-secondary">Organize your analyses into projects for better management</p>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>Create First Project</button>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map(p => (
            <div key={p.id} className="project-card" onClick={() => setShowProject(p)}>
              <div className="project-icon"><FolderOpen size={24} /></div>
              <div className="project-info">
                <div className="project-name-row">
                  <h4>{p.name}</h4>
                  {getVisibilityBadge(p.visibility)}
                </div>
                <p className="project-desc">{p.description || 'No description'}</p>
                <div className="project-meta">
                  <span>{p.analysis_ids?.length || 0} analyses</span>
                  <span>{new Date(p.updated_at).toLocaleDateString()}</span>
                </div>
                {p.tags.length > 0 && (
                  <div className="project-tags">
                    {p.tags.slice(0, 3).map(t => <span key={t} className="tag">{t}</span>)}
                    {p.tags.length > 3 && <span className="tag more">+{p.tags.length - 3}</span>}
                  </div>
                )}
              </div>
              <div className="project-actions">
                <button className="icon-btn" onClick={e => { e.stopPropagation(); handleDelete(p.id); }} title="Delete">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}