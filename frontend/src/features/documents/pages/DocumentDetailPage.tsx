import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { DocumentMetadata, SourceMetadata } from '../../../types/api';
import { getDocument } from '../../../api/documents';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { ExtractedFieldCard } from '../components/ExtractedFieldCard';
import { DocumentViewer } from '../components/DocumentViewer';
import '../Documents.css';

export const DocumentDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const [document, setDocument] = useState<DocumentMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFieldSk, setActiveFieldSk] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<SourceMetadata | null>(null);

  const fetchDocument = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const doc = await getDocument(id);
      setDocument(doc);
    } catch {
      setError('Failed to load document details or document not found.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetchDocument();
    
    const interval = setInterval(fetchDocument, 5000);
    return () => clearInterval(interval);
  }, [fetchDocument]);

  if (loading && !document) return <div className="loading">Loading document...</div>;
  if (error || !document) {
    return (
      <div className="document-detail-page">
        <Link to="/documents" className="back-link">← Back to Documents</Link>
        <div className="error-message">{error || 'Not found'}</div>
      </div>
    );
  }

  return (
    <div className="document-detail-page">
      <Link to="/documents" className="back-link">← Back to Documents</Link>
      
      <header className="doc-detail-header">
        <h2>{document.name}</h2>
        <div className="doc-meta">
          <ProcessingStatus status={document.status} />
          <span>{document.type}</span>
          <span>Uploaded: {new Date(document.uploadedAt).toLocaleDateString()}</span>
        </div>
      </header>
      
      {document.errorReason && (
        <div className="doc-detail-error">
          <p><strong>Processing Failed:</strong> {document.errorReason}</p>
        </div>
      )}

      {document.status === 'processing' && (
        <div className="doc-processing-banner">
          <p>We are currently extracting information from this document...</p>
        </div>
      )}

      <div className="doc-detail-content">
        <section className="doc-extracted-pane">
          <h3>Extracted Information</h3>
          {document.status === 'ready' ? (
             <div className="extracted-fields-list">
               {document.extractedData && document.extractedData.length > 0 ? (
                 document.extractedData.map(field => (
                   <ExtractedFieldCard 
                     key={field.sk} 
                     field={field} 
                     isActiveSource={activeFieldSk === field.sk}
                     onShowOriginal={(source) => { setActiveSource(source); setActiveFieldSk(field.sk); }}
                     onRefresh={fetchDocument}
                   />
                 ))
               ) : (
                 <p className="not-ready-text">No clinical entities were extracted from this document.</p>
               )}
             </div>
          ) : (
            <p className="not-ready-text">Extracted information will be available once processing completes.</p>
          )}
        </section>

        <section className="doc-original-pane">
          <h3>Original Document</h3>
          <DocumentViewer documentName={document.name} sourceHighlight={activeSource} />
        </section>
      </div>
    </div>
  );
};
