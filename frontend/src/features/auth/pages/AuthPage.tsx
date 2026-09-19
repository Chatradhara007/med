import { useAuth } from '../../../app/auth/AuthContext';
import { Navigate } from 'react-router-dom';

export const AuthPage = () => {
  const { login, isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <div style={{ padding: '20px' }}>Loading...</div>;
  if (isAuthenticated) return <Navigate to="/" replace />;

  const isMock = import.meta.env.VITE_USE_MOCK_API !== 'false';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#f8fafc' }}>
      <h1 style={{ color: '#1e293b', marginBottom: '8px' }}>CareThread</h1>
      <p style={{ color: '#64748b', marginBottom: '32px' }}>Secure Patient Portal</p>
      
      <button 
        onClick={login}
        style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', fontSize: '1rem', fontWeight: 600, cursor: 'pointer' }}
      >
        {isMock ? 'Mock Login (Development)' : 'Sign In with AWS Cognito'}
      </button>

      {isMock && (
        <p style={{ marginTop: '24px', color: '#94a3b8', fontSize: '0.85rem' }}>
          Running in Mock API mode.
        </p>
      )}
    </div>
  );
};
