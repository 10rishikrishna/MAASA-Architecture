// src/pages/TeamsPage.tsx
import { useState, useEffect } from 'react';
import { Plus, Users, Trash2, ArrowLeft, Crown, Shield, User, AlertCircle, CheckCircle } from 'lucide-react';
import { teamsApi, type Team, type TeamDetail } from '../api/client';
import './TeamsPage.css';

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTeam, setSelectedTeam] = useState<TeamDetail | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [formData, setFormData] = useState({ name: '', description: '' });
  const [memberEmail, setMemberEmail] = useState('');
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => { loadTeams(); }, []);

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function loadTeams() {
    try {
      const data = await teamsApi.list();
      setTeams(data);
    } catch (err) {
      console.error('Failed to load teams', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const team = await teamsApi.create(formData);
      setTeams(prev => [team, ...prev]);
      setShowCreate(false);
      setFormData({ name: '', description: '' });
      showToast('Team created');
    } catch (err: any) {
      showToast(err.message || 'Failed to create team', 'error');
    } finally {
      setCreating(false);
    }
  }

  async function handleSelectTeam(team: Team) {
    try {
      const detail = await teamsApi.get(team.id);
      setSelectedTeam(detail);
    } catch (_err) {
      showToast('Failed to load team details', 'error');
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedTeam) return;
    try {
      await teamsApi.addMember(selectedTeam.id, { email: memberEmail });
      const detail = await teamsApi.get(selectedTeam.id);
      setSelectedTeam(detail);
      setShowAddMember(false);
      setMemberEmail('');
      showToast('Member added');
    } catch (err: any) {
      showToast(err.message || 'Failed to add member', 'error');
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!selectedTeam || !confirm('Remove this member?')) return;
    try {
      await teamsApi.removeMember(selectedTeam.id, userId);
      const detail = await teamsApi.get(selectedTeam.id);
      setSelectedTeam(detail);
      showToast('Member removed');
    } catch (err: any) {
      showToast(err.message || 'Failed to remove member', 'error');
    }
  }

  async function handleDeleteTeam(teamId: string) {
    if (!confirm('Delete this team? This action cannot be undone.')) return;
    try {
      await teamsApi.delete(teamId);
      setTeams(prev => prev.filter(t => t.id !== teamId));
      if (selectedTeam?.id === teamId) setSelectedTeam(null);
      showToast('Team deleted');
    } catch (err: any) {
      showToast(err.message || 'Failed to delete team', 'error');
    }
  }

  function getRoleBadge(role: string) {
    if (role === 'admin') return <span className="badge badge-accent"><Crown size={10} /> Admin</span>;
    if (role === 'viewer') return <span className="badge badge-info"><Shield size={10} /> Viewer</span>;
    return <span className="badge badge-success"><User size={10} /> Member</span>;
  }

  if (selectedTeam) {
    return (
      <div className="teams-page">
        {toast && (
          <div className={`toast toast-${toast.type}`}>
            {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {toast.message}
          </div>
        )}

        <div className="page-header">
          <div className="flex items-center gap-3">
            <button className="btn btn-ghost btn-sm" onClick={() => setSelectedTeam(null)}>
              <ArrowLeft size={16} /> Back
            </button>
            <div>
              <h1>{selectedTeam.name}</h1>
              <p className="text-secondary text-sm">{selectedTeam.description || 'No description'}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={() => setShowAddMember(true)}>
              <Plus size={14} /> Add Member
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => handleDeleteTeam(selectedTeam.id)}>
              <Trash2 size={14} /> Delete
            </button>
          </div>
        </div>

        <div className="team-stats">
          <div className="card stat-mini">
            <span className="stat-mini-value">{selectedTeam.member_count}</span>
            <span className="stat-mini-label">Members</span>
          </div>
          <div className="card stat-mini">
            <span className="stat-mini-value">{new Date(selectedTeam.created_at).toLocaleDateString()}</span>
            <span className="stat-mini-label">Created</span>
          </div>
        </div>

        {showAddMember && (
          <div className="modal-overlay" onClick={() => setShowAddMember(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <h3>Add Team Member</h3>
              <form onSubmit={handleAddMember}>
                <div className="form-group">
                  <label className="form-label">Email Address</label>
                  <input className="input" type="email" placeholder="user@example.com" value={memberEmail} onChange={e => setMemberEmail(e.target.value)} required />
                </div>
                <div className="modal-actions">
                  <button type="button" className="btn btn-ghost" onClick={() => setShowAddMember(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">Add Member</button>
                </div>
              </form>
            </div>
          </div>
        )}

        <div className="card">
          <h3 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>Members</h3>
          <div className="members-list">
            {selectedTeam.members.map(member => (
              <div key={member.id} className="member-row">
                <div className="member-avatar">{member.name.charAt(0).toUpperCase()}</div>
                <div className="member-info">
                  <span className="member-name">{member.name}</span>
                  <span className="member-email">{member.email}</span>
                </div>
                {getRoleBadge(member.role)}
                <button className="icon-btn" onClick={() => handleRemoveMember(member.user_id)} title="Remove">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="teams-page">
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          {toast.message}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1>Teams</h1>
          <p className="text-secondary text-sm">{teams.length} teams</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} /> New Team
        </button>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create Team</h3>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label">Name <span className="required">*</span></label>
                <input className="input" placeholder="My Team" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} required />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea className="input textarea" placeholder="Team description..." value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} rows={3} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>{creating ? 'Creating...' : 'Create Team'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-state"><div className="spinner" style={{ width: 40, height: 40 }} /><p>Loading teams...</p></div>
      ) : teams.length === 0 ? (
        <div className="empty-state">
          <Users size={48} />
          <h3>No teams yet</h3>
          <p className="text-secondary">Create a team to collaborate on projects</p>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>Create First Team</button>
        </div>
      ) : (
        <div className="teams-grid">
          {teams.map(team => (
            <div key={team.id} className="team-card card" onClick={() => handleSelectTeam(team)}>
              <div className="team-card-icon"><Users size={24} /></div>
              <h4>{team.name}</h4>
              <p className="text-sm text-secondary">{team.description || 'No description'}</p>
              <div className="team-card-meta">
                <span>{team.member_count} members</span>
                <span>{new Date(team.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
