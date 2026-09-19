import { Link } from 'react-router-dom';
import type { DocumentMetadata } from '../../../types/api';
import { ProcessingStatus } from './ProcessingStatus';

interface Props {
  document: DocumentMetadata;
}

export const DocumentCard = ({ document }: Props) => {
  const dateStr = new Date(document.uploadedAt).toLocaleDateString();

  return (
    <Link to={`/documents/${document.id}`} className="document-card">
      <div className="doc-card-main">
        <div className="doc-icon">📄</div>
        <div className="doc-card-info">
          <h4>{document.name}</h4>
          <p>{dateStr} • {document.type}</p>
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
