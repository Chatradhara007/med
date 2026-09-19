import { useAuth } from '../../app/auth/AuthContext';

export const Header = () => {
  const { logout } = useAuth();

  return (
    <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px' }}>
      <h1 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>CareThread</h1>
      <button onClick={logout} style={{ background: 'none', border: '1px solid #cbd5e1', padding: '6px 12px', borderRadius: '6px', color: '#64748b', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 }}>
        Sign Out
      </button>
    </header>
  );
};
