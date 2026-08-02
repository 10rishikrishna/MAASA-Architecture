// src/components/Sidebar.tsx
import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Zap, FolderOpen, LogOut, ChevronLeft, ChevronRight,
  Users, Settings
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Sidebar.css';

const NAV = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/analyze/new',icon: Zap,              label: 'New Analysis' },
  { to: '/analyses',   icon: Zap,              label: 'Analyses' },
  { to: '/projects',   icon: FolderOpen,       label: 'Projects' },
  { to: '/teams',      icon: Users,            label: 'Teams' },
  { to: '/settings',   icon: Settings,         label: 'Settings' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  function handleLogout() { logout(); navigate('/login'); }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-logo">
        <div className="logo-icon">M</div>
        {!collapsed && <span className="logo-text">Mosaic Studio</span>}
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Icon size={18} />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-bottom">
        {user && (
          <div className="sidebar-user">
            <div className="avatar">{user.name.charAt(0).toUpperCase()}</div>
            {!collapsed && (
              <div className="user-info">
                <span className="user-name">{user.name}</span>
                <span className="user-plan badge badge-accent">{user.plan}</span>
              </div>
            )}
          </div>
        )}

        <button className="nav-item logout-btn" onClick={handleLogout} title="Logout">
          <LogOut size={18} />
          {!collapsed && <span>Logout</span>}
        </button>

        <button className="collapse-btn" onClick={() => setCollapsed(c => !c)}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
