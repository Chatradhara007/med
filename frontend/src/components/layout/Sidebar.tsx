import { NavLink } from 'react-router-dom';
import { useAuth } from '../../app/auth/AuthContext';

interface SidebarProps {
  patientName?: string;
}

export const Sidebar = ({ patientName }: SidebarProps) => {
  const { userId } = useAuth();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-header">
        <div className="brand-logo-row">
          <div className="brand-icon">
            <span>CT</span>
          </div>
          <span className="brand-name">CareThread</span>
        </div>
        <div className="brand-badge">
          <span className="pulse-dot" />
          <span>Care Episode Live</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Clinical Record</div>

        <NavLink to="/" end className={({ isActive }) => `nav-link-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </span>
          <span>Timeline & Care</span>
        </NavLink>

        <NavLink to="/documents" className={({ isActive }) => `nav-link-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </span>
          <span>Medical Records</span>
        </NavLink>

        <NavLink to="/medicine" className={({ isActive }) => `nav-link-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
          </span>
          <span>Medications & Safety</span>
        </NavLink>

        <NavLink to="/labs" className={({ isActive }) => `nav-link-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 2v7.31M14 2v7.31M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0" />
            </svg>
          </span>
          <span>Lab Interpretation</span>
        </NavLink>

        <div className="nav-section-title" style={{ marginTop: '16px' }}>Account & Settings</div>

        <NavLink to="/profile" className={({ isActive }) => `nav-link-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </span>
          <span>Patient Profile</span>
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="patient-context-badge">
          <span className="patient-context-label">Active Episode</span>
          <span className="patient-context-name">{patientName || 'Active Patient'}</span>
          <span style={{ fontSize: '10.5px', color: 'var(--ct-text-muted)', fontFamily: 'monospace' }}>
            ID: {userId ? `${userId.slice(0, 10)}...` : 'Connected'}
          </span>
        </div>
      </div>
    </aside>
  );
};
