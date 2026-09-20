import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PreviousScanEntry } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { PreviousScanCard } from '../components/PreviousScanCard';
import '../Medicine.css';

export const PreviousScansPage = () => {
  const [scans, setScans] = useState<PreviousScanEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchScans = async () => {
      try {
        // Derive previous scans from the canonical record.
        // GET /medicine/scans does not exist — filter record.documents by type.
        const record = await getRecord();
        const medicineScans: PreviousScanEntry[] = record.recentDocuments
          .filter((d) => d.type === 'medicine_strip')
          .map((d) => ({
            id: d.id,
            date: d.updated_at || d.created_at || new Date().toISOString(),
            status: d.status,
            type: d.type || 'medicine_strip',
          }));
        setScans(medicineScans);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to load previous scans.';
        setError(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchScans();
  }, []);

  return (
    <div className="previous-scans-page">
      <div className="result-nav">
        <Link to="/medicine" className="back-link">← Back to Scanner</Link>
      </div>
      <h2>Previous Scans</h2>

      {loading ? (
        <div className="loading">Loading history...</div>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : scans.length === 0 ? (
        <div className="empty-state">
          <p>No previous medicine scans found.</p>
          <p>Scan a medicine strip to get started.</p>
        </div>
      ) : (
        <div className="scans-list">
          {scans.map((scan) => (
            <PreviousScanCard key={scan.id} scan={scan} />
          ))}
        </div>
      )}
    </div>
  );
};
