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
          <div key={i} className="med-item">
            <div className="med-icon">💊</div>
            <div className="med-info">
              <strong>{med.name}</strong>
              <span>{med.strength} • {med.frequency}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
