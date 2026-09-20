import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { markPlanDone, generateCarePlan } from '../../../api/plan';
import { AlertCard } from '../components/AlertCard';
import { TimelineDay } from '../components/TimelineDay';
import { RecentDocumentCard } from '../components/RecentDocumentCard';
import { CardSkeleton } from '../../../components/ui';
import { ProvenanceChip } from '../../../components/ui/ProvenanceChip';
import '../Timeline.css';

export const TimelinePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [selectedDayTab, setSelectedDayTab] = useState<number | 'all'>('all');

  const loadRecord = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const data = await getRecord();
      setRecord(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load your health timeline.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecord(true); // eslint-disable-line react-hooks/set-state-in-effect
  }, []);

  const handleMarkDone = async (dayIndex: number, slot: string) => {
    // Optimistic UI update
    if (record) {
      const updatedPlan = record.carePlan.map((item) =>
        item.day_index === dayIndex && item.slot === slot
          ? { ...item, done: true, completed_at: new Date().toISOString() }
          : item
      );
      setRecord({ ...record, carePlan: updatedPlan });
    }

    try {
      await markPlanDone(dayIndex, slot);
      await loadRecord(false);
    } catch (err) {
      console.error('Failed to mark done', err);
      // Revert if error
      await loadRecord(false);
    }
  };

  const handleGeneratePlan = async () => {
    try {
      setGenerating(true);
      await generateCarePlan();
      await loadRecord(false);
    } catch (err) {
      console.error('Failed to generate care plan', err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="ct-card">
          <CardSkeleton />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
        <div className="ct-card">
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)', backgroundColor: 'var(--ct-surface)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--ct-blocked)' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Unable to load patient record</h3>
        </div>
        <p style={{ color: 'var(--ct-text-secondary)', marginTop: '8px', marginBottom: '16px' }}>{error}</p>
        <button onClick={() => loadRecord(true)} className="btn-primary">
          Retry Connection
        </button>
      </div>
    );
  }

  if (!record) return null;

  // Incomplete profile banner
  if (!record.profile_complete) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--ct-surface)',
            border: '1px solid var(--ct-review-border)',
            borderRadius: 'var(--ct-radius-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '20px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="ct-badge review">ACTION REQUIRED</span>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--ct-text-primary)' }}>
                Set Up Patient Baseline
              </h3>
            </div>
            <p style={{ color: 'var(--ct-text-secondary)', margin: 0, fontSize: '13.5px' }}>
              Complete the patient profile demographics to generate an automated 7-day care plan and enable drug-drug safety checks.
            </p>
          </div>
          <Link to="/profile" className="btn-primary" style={{ whiteSpace: 'nowrap' }}>
            Complete Profile →
          </Link>
        </div>
      </div>
    );
  }

  // Care plan groupings
  const groupedItems = record.carePlan.reduce((acc, item) => {
    const key = item.day_index;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {} as Record<number, typeof record.carePlan>);

  const sortedDays = Object.keys(groupedItems).map(Number).sort((a, b) => a - b);
  const totalTasks = record.carePlan.length;
  const completedTasks = record.carePlan.filter((i) => i.done).length;
  const adherenceRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Patient Header Banner */}
      <div
        className="ct-card"
        style={{
          background: 'linear-gradient(145deg, #0f172a 0%, #172554 100%)',
          borderColor: 'rgba(59, 130, 246, 0.25)',
          padding: '24px 28px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'white', margin: 0 }}>
                {record.patient.name}
              </h1>
              <span className="ct-badge confirmed" style={{ fontSize: '11px' }}>
                EPISODE BASELINE ACTIVE
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '13px', color: '#94a3b8' }}>
              {record.patient.age != null && <span>Age: <strong style={{ color: 'white' }}>{record.patient.age}</strong></span>}
              {record.patient.sex && <span>Sex: <strong style={{ color: 'white' }}>{record.patient.sex}</strong></span>}
              {record.patient.language && <span>Language: <strong style={{ color: 'white' }}>{record.patient.language}</strong></span>}
              <span>ID: <strong style={{ color: 'white', fontFamily: 'monospace' }}>{record.patient.id.slice(0, 8)}</strong></span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Link to="/documents" className="btn-primary" style={{ padding: '8px 16px', fontSize: '13px' }}>
              + Upload Document
            </Link>
          </div>
        </div>

        {/* Quick Episode Stat Metrics */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '12px',
            marginTop: '22px',
            paddingTop: '18px',
            borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <div>
            <div style={{ fontSize: '11.5px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Active Medications</div>
            <div className="tabular" style={{ fontSize: '1.4rem', fontWeight: 700, color: 'white', marginTop: '2px' }}>
              {record.activeMedications.length}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11.5px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Diagnoses</div>
            <div className="tabular" style={{ fontSize: '1.4rem', fontWeight: 700, color: 'white', marginTop: '2px' }}>
              {record.diagnoses.length}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11.5px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Plan Adherence</div>
            <div className="tabular" style={{ fontSize: '1.4rem', fontWeight: 700, color: adherenceRate >= 80 ? 'var(--ct-confirmed)' : '#60a5fa', marginTop: '2px' }}>
              {adherenceRate}%
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11.5px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Documents Ingested</div>
            <div className="tabular" style={{ fontSize: '1.4rem', fontWeight: 700, color: 'white', marginTop: '2px' }}>
              {record.recentDocuments.length}
            </div>
          </div>
        </div>
      </div>

      {/* Priority Alerts Section */}
      {record.alerts.length > 0 && (
        <section>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--ct-abnormal)' }} />
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
              Clinical Escalations & Alerts ({record.alerts.length})
            </h2>
          </div>
          <div>
            {record.alerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </div>
        </section>
      )}

      {/* Main Grid: Care Plan + Episode Narrative */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: '24px' }}>
        {/* Left Column: Today's Care Plan */}
        <section className="ct-card">
          <div className="ct-card-header">
            <div>
              <h2 className="ct-card-title">
                <span>Care Plan Schedule</span>
              </h2>
              <p style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
                7-day episode protocol generated from clinical baseline
              </p>
            </div>

            <button
              onClick={handleGeneratePlan}
              disabled={generating}
              className="btn-secondary"
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              {generating ? 'Re-compiling...' : '↻ Re-generate Plan'}
            </button>
          </div>

          {/* Day Navigation Filter */}
          {sortedDays.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', overflowX: 'auto', paddingBottom: '4px' }}>
              <button
                type="button"
                onClick={() => setSelectedDayTab('all')}
                style={{
                  padding: '5px 12px',
                  borderRadius: 'var(--ct-radius-md)',
                  fontSize: '12px',
                  fontWeight: 600,
                  border: '1px solid',
                  cursor: 'pointer',
                  backgroundColor: selectedDayTab === 'all' ? 'var(--ct-primary-subtle)' : 'transparent',
                  borderColor: selectedDayTab === 'all' ? 'var(--ct-primary-border)' : 'var(--ct-border-subtle)',
                  color: selectedDayTab === 'all' ? '#60a5fa' : 'var(--ct-text-secondary)',
                }}
              >
                All Days
              </button>
              {sortedDays.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setSelectedDayTab(d)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 'var(--ct-radius-md)',
                    fontSize: '12px',
                    fontWeight: 600,
                    border: '1px solid',
                    cursor: 'pointer',
                    backgroundColor: selectedDayTab === d ? 'var(--ct-primary-subtle)' : 'transparent',
                    borderColor: selectedDayTab === d ? 'var(--ct-primary-border)' : 'var(--ct-border-subtle)',
                    color: selectedDayTab === d ? '#60a5fa' : 'var(--ct-text-secondary)',
                  }}
                >
                  {d === 0 ? 'Today' : `Day ${d}`}
                </button>
              ))}
            </div>
          )}

          {sortedDays.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--ct-text-muted)' }}>
              <p style={{ fontSize: '14px', marginBottom: '12px' }}>No care plan entries yet for this episode.</p>
              <button onClick={handleGeneratePlan} disabled={generating} className="btn-primary">
                {generating ? 'Generating Schedule...' : 'Generate 7-Day Care Plan'}
              </button>
            </div>
          ) : (
            <div>
              {sortedDays
                .filter((d) => selectedDayTab === 'all' || selectedDayTab === d)
                .map((dayIndex) => (
                  <TimelineDay
                    key={dayIndex}
                    dayIndex={dayIndex}
                    items={groupedItems[dayIndex]}
                    onMarkDone={handleMarkDone}
                  />
                ))}
            </div>
          )}
        </section>

        {/* Right Column: Episode Context (Active Baseline & Documents) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Active Medications Baseline Card */}
          <section className="ct-card">
            <div className="ct-card-header">
              <h2 className="ct-card-title">
                <span>Active Medications ({record.activeMedications.length})</span>
              </h2>
              <Link to="/medicine" style={{ fontSize: '12px', color: '#60a5fa', textDecoration: 'none', fontWeight: 500 }}>
                Safety Checker →
              </Link>
            </div>

            {record.activeMedications.length === 0 ? (
              <p style={{ color: 'var(--ct-text-muted)', fontSize: '13px', margin: 0 }}>
                No active medications extracted yet. Upload a discharge summary or prescription to establish baseline.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {record.activeMedications.map((med, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '10px 14px',
                      backgroundColor: 'var(--ct-surface-elevated)',
                      borderRadius: 'var(--ct-radius-md)',
                      border: '1px solid var(--ct-border-subtle)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', fontSize: '13.5px' }}>
                        {med.name} {med.strength || ''}
                      </div>
                      <div style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)' }}>
                        {med.frequency || 'Daily'} {med.instructions ? `• ${med.instructions}` : ''}
                      </div>
                    </div>
                    {med.provenance?.source?.doc_id && (
                      <ProvenanceChip
                        docId={med.provenance.source.doc_id}
                        page={med.provenance.source.page}
                        confidence={med.provenance.confidence}
                        quote={med.provenance.source.verbatim}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Diagnoses Baseline Card */}
          <section className="ct-card">
            <div className="ct-card-header">
              <h2 className="ct-card-title">
                <span>Diagnoses Baseline ({record.diagnoses.length})</span>
              </h2>
            </div>

            {record.diagnoses.length === 0 ? (
              <p style={{ color: 'var(--ct-text-muted)', fontSize: '13px', margin: 0 }}>
                No clinical diagnoses recorded.
              </p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {record.diagnoses.map((diag, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: 'var(--ct-surface-elevated)',
                      border: '1px solid var(--ct-border)',
                      borderRadius: 'var(--ct-radius-md)',
                      fontSize: '12.5px',
                      color: 'var(--ct-text-primary)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <span style={{ fontWeight: 500 }}>{diag.condition}</span>
                    {diag.provenance?.source?.doc_id && (
                      <ProvenanceChip
                        docId={diag.provenance.source.doc_id}
                        page={diag.provenance.source.page}
                        confidence={diag.provenance.confidence}
                        quote={diag.provenance.source.verbatim}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Recent Ingested Documents */}
          <section className="ct-card">
            <div className="ct-card-header">
              <h2 className="ct-card-title">
                <span>Recent Documents</span>
              </h2>
              <Link to="/documents" style={{ fontSize: '12px', color: '#60a5fa', textDecoration: 'none', fontWeight: 500 }}>
                View All →
              </Link>
            </div>

            {record.recentDocuments.length === 0 ? (
              <p style={{ color: 'var(--ct-text-muted)', fontSize: '13px', margin: 0 }}>
                No clinical documents uploaded yet.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {record.recentDocuments.slice(0, 3).map((doc) => (
                  <RecentDocumentCard key={doc.id} document={doc} />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};
