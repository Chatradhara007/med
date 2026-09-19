import { useEffect, useState } from 'react';
import type { PatientRecord } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { markPlanDone } from '../../../api/plan';
import { AlertCard } from '../components/AlertCard';
import { TimelineDay } from '../components/TimelineDay';
import { RecentDocumentCard } from '../components/RecentDocumentCard';
import '../Timeline.css';

export const TimelinePage = () => {
  const [record, setRecord] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRecord = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      const data = await getRecord();
      setRecord(data);
    } catch (err) {
      console.error('Failed to load record', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRecord();
  }, []);

  const handleMarkDone = async (id: string) => {
    try {
      await markPlanDone(id);
      // Re-fetch record to get updated state
      loadRecord();
    } catch (err) {
      console.error('Failed to mark done', err);
    }
  };

  if (loading) return <div className="loading">Loading timeline...</div>;
  if (!record) return <div className="error">Failed to load data</div>;

  // Group care plan items by day
  const groupedItems = record.carePlan.reduce((acc, item) => {
    if (!acc[item.day]) acc[item.day] = [];
    acc[item.day].push(item);
    return acc;
  }, {} as Record<string, typeof record.carePlan>);

  return (
    <div className="timeline-page">
      <header className="patient-greeting">
        <h2>Hello, {record.patient.name}</h2>
      </header>

      {record.alerts.length > 0 && (
        <section className="alerts-section">
          {record.alerts.map(alert => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </section>
      )}

      <section className="care-plan-section">
        {Object.entries(groupedItems).map(([day, items]) => (
          <TimelineDay key={day} day={day} items={items} onMarkDone={handleMarkDone} />
        ))}
      </section>

      {record.recentDocuments.length > 0 && (
        <section className="documents-section">
          <h3>Recent Documents</h3>
          {record.recentDocuments.map(doc => (
            <RecentDocumentCard key={doc.id} document={doc} />
          ))}
        </section>
      )}
    </div>
  );
};
