import type { PreviousScanEntry } from '../../../types/api';

interface Props {
  scan: PreviousScanEntry;
}

const STATUS_LABEL: Record<string, string> = {
  ready: 'Ready',
  failed: 'Failed',
  unsupported: 'Unsupported',
  review_required: 'Needs Review',
  uploading: 'Uploading',
  uploaded: 'Uploaded',
  rasterising: 'Processing',
  classifying: 'Processing',
  extracting: 'Processing',
  validating: 'Processing',
};

export const PreviousScanCard = ({ scan }: Props) => {
  const dateStr = new Date(scan.date).toLocaleDateString();
  const label = STATUS_LABEL[scan.status] || scan.status;
  const statusGroup = ['ready'].includes(scan.status) ? 'success'
    : ['failed', 'unsupported'].includes(scan.status) ? 'error'
    : 'processing';

  return (
    <div className="previous-scan-card">
      <div className="scan-main">
        <div className="scan-icon">🔍</div>
        <div className="scan-info">
          <h4>{scan.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</h4>
          <p>{dateStr}</p>
        </div>
      </div>
      <div className="scan-status">
        <span className={`scan-badge ${statusGroup}`}>{label}</span>
      </div>
    </div>
  );
};
