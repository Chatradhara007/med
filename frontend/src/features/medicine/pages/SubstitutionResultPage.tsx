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
    <div className="substitution-result-page">
      <div className="result-nav">
        <Link to="/medicine" className="back-link">← New Scan</Link>
      </div>

      {result.blocked ? (
        <BlockedSubstitution reason={result.reason || 'Substitution not available.'} />
      ) : (
        <>
          {result.interactions.length > 0 && (
            <section className="interactions-section">
              <h3>⚠️ Interaction Warnings</h3>
              <div className="interactions-list">
                {result.interactions.map((warning, i) => (
                  <div key={i} className="interaction-warning high">
                    <div className="warn-header">
                      <span className="warn-icon">⚠</span>
                      <strong>Interaction Warning</strong>
                    </div>
                    <p className="warn-message">{warning}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="alternatives-section">
            <h3>Substitution Options</h3>
            {result.alternatives.length === 0 ? (
              <p className="no-alternatives">No alternatives found for this medicine.</p>
            ) : (
              <>
                <p className="alt-subtitle">✓ {result.alternatives.length} alternative{result.alternatives.length > 1 ? 's' : ''} available</p>
                <div className="alternatives-list">
                  {result.alternatives.map((alt, i) => (
                    <AlternativeCard key={i} alternative={alt} />
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      )}

      <div className="advisory-banner">
        <strong>IMPORTANT</strong>
        <p>Do not change your medication based only on this result. Ask your pharmacist or clinician before switching medicines.</p>
      </div>
    </div>
  );
};
