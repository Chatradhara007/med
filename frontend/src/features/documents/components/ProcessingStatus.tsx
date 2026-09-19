import type { DocumentMetadata } from '../../../types/api';

interface Props {
  status: DocumentMetadata['status'];
}

export const ProcessingStatus = ({ status }: Props) => {
  const statusLabels = {
    uploaded: 'Uploaded',
    processing: 'Processing',
    ready: 'Ready',
    failed: 'Failed'
  };

  return (
    <span className={`doc-status-badge ${status}`}>
      {statusLabels[status]}
    </span>
  );
};
