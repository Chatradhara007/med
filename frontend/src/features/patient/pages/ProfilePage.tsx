import { useEffect, useState } from 'react';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { PatientInfoCard } from '../components/PatientInfoCard';
import { CareEpisodeCard } from '../components/CareEpisodeCard';
import { MedicationList } from '../components/MedicationList';
import { AllergyCard } from '../components/AllergyCard';
import { CareTeamCard } from '../components/CareTeamCard';
import { RecordsSummary } from '../components/RecordsSummary';
import { PreferencesCard } from '../components/PreferencesCard';
import '../Patient.css';

export const ProfilePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await getRecord();
        setRecord(data);
      } catch {
        setError('Failed to load patient profile.');
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  if (loading) return <div className="loading-state">Loading profile...</div>;
  if (error || !record) return <div className="error-state">{error || 'Not found'}</div>;

  return (
    <div className="profile-page">
      <header className="profile-header">
        <h1>My Profile</h1>
      </header>

      <div className="profile-content">
        <PatientInfoCard patient={record.patient} />
        
        <CareEpisodeCard episode={record.currentEpisode} />
        
        <MedicationList medications={record.activeMedications} />
        
        <AllergyCard allergies={record.allergies} />
        
        <CareTeamCard team={record.careTeam} />
        
        <RecordsSummary documents={record.recentDocuments} />
        
        <PreferencesCard />
      </div>
    </div>
  );
};
