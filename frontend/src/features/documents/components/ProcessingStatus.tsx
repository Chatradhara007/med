import type { BackendDocumentStatus } from '../../../types/api';

interface Props {
  status: BackendDocumentStatus;
}

type StatusGroup = 'processing' | 'needs_review' | 'ready' | 'unsupported' | 'failed';

const STATUS_GROUP: Record<BackendDocumentStatus, StatusGroup> = {
  uploading: 'processing',
  uploaded: 'processing',
  rasterising: 'processing',
  classifying: 'processing',
  extracting: 'processing',
  validating: 'processing',
  review_required: 'needs_review',
  ready: 'ready',
  unsupported: 'unsupported',
  failed: 'failed',
};

const STATUS_LABEL: Record<BackendDocumentStatus, string> = {
  uploading: 'Uploading',
  uploaded: 'Uploaded',
  rasterising: 'Processing',
  classifying: 'Processing',
  extracting: 'Processing',
  validating: 'Validating',
  review_required: 'Needs Review',
  ready: 'Ready',
  unsupported: 'Unsupported',
  failed: 'Failed',
};

export const ProcessingStatus = ({ status }: Props) => {
  const group = STATUS_GROUP[status] || 'processing';
  const label = STATUS_LABEL[status] || status;

  return (
    <span className={`doc-status-badge ${group}`}>
      {label}
    </span>
  );
};
