import { useEffect, useState, useCallback } from 'react';
import type { DocumentMetadata } from '../../../types/api';
import { getRecord } from '../../../api/record';
import { getDocument, deleteDocument, TERMINAL_STATUSES } from '../../../api/documents';
import { DocumentCard } from '../components/DocumentCard';
import { UploadDocument } from '../components/UploadDocument';
import { CardSkeleton } from '../../../components/ui';
import '../Documents.css';

export const DocumentsPage = () => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<'all' | 'ready' | 'review' | 'processing'>('all');

  const fetchDocuments = useCallback(async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const record = await getRecord();
      const derivedDocs = record.recentDocuments.map((doc) => {
        if (doc.status === 'review_required') {
          const docMeds = record.activeMedications.filter((m) => m.provenance?.source?.doc_id === doc.id);
          const docDiags = record.diagnoses.filter((d) => d.provenance?.source?.doc_id === doc.id);
          const docLabs = record.labResults.filter((l) => l.provenance?.source?.doc_id === doc.id);

          const totalEntities = docMeds.length + docDiags.length + docLabs.length;
          const hasUnconfirmed = [...docMeds, ...docDiags, ...docLabs].some(
            (e) => e.provenance?.status === 'needs_review'
          );

          if (totalEntities > 0 && !hasUnconfirmed) {
            return { ...doc, status: 'ready' as const };
          }
        }
        return doc;
      });
      setDocuments(derivedDocs);
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

  const handleDeleteDocument = useCallback(async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setFeedbackMessage(`Document ${docId.slice(0, 8)} successfully removed from record.`);
      setTimeout(() => setFeedbackMessage(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete document.';
      setError(msg);
    }
  }, []);

  const handleUploadComplete = useCallback(async (docId: string) => {
    setPollingIds((prev) => new Set(prev).add(docId));
    fetchDocuments(false);

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

  const filteredDocs = documents.filter((doc) => {
    if (filter === 'ready') return doc.status === 'ready';
    if (filter === 'review') return doc.status === 'review_required' || doc.status === 'unsupported' || doc.status === 'failed';
    if (filter === 'processing') return !TERMINAL_STATUSES.has(doc.status);
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)', margin: 0 }}>
          Medical Documents Hub
        </h1>
        <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '4px', maxWidth: '650px', lineHeight: 1.5 }}>
          Upload and manage clinical discharge summaries, lab reports, prescriptions, and pharmacy strip photos. Every field extracted is linked directly to bounding-box coordinates on the document page.
        </p>
      </div>

      {/* Success Notification Banner */}
      {feedbackMessage && (
        <div
          style={{
            padding: '12px 18px',
            backgroundColor: 'var(--ct-confirmed-bg)',
            border: '1px solid var(--ct-confirmed-border)',
            borderRadius: 'var(--ct-radius-md)',
            color: 'var(--ct-confirmed)',
            fontSize: '13px',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <span>✓</span>
          <span>{feedbackMessage}</span>
        </div>
      )}

      {/* Upload Zone */}
      <UploadDocument onUploadComplete={handleUploadComplete} />

      {/* In-Flight Pipeline Banner */}
      {pollingIds.size > 0 && (
        <div
          style={{
            padding: '14px 20px',
            backgroundColor: 'var(--ct-primary-subtle)',
            border: '1px solid var(--ct-primary-border)',
            borderRadius: 'var(--ct-radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: '#60a5fa',
            fontSize: '13.5px',
            fontWeight: 500,
          }}
        >
          <span className="pulse-dot" />
          <span>
            Processing {pollingIds.size} document{pollingIds.size > 1 ? 's' : ''} through multimodal rasterise, classify, extract, and schema validation pipeline...
          </span>
        </div>
      )}

      {/* Filter Tabs & Count */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--ct-border)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {[
            { id: 'all', label: `All Documents (${documents.length})` },
            { id: 'ready', label: 'Confirmed' },
            { id: 'review', label: 'Needs Review / Issues' },
            { id: 'processing', label: 'In-Flight' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id as typeof filter)}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--ct-radius-md)',
                fontSize: '12.5px',
                fontWeight: 600,
                border: '1px solid',
                cursor: 'pointer',
                backgroundColor: filter === tab.id ? 'var(--ct-primary-subtle)' : 'transparent',
                borderColor: filter === tab.id ? 'var(--ct-primary-border)' : 'transparent',
                color: filter === tab.id ? '#60a5fa' : 'var(--ct-text-secondary)',
                transition: 'all var(--ct-transition-fast)',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button onClick={() => fetchDocuments(true)} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>
          ↻ Refresh List
        </button>
      </div>

      {/* Documents List */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : error ? (
        <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)' }}>
          <p style={{ color: 'var(--ct-blocked)', margin: 0 }}>{error}</p>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div
          className="ct-card"
          style={{
            textAlign: 'center',
            padding: '48px 24px',
            color: 'var(--ct-text-muted)',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>📂</div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--ct-text-primary)', margin: 0 }}>
            {filter === 'all' ? 'No medical documents added yet' : 'No documents match this filter'}
          </h3>
          <p style={{ fontSize: '13px', marginTop: '6px', maxWidth: '380px', margin: '6px auto 0' }}>
            {filter === 'all'
              ? 'Upload your first clinical record above to begin automatic entity extraction.'
              : 'Switch tabs or upload another document to see records.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredDocs.map((doc) => (
            <DocumentCard key={doc.id} document={doc} onDelete={handleDeleteDocument} />
          ))}
        </div>
      )}
    </div>
  );
};
