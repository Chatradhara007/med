import type { Patient } from '../../../types/api';

interface Props {
  patient: Patient;
}

export const PatientInfoCard = ({ patient }: Props) => {
  return (
    <section className="profile-card patient-info-card">
      <div className="avatar-placeholder">{patient.name.charAt(0)}</div>
      <div className="patient-details">
        <h2>{patient.name}</h2>
        <div className="meta-grid">
          <div className="meta-item">
            <label>Patient ID</label>
            <span>{patient.id}</span>
          </div>
          {patient.age != null && (
            <div className="meta-item">
              <label>Age</label>
              <span>{patient.age} years</span>
            </div>
          )}
          {patient.sex && (
            <div className="meta-item">
              <label>Sex</label>
              <span>{patient.sex}</span>
            </div>
          )}
          {patient.language && (
            <div className="meta-item">
              <label>Language</label>
              <span>{patient.language}</span>
            </div>
          )}
          {patient.phone && (
            <div className="meta-item">
              <label>Phone</label>
              <span>{patient.phone}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
