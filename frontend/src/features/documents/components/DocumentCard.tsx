import { Link } from 'react-router-dom';
import type { DocumentMetadata } from '../../../types/api';
import { ProcessingStatus } from './ProcessingStatus';

interface Props {
  document: DocumentMetadata;
}

export const DocumentCard = ({ document }: Props) => {
  const dateStr = document.updated_at || document.created_at
    ? new Date(document.updated_at || document.created_at || '').toLocaleDateString()
    : 'Unknown date';

  // Display name: use type if available, otherwise fall back to doc_id
  const displayName = document.type
    ? document.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : `Document ${document.id}`;

  return (
    <Link to={`/documents/${document.id}`} className="document-card">
      <div className="doc-card-main">
        <div className="doc-icon">📄</div>
        <div className="doc-card-info">
          <h4>{displayName}</h4>
          <p>{dateStr}</p>
        </div>
      </div>
      <div className="doc-card-status">
        <ProcessingStatus status={document.status} />
      </div>
      {document.errorReason && (
        <div className="doc-card-error">
          <small>Reason: {document.errorReason}</small>
        </div>
      )}
    </Link>
  );
};
