import { Link } from 'react-router-dom';
import type { DocumentMetadata  } from '../../../types/api';

interface Props {
  document: DocumentMetadata;
}

export const RecentDocumentCard = ({ document }: Props) => {
  return (
    <Link to={`/documents/${document.id}`} className="recent-document-card">
      <div className="doc-info">
        <h4>{document.name}</h4>
        <span className={`doc-status ${document.status}`}>{document.status}</span>
      </div>
    </Link>
  );
};
