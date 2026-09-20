import { useEffect, useState } from 'react';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { updateRecordField } from '../../../api/record';
import { PatientInfoCard } from '../components/PatientInfoCard';
import { MedicationList } from '../components/MedicationList';
import { RecordsSummary } from '../components/RecordsSummary';
import { PreferencesCard } from '../components/PreferencesCard';
import '../Patient.css';

// Fields editable via PATCH /record/field with SK = PROFILE
const PROFILE_FIELDS: Array<{ key: string; label: string; type?: string }> = [
  { key: 'name', label: 'Full Name' },
  { key: 'age', label: 'Age', type: 'number' },
  { key: 'sex', label: 'Sex' },
  { key: 'language', label: 'Language' },
  { key: 'phone', label: 'Phone' },
];

export const ProfilePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Profile completion form state
  const [profileForm, setProfileForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const fetchProfile = async () => {
    try {
      setError(null);
      const data = await getRecord();
      setRecord(data);
      // Pre-fill form from existing patient data
      setProfileForm({
        name: data.patient.name || '',
        age: data.patient.age != null ? String(data.patient.age) : '',
        sex: data.patient.sex || '',
        language: data.patient.language || '',
        phone: data.patient.phone || '',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load patient profile.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile(); // eslint-disable-line react-hooks/set-state-in-effect
  }, []);

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setSaveError(null);

      // Send one PATCH /record/field per changed field
      const changedFields = PROFILE_FIELDS.filter((f) => {
        const current = String(
          f.key === 'age'
            ? (record?.patient.age ?? '')
            : record?.patient[f.key as keyof typeof record.patient] ?? ''
        );
        return profileForm[f.key] !== current && profileForm[f.key] !== '';
      });

      await Promise.all(
        changedFields.map((f) =>
          updateRecordField({
            sk: 'PROFILE',
            field: f.key,
            value: f.type === 'number' ? Number(profileForm[f.key]) : profileForm[f.key],
          })
        )
      );

      setSaved(true);
      await fetchProfile();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading-state">Loading profile...</div>;
  if (error || !record) return <div className="error-state">{error || 'Not found'}</div>;

  return (
    <div className="profile-page">
      <header className="profile-header">
        <h1>My Profile</h1>
      </header>

      <div className="profile-content">
        {!record.profile_complete && (
          <section className="profile-card profile-incomplete-card">
            <h3>⚠️ Complete your profile</h3>
            <p>Please fill in your details to activate your care plan and personalised features.</p>

            <form className="profile-completion-form" onSubmit={handleProfileSave}>
              {PROFILE_FIELDS.map((f) => (
                <div key={f.key} className="profile-field-group">
                  <label>{f.label}</label>
                  <input
                    type={f.type || 'text'}
                    value={profileForm[f.key] || ''}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  />
                </div>
              ))}

              {saveError && <div className="review-error">{saveError}</div>}
              {saved && <div className="save-success">Profile saved successfully.</div>}

              <button type="submit" className="btn-confirm" disabled={saving}>
                {saving ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          </section>
        )}

        <PatientInfoCard patient={record.patient} />

        {record.profile_complete && (
          <section className="profile-card profile-edit-card">
            <h3>Edit Profile</h3>
            <form className="profile-completion-form" onSubmit={handleProfileSave}>
              {PROFILE_FIELDS.map((f) => (
                <div key={f.key} className="profile-field-group">
                  <label>{f.label}</label>
                  <input
                    type={f.type || 'text'}
                    value={profileForm[f.key] || ''}
                    onChange={(e) => setProfileForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  />
                </div>
              ))}

              {saveError && <div className="review-error">{saveError}</div>}
              {saved && <div className="save-success">Profile updated.</div>}

              <div className="review-actions">
                <button type="submit" className="btn-confirm" disabled={saving}>
                  {saving ? 'Saving...' : 'Update Profile'}
                </button>
              </div>
            </form>
          </section>
        )}

        <MedicationList medications={record.activeMedications} />

        <RecordsSummary documents={record.recentDocuments} />

        <PreferencesCard />
      </div>
    </div>
  );
};
