import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { PreviousScanEntry } from '../../../types/api';
import { getPreviousScans } from '../../../api/medicine';
import { PreviousScanCard } from '../components/PreviousScanCard';
import '../Medicine.css';

export const PreviousScansPage = () => {
  const [scans, setScans] = useState<PreviousScanEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchScans = async () => {
      try {
        const data = await getPreviousScans();
        setScans(data);
      } catch (err) {
        console.error(err);
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
      ) : scans.length === 0 ? (
        <div className="empty-state">No previous scans found.</div>
      ) : (
        <div className="scans-list">
          {scans.map(scan => (
            <PreviousScanCard key={scan.id} scan={scan} />
          ))}
        </div>
      )}
    </div>
  );
};
