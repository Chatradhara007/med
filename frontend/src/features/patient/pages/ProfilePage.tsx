import { useEffect, useState } from 'react';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { updateRecordField } from '../../../api/record';
import { PatientInfoCard } from '../components/PatientInfoCard';
import { MedicationList } from '../components/MedicationList';
import { RecordsSummary } from '../components/RecordsSummary';
import { PreferencesCard } from '../components/PreferencesCard';
import { CardSkeleton } from '../../../components/ui';
import '../Patient.css';

const PROFILE_FIELDS: Array<{ key: string; label: string; type?: string }> = [
  { key: 'name', label: 'Full Name' },
  { key: 'age', label: 'Age', type: 'number' },
  { key: 'sex', label: 'Sex' },
  { key: 'language', label: 'Preferred Language' },
  { key: 'phone', label: 'Contact Phone' },
];

export const ProfilePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [profileForm, setProfileForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const fetchProfile = async () => {
    try {
      setError(null);
      const data = await getRecord();
      setRecord(data);
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

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)' }}>
        <p style={{ color: 'var(--ct-blocked)', margin: 0 }}>{error || 'Patient profile not found.'}</p>
        <button onClick={fetchProfile} className="btn-primary" style={{ marginTop: '12px' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <div>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)', margin: 0 }}>
          Patient Profile &amp; Episode Baseline
        </h1>
        <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '4px', maxWidth: '650px', lineHeight: 1.5 }}>
          Manage your verified personal demographics, emergency contact phone, active medications, and notification preferences.
        </p>
      </div>

      <PatientInfoCard patient={record.patient} />

      {/* Profile Edit Form */}
      <section className="ct-card">
        <div className="ct-card-header">
          <div>
            <h2 className="ct-card-title">
              <span>{record.profile_complete ? 'Update Profile Details' : '⚠️ Complete Profile Setup'}</span>
            </h2>
            <p style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
              Changes are saved to your isolated DynamoDB partition via secure field patch.
            </p>
          </div>
        </div>

        <form onSubmit={handleProfileSave} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            {PROFILE_FIELDS.map((f) => (
              <div key={f.key}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--ct-text-secondary)', marginBottom: '6px' }}>
                  {f.label}
                </label>
                <input
                  type={f.type || 'text'}
                  className="ct-input"
                  value={profileForm[f.key] || ''}
                  onChange={(e) => setProfileForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                />
              </div>
            ))}
          </div>

          {saveError && (
            <div style={{ color: 'var(--ct-blocked)', fontSize: '13px', backgroundColor: 'var(--ct-blocked-bg)', padding: '8px 14px', borderRadius: 'var(--ct-radius-sm)' }}>
              {saveError}
            </div>
          )}

          {saved && (
            <div style={{ color: 'var(--ct-confirmed)', fontSize: '13px', backgroundColor: 'var(--ct-confirmed-bg)', padding: '8px 14px', borderRadius: 'var(--ct-radius-sm)' }}>
              ✓ Profile saved successfully.
            </div>
          )}

          <div>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : record.profile_complete ? 'Update Profile Baseline' : 'Save & Activate Care Plan'}
            </button>
          </div>
        </form>
      </section>

      <MedicationList medications={record.activeMedications} />

      <RecordsSummary documents={record.recentDocuments} />

      <PreferencesCard />
    </div>
  );
};
