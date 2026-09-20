import type { MedicationValue } from '../../../types/api';

interface Props {
  medications?: MedicationValue[];
}

export const MedicationList = ({ medications }: Props) => {
  if (!medications || medications.length === 0) return null;

  return (
    <section className="profile-card med-list-card">
      <h3>Active Medications</h3>
      <div className="med-list">
        {medications.map((med, i) => (
          <div key={med.sk || i} className="med-item">
            <div className="med-icon">💊</div>
            <div className="med-info">
              <strong>{med.name}</strong>
              <span>
                {[med.strength, med.form, med.frequency ? `${med.frequency}` : null]
                  .filter(Boolean)
                  .join(' • ')}
              </span>
              {med.instructions && <small>{med.instructions}</small>}
              {med.salt && <small className="med-salt">{med.salt}</small>}
              {med.provenance?.status === 'needs_review' && (
                <span className="needs-review-badge">Needs Review</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
