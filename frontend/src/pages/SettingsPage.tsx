// src/pages/SettingsPage.tsx
import { useState, useEffect } from 'react';
import { User, Lock, Key, Save, AlertCircle, CheckCircle, Plus, Trash2, Shield } from 'lucide-react';
import { authApi, apiKeysApi, type ApiKey } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './SettingsPage.css';

export default function SettingsPage() {
  const { user } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null);

  useEffect(() => {
    if (user) setName(user.name);
  }, [user]);

  useEffect(() => {
    apiKeysApi.list().then(setApiKeys).catch(() => {});
  }, []);

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await authApi.updateProfile({ name });
      showToast('Profile updated successfully');
    } catch (err: any) {
      showToast(err.message || 'Failed to update profile', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showToast('Passwords do not match', 'error');
      return;
    }
    if (newPassword.length < 6) {
      showToast('Password must be at least 6 characters', 'error');
      return;
    }
    setChangingPassword(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      showToast('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      showToast(err.message || 'Failed to change password', 'error');
    } finally {
      setChangingPassword(false);
    }
  }

  async function handleCreateApiKey(e: React.FormEvent) {
    e.preventDefault();
    setCreatingKey(true);
    try {
      const res = await apiKeysApi.create({ name: newKeyName });
      setApiKeys(prev => [{ id: res.id, name: res.name, key_preview: res.key_preview, created_at: res.created_at, expires_at: res.expires_at, last_used_at: res.last_used_at }, ...prev]);
      setNewKeyValue(res.full_key);
      setNewKeyName('');
      showToast('API key created');
    } catch (err: any) {
      showToast(err.message || 'Failed to create API key', 'error');
    } finally {
      setCreatingKey(false);
    }
  }

  async function handleRevokeKey(keyId: string) {
    if (!confirm('Revoke this API key? This cannot be undone.')) return;
    try {
      await apiKeysApi.revoke(keyId);
      setApiKeys(prev => prev.filter(k => k.id !== keyId));
      showToast('API key revoked');
    } catch (_err) {
      showToast('Failed to revoke key', 'error');
    }
  }

  return (
    <div className="settings-page">
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          {toast.message}
        </div>
      )}

      <h1>Settings</h1>
      <p className="text-secondary text-sm" style={{ marginBottom: '2rem' }}>Manage your account and preferences</p>

      <div className="settings-grid">
        {/* Profile */}
        <div className="card settings-card">
          <div className="settings-card-header">
            <div className="settings-icon"><User size={18} /></div>
            <h2>Profile</h2>
          </div>
          <form onSubmit={handleSaveProfile} className="settings-form">
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="input" value={user?.email || ''} disabled />
              <p className="form-hint">Email cannot be changed</p>
            </div>
            <div className="form-group">
              <label className="form-label">Plan</label>
              <div><span className="badge badge-accent">{user?.plan || 'free'}</span></div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              <Save size={14} /> {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </form>
        </div>

        {/* Password */}
        <div className="card settings-card">
          <div className="settings-card-header">
            <div className="settings-icon"><Lock size={18} /></div>
            <h2>Change Password</h2>
          </div>
          <form onSubmit={handleChangePassword} className="settings-form">
            <div className="form-group">
              <label className="form-label">Current Password</label>
              <input className="input" type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">New Password</label>
              <input className="input" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required minLength={6} />
            </div>
            <div className="form-group">
              <label className="form-label">Confirm New Password</label>
              <input className="input" type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required minLength={6} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={changingPassword}>
              <Lock size={14} /> {changingPassword ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>

        {/* API Keys */}
        <div className="card settings-card settings-card-full">
          <div className="settings-card-header">
            <div className="settings-icon"><Key size={18} /></div>
            <h2>API Keys</h2>
          </div>

          {newKeyValue && (
            <div className="api-key-reveal">
              <div className="api-key-reveal-header">
                <Shield size={14} />
                <strong>Your new API key (copy it now, it won't be shown again):</strong>
              </div>
              <code className="api-key-value">{newKeyValue}</code>
              <button className="btn btn-ghost btn-sm" onClick={() => { navigator.clipboard.writeText(newKeyValue); showToast('Copied to clipboard'); }}>
                Copy
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setNewKeyValue(null)}>Dismiss</button>
            </div>
          )}

          <form onSubmit={handleCreateApiKey} className="api-key-form">
            <input className="input" placeholder="Key name (e.g., production, staging)" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} required />
            <button type="submit" className="btn btn-primary" disabled={creatingKey}>
              <Plus size={14} /> {creatingKey ? 'Creating...' : 'Create Key'}
            </button>
          </form>

          <div className="api-keys-list">
            {apiKeys.length === 0 ? (
              <p className="text-secondary text-sm">No API keys yet</p>
            ) : (
              apiKeys.map(key => (
                <div key={key.id} className="api-key-row">
                  <div className="api-key-info">
                    <span className="api-key-name">{key.name}</span>
                    <code className="api-key-preview">{key.key_preview}</code>
                    <span className="text-xs text-muted">Created {new Date(key.created_at).toLocaleDateString()}</span>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => handleRevokeKey(key.id)}>
                    <Trash2 size={12} /> Revoke
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
