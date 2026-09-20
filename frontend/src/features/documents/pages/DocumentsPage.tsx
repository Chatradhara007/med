import { useEffect, useState, useCallback } from 'react';
import type { DocumentMetadata } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { getDocument, TERMINAL_STATUSES } from '../../../api/documents';
import { DocumentCard } from '../components/DocumentCard';
import { UploadDocument } from '../components/UploadDocument';
import '../Documents.css';

export const DocumentsPage = () => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Track doc IDs being polled after upload
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());

  const fetchDocuments = useCallback(async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const record = await getRecord();
      // Documents come from GET /record — already sorted by the adapter
      setDocuments(record.recentDocuments);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load medical records.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments(true); // eslint-disable-line react-hooks/set-state-in-effect
  }, [fetchDocuments]);

  /**
   * Called after a successful upload.
   * Polls GET /documents/{docId} for this specific document until terminal.
   */
  const handleUploadComplete = useCallback(async (docId: string) => {
    setPollingIds((prev) => new Set(prev).add(docId));
    // Immediately refresh the list to show the new document
    fetchDocuments(false);

    // Poll this doc until terminal status
    const poll = async () => {
      try {
        const doc = await getDocument(docId);
        setDocuments((prev) =>
          prev.map((d) => (d.id === docId ? { ...d, status: doc.status } : d))
        );
        if (!TERMINAL_STATUSES.has(doc.status)) {
          setTimeout(poll, 3000);
        } else {
          setPollingIds((prev) => {
            const next = new Set(prev);
            next.delete(docId);
            return next;
          });
          // Final refresh to get latest record state
          fetchDocuments(false);
        }
      } catch {
        setPollingIds((prev) => {
          const next = new Set(prev);
          next.delete(docId);
          return next;
        });
      }
    };
    setTimeout(poll, 3000);
  }, [fetchDocuments]);

  return (
    <div className="documents-page">
      <h2>Medical Records</h2>

      <section className="upload-section">
        <UploadDocument onUploadComplete={handleUploadComplete} />
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
          {documents.map((doc) => (
            <DocumentCard key={doc.id} document={doc} />
          ))}
        </section>
      )}

      {pollingIds.size > 0 && (
        <div className="polling-banner">
          <span className="spinner-small" />
          Processing {pollingIds.size} document{pollingIds.size > 1 ? 's' : ''}...
        </div>
      )}
    </div>
  );
};
