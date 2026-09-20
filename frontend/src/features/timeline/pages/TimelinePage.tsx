import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { markPlanDone, generateCarePlan } from '../../../api/plan';
import { AlertCard } from '../components/AlertCard';
import { TimelineDay } from '../components/TimelineDay';
import { RecentDocumentCard } from '../components/RecentDocumentCard';
import '../Timeline.css';

export const TimelinePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

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
    try {
      await markPlanDone(dayIndex, slot);
      loadRecord();
    } catch (err) {
      console.error('Failed to mark done', err);
    }
  };

  const handleGeneratePlan = async () => {
    try {
      setGenerating(true);
      await generateCarePlan();
      await loadRecord();
    } catch (err) {
      console.error('Failed to generate care plan', err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="loading">Loading timeline...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!record) return <div className="error">Failed to load data</div>;

  // If profile is not complete, show a prompt
  if (!record.profile_complete) {
    return (
      <div className="timeline-page">
        <header className="patient-greeting">
          <h2>Hello, {record.patient.name || 'Patient'}</h2>
        </header>
        <div className="profile-incomplete-banner">
          <h3>Complete your profile</h3>
          <p>Please complete your health profile to enable your care plan and personalized features.</p>
          <Link to="/profile" className="btn-complete-profile">Complete Profile →</Link>
        </div>
      </div>
    );
  }

  // Group care plan items by day_index
  const groupedItems = record.carePlan.reduce((acc, item) => {
    const key = item.day_index;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {} as Record<number, typeof record.carePlan>);

  const sortedDays = Object.keys(groupedItems).map(Number).sort((a, b) => a - b);

  return (
    <div className="timeline-page">
      <header className="patient-greeting">
        <h2>Hello, {record.patient.name}</h2>
      </header>

      {record.alerts.length > 0 && (
        <section className="alerts-section">
          {record.alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </section>
      )}

      <section className="care-plan-section">
        <div className="care-plan-header">
          <h3>Care Plan</h3>
          <button
            className="btn-generate-plan"
            onClick={handleGeneratePlan}
            disabled={generating}
          >
            {generating ? 'Generating...' : '↻ Generate Plan'}
          </button>
        </div>

        {sortedDays.length === 0 ? (
          <div className="empty-state">
            <p>No care plan entries yet.</p>
            <p>Click "Generate Plan" to create your personalised care schedule.</p>
          </div>
        ) : (
          sortedDays.map((dayIndex) => (
            <TimelineDay
              key={dayIndex}
              dayIndex={dayIndex}
              items={groupedItems[dayIndex]}
              onMarkDone={handleMarkDone}
            />
          ))
        )}
      </section>

      {record.recentDocuments.length > 0 && (
        <section className="documents-section">
          <h3>Recent Documents</h3>
          {record.recentDocuments.slice(0, 3).map((doc) => (
            <RecentDocumentCard key={doc.id} document={doc} />
          ))}
          <Link to="/documents" className="view-all-link">View all documents →</Link>
        </section>
      )}
    </div>
  );
};
