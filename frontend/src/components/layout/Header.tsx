import { useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../app/auth/AuthContext';

const ROUTE_LABELS: Record<string, string> = {
  '/': 'Care Timeline & Schedule',
  '/documents': 'Medical Documents Hub',
  '/medicine': 'Medications & Safety Analysis',
  '/medicine/result': 'Medicine Substitution Result',
  '/medicine/history': 'Previous Scans',
  '/labs': 'Clinical Lab Interpretation',
  '/profile': 'Patient Profile & Episode Baseline',
};

export const Header = () => {
  const { logout } = useAuth();
  const location = useLocation();

  const currentTitle = ROUTE_LABELS[location.pathname] || (
    location.pathname.startsWith('/documents/') ? 'Document Inspection' : 'CareThread Portal'
  );

  return (
    <header className="app-topbar">
      <div className="topbar-left">
        <div className="topbar-breadcrumb">
          <span>CareThread</span>
          <span style={{ color: 'var(--ct-text-muted)' }}>/</span>
          <span className="active-crumb">{currentTitle}</span>
        </div>
      </div>

      <div className="topbar-right">
        {location.pathname !== '/documents' && (
          <Link
            to="/documents"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'var(--ct-surface-elevated)',
              color: 'var(--ct-text-primary)',
              border: '1px solid var(--ct-border)',
              padding: '6px 12px',
              borderRadius: 'var(--ct-radius-md)',
              fontSize: '12.5px',
              fontWeight: 500,
              textDecoration: 'none',
              transition: 'all var(--ct-transition-fast)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>Upload Document</span>
          </Link>
        )}

        <button
          onClick={logout}
          className="btn-signout"
          title="Sign out of CareThread"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          <span>Sign Out</span>
        </button>
      </div>
    </header>
  );
};
