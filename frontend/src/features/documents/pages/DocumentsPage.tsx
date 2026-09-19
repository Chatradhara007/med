import { useEffect, useState } from 'react';
import type { DocumentMetadata } from '../../../types/api';
import { getDocuments } from '../../../api/documents';
import { DocumentCard } from '../components/DocumentCard';
import { UploadDocument } from '../components/UploadDocument';
import '../Documents.css';

export const DocumentsPage = () => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const docs = await getDocuments();
      // Sort newest first
      docs.sort((a, b) => new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime());
      setDocuments(docs);
    } catch {
      setError('Failed to load medical records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDocuments(true);
    
    // Auto-poll to show state transitions from uploaded -> processing -> ready
    const intervalId = setInterval(() => {
      fetchDocuments(false);
    }, 2000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="documents-page">
      <h2>Medical Records</h2>
      
      <section className="upload-section">
        <UploadDocument onUploadStarted={() => fetchDocuments(false)} />
      </section>

      {loading && <div className="loading">Loading records...</div>}
      {error && <div className="error-message">{error}</div>}

      {!loading && !error && documents.length === 0 && (
        <div className="empty-state">
          <h3>No medical records yet</h3>
          <p>Please upload a document above to get started.</p>
        </div>
      )}

      {!loading && documents.length > 0 && (
        <section className="document-list">
          {documents.map(doc => (
            <DocumentCard key={doc.id} document={doc} />
          ))}
        </section>
      )}
    </div>
  );
};
