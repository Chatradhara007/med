import { Link } from 'react-router-dom';
import type { DocumentMetadata } from '../../../types/api';

interface Props {
  documents?: DocumentMetadata[];
}

export const RecordsSummary = ({ documents }: Props) => {
  if (!documents) return null;

  return (
    <section className="profile-card records-summary-card">
      <h3>My Records</h3>
      <p className="records-count">{documents.length} recent documents</p>
      
      {documents.length > 0 && (
        <ul className="recent-docs-list">
          {documents.map(doc => (
            <li key={doc.id}>
              <Link to={`/documents/${doc.id}`} className="doc-link">
                📄 {doc.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
      
      <Link to="/documents" className="view-all-btn">
        View all documents
      </Link>
    </section>
  );
};
