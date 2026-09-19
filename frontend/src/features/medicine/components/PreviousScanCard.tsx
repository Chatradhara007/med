import type { PreviousScanEntry } from '../../../types/api';

interface Props {
  scan: PreviousScanEntry;
}

export const PreviousScanCard = ({ scan }: Props) => {
  const dateStr = new Date(scan.date).toLocaleDateString();
  
  return (
    <div className="previous-scan-card">
      <div className="scan-main">
        <div className="scan-icon">🔍</div>
        <div className="scan-info">
          <h4>{scan.detectedName}</h4>
          <p>{dateStr}</p>
        </div>
      </div>
      <div className="scan-status">
        <span className={`scan-badge ${scan.status}`}>{scan.status}</span>
      </div>
    </div>
  );
};
