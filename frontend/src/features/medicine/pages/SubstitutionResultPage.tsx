import { useLocation, Link, Navigate } from 'react-router-dom';
import type { SubstitutionResponse } from '../../../types/api';
import { AlternativeCard } from '../components/AlternativeCard';
import { BlockedSubstitution } from '../components/BlockedSubstitution';
import '../Medicine.css';

export const SubstitutionResultPage = () => {
  const location = useLocation();
  const result = location.state?.result as SubstitutionResponse | undefined;

  if (!result) {
    return <Navigate to="/medicine" replace />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <div>
        <Link
          to="/medicine"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--ct-text-muted)',
            fontSize: '13px',
            textDecoration: 'none',
            marginBottom: '12px',
          }}
        >
          ← Back to Medication Scanner
        </Link>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)', margin: 0 }}>
          Substitution &amp; Safety Analysis
        </h1>
        <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '4px', maxWidth: '650px', lineHeight: 1.5 }}>
          Bioequivalence evaluation, Narrow Therapeutic Index safety check, and cross-reference against active medications.
        </p>
      </div>

      {result.blocked ? (
        <BlockedSubstitution reason={result.reason || 'Safety rail prevented automatic substitution.'} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Interaction Warnings */}
          {result.interactions.length > 0 && (
            <div
              style={{
                padding: '20px',
                backgroundColor: 'var(--ct-review-bg)',
                border: '1px solid var(--ct-review-border)',
                borderRadius: 'var(--ct-radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>⚠️</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--ct-review)' }}>
                  Potential Drug Interactions Detected ({result.interactions.length})
                </h3>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {result.interactions.map((warning, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '10px 14px',
                      backgroundColor: 'rgba(0, 0, 0, 0.2)',
                      borderRadius: 'var(--ct-radius-sm)',
                      borderLeft: '3px solid var(--ct-review)',
                      fontSize: '13.5px',
                      color: 'var(--ct-text-primary)',
                      lineHeight: 1.45,
                    }}
                  >
                    {warning}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alternatives Section */}
          <section className="ct-card">
            <div className="ct-card-header">
              <div>
                <h2 className="ct-card-title">
                  <span>Bioequivalent Substitution Options</span>
                </h2>
                <p style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
                  {result.alternatives.length} verified bioequivalent alternative{result.alternatives.length > 1 ? 's' : ''} available in pharmacy formulary
                </p>
              </div>
            </div>

            {result.alternatives.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px 20px', color: 'var(--ct-text-muted)' }}>
                <p style={{ fontSize: '13.5px', margin: 0 }}>
                  No bioequivalent alternatives were found matching the exact salt and dosage profile.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {result.alternatives.map((alt, i) => (
                  <AlternativeCard key={i} alternative={alt} />
                ))}
              </div>
            )}
          </section>

          {/* Clinical Advisory Banner */}
          <div
            style={{
              padding: '18px 24px',
              backgroundColor: 'var(--ct-surface)',
              border: '1px solid var(--ct-border)',
              borderRadius: 'var(--ct-radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
            }}
          >
            <span style={{ fontSize: '24px' }}>🛡️</span>
            <div>
              <strong style={{ color: 'var(--ct-text-primary)', fontSize: '13.5px', display: 'block', marginBottom: '2px' }}>
                Advisory Only — Consult Pharmacist Before Switching
              </strong>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--ct-text-muted)', lineHeight: 1.5 }}>
                CareThread checks drug databases for equivalence and known interactions. It does not replace clinical consultation. Always confirm medication adjustments with a licensed medical professional.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
