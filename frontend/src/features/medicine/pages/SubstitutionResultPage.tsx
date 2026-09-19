import { useLocation, Link, Navigate } from 'react-router-dom';
import type { SubstitutionResponse } from '../../../types/api';
import { AlternativeCard } from '../components/AlternativeCard';
import { InteractionWarning } from '../components/InteractionWarning';
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

      {result.detected && (
        <section className="detected-section">
          <h3>Medicine Detected</h3>
          <div className="detected-card">
            <h4>{result.detected.brand}</h4>
            <p>{result.detected.generic}</p>
            <p className="strength">{result.detected.strength}</p>
          </div>
        </section>
      )}

      {result.blocked ? (
        <BlockedSubstitution reason={result.reason || 'Unknown reason'} />
      ) : (
        <>
          {result.interactions.length > 0 && (
            <section className="interactions-section">
              <h3>Interactions</h3>
              {result.interactions.map((warn, i) => (
                <InteractionWarning key={i} interaction={warn} />
              ))}
            </section>
          )}

          <section className="alternatives-section">
            <h3>Substitution</h3>
            <p className="alt-subtitle">✓ Alternatives available</p>
            
            <div className="alternatives-list">
              {result.alternatives.map((alt, i) => (
                <AlternativeCard key={i} alternative={alt} />
              ))}
            </div>
          </section>
        </>
      )}

      <div className="advisory-banner">
        <strong>IMPORTANT</strong>
        <p>Do not change your medication based only on this result. Ask your pharmacist or clinician.</p>
      </div>
    </div>
  );
};
