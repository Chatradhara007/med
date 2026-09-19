import type { Patient } from '../../../types/api';

interface Props {
  patient: Patient;
}

export const PatientInfoCard = ({ patient }: Props) => {
  const formattedDob = new Date(patient.dob).toLocaleDateString('en-GB', { 
    day: 'numeric', month: 'long', year: 'numeric' 
  });

  return (
    <section className="profile-card patient-info-card">
      <div className="avatar-placeholder">{patient.name.charAt(0)}</div>
      <div className="patient-details">
        <h2>{patient.name}</h2>
        <div className="meta-grid">
          <div className="meta-item">
            <label>Date of birth</label>
            <span>{formattedDob}</span>
          </div>
          <div className="meta-item">
            <label>Patient ID</label>
            <span>{patient.id}</span>
          </div>
        </div>
      </div>
    </section>
  );
};
