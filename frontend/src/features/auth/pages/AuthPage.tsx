import { useAuth } from '../../../app/auth/AuthContext';
import { Navigate } from 'react-router-dom';

export const AuthPage = () => {
  const { login, isAuthenticated, isLoading, authError } = useAuth();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', width: '100%', backgroundColor: 'var(--ct-canvas)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div className="brand-icon" style={{ width: '40px', height: '40px', fontSize: '18px' }}>CT</div>
          <span style={{ color: 'var(--ct-text-secondary)', fontSize: '14px' }}>Connecting to CareThread...</span>
        </div>
      </div>
    );
  }

  if (isAuthenticated) return <Navigate to="/" replace />;

  return (
    <div className="auth-container">
      {/* Left Column: Clinical Platform Positioning */}
      <div className="auth-left-pane">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', zIndex: 1 }}>
          <div className="brand-icon" style={{ width: '36px', height: '36px', fontSize: '16px' }}>CT</div>
          <span style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)' }}>CareThread</span>
          <span style={{ marginLeft: '6px', fontSize: '11px', fontWeight: 600, color: '#38bdf8', backgroundColor: 'var(--ct-processing-bg)', padding: '2px 8px', borderRadius: 'var(--ct-radius-pill)', border: '1px solid var(--ct-processing-border)' }}>
            PATIENT EPISODE PORTAL
          </span>
        </div>

        <div style={{ maxWidth: '560px', zIndex: 1, margin: '40px 0' }}>
          <h1 style={{ fontSize: '2.3rem', fontWeight: 800, lineHeight: 1.18, letterSpacing: '-0.03em', color: 'var(--ct-text-primary)', marginBottom: '18px' }}>
            A unified clinical record for one episode of care.
          </h1>
          <p style={{ fontSize: '1.05rem', lineHeight: 1.65, color: 'var(--ct-text-secondary)', marginBottom: '28px' }}>
            Discharge summaries, outpatient lab reports, and pharmacy encounters treated as one connected episode belonging to one person in the same week.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
            <div style={{ padding: '14px', backgroundColor: 'var(--ct-surface-subtle)', borderRadius: 'var(--ct-radius-md)', border: '1px solid var(--ct-border-subtle)' }}>
              <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#10b981' }}>✓</span> 100% Sourced Values
              </div>
              <p style={{ fontSize: '12px', color: 'var(--ct-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Every extracted medication, dosage, and lab is anchored to exact coordinates on the source document.
              </p>
            </div>

            <div style={{ padding: '14px', backgroundColor: 'var(--ct-surface-subtle)', borderRadius: 'var(--ct-radius-md)', border: '1px solid var(--ct-border-subtle)' }}>
              <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#38bdf8' }}>✓</span> Multimodal Vision Pipeline
              </div>
              <p style={{ fontSize: '12px', color: 'var(--ct-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Rasterised multi-page document parsing with automated schema validation and confidence gating.
              </p>
            </div>

            <div style={{ padding: '14px', backgroundColor: 'var(--ct-surface-subtle)', borderRadius: 'var(--ct-radius-md)', border: '1px solid var(--ct-border-subtle)' }}>
              <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#f59e0b' }}>✓</span> Clinical Safety Rails
              </div>
              <p style={{ fontSize: '12px', color: 'var(--ct-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Deterministic Narrow Therapeutic Index (NTI) drug block and advisory interaction checks.
              </p>
            </div>

            <div style={{ padding: '14px', backgroundColor: 'var(--ct-surface-subtle)', borderRadius: 'var(--ct-radius-md)', border: '1px solid var(--ct-border-subtle)' }}>
              <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#c084fc' }}>✓</span> Patient-Controlled Privacy
              </div>
              <p style={{ fontSize: '12px', color: 'var(--ct-text-muted)', lineHeight: 1.5, margin: 0 }}>
                Isolated AWS Cognito partition per patient identity with Zero PHI in external delivery paths.
              </p>
            </div>
          </div>
        </div>

        <div style={{ fontSize: '12px', color: 'var(--ct-text-muted)', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span>AWS Serverless</span>
          <span>•</span>
          <span>Groq / Claude Multimodal</span>
          <span>•</span>
          <span>Amazon Cognito JWT</span>
        </div>
      </div>

      {/* Right Column: Secure Portal Authentication */}
      <div className="auth-right-pane">
        <div style={{ width: '100%', maxWidth: '400px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ct-text-muted)' }}>
              Patient & Clinician Access
            </span>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--ct-text-primary)', marginTop: '4px', letterSpacing: '-0.02em' }}>
              Sign In to CareThread
            </h2>
            <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '6px', lineHeight: 1.5 }}>
              Authenticate securely via your healthcare organization's AWS Cognito provider to access your active episode.
            </p>
          </div>

          <div
            style={{
              padding: '24px',
              backgroundColor: 'var(--ct-surface-elevated)',
              border: '1px solid var(--ct-border)',
              borderRadius: 'var(--ct-radius-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <button
              onClick={login}
              className="btn-primary"
              style={{ width: '100%', padding: '13px 20px', fontSize: '14.5px', fontWeight: 600, letterSpacing: '-0.01em' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span>Continue with AWS Cognito</span>
            </button>

            {authError && (
              <div
                role="alert"
                style={{
                  padding: '10px 14px',
                  backgroundColor: 'var(--ct-blocked-bg)',
                  border: '1px solid var(--ct-blocked-border)',
                  borderRadius: 'var(--ct-radius-md)',
                  color: 'var(--ct-blocked)',
                  fontSize: '12.5px',
                  lineHeight: 1.4,
                  textAlign: 'center',
                }}
              >
                <strong>Sign-in failed:</strong> {authError}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--ct-border-subtle)' }} />
              <span style={{ fontSize: '11px', color: 'var(--ct-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Encrypted SSO</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--ct-border-subtle)' }} />
            </div>

            <div style={{ fontSize: '12px', color: 'var(--ct-text-secondary)', lineHeight: 1.5, textAlign: 'center' }}>
              Authentication uses OAuth 2.0 PKCE with short-lived tokens and secure presigned S3 URLs.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '11.5px', color: 'var(--ct-text-muted)' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--ct-confirmed)' }} />
            <span>HIPAA-Eligible Services • TLS 1.3 In-Flight Encryption</span>
          </div>
        </div>
      </div>
    </div>
  );
};
