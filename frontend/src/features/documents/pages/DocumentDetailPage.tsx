import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import type {
  DocumentMetadata,
  SourceMetadata,
  ExtractedField,
  PatientRecord,
} from '../../../types/api';
import { getDocument, deleteDocument, TERMINAL_STATUSES } from '../../../api/documents';
import { getRecord } from '../../../api/record';
import { ExtractedFieldCard } from '../components/ExtractedFieldCard';
import { DocumentViewer } from '../components/DocumentViewer';
import { CardSkeleton } from '../../../components/ui';
import '../Documents.css';

function normaliseKeyPart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

function medicationSk(name: string): string {
  return `MED#${normaliseKeyPart(name)}`;
}

function diagnosisSk(codeOrSlug: string | undefined, label: string): string {
  return `DIAG#${normaliseKeyPart(codeOrSlug || label)}`;
}

function buildExtractedFields(
  record: PatientRecord,
  docId: string
): ExtractedField<Record<string, unknown>>[] {
  const fields: ExtractedField<Record<string, unknown>>[] = [];

  for (const med of record.activeMedications) {
    if (med.provenance?.source.doc_id !== docId) continue;
    fields.push({
      sk: med.sk || medicationSk(med.name),
      category: 'medication',
      value: {
        name: med.name,
        salt: med.salt,
        strength: med.strength,
        form: med.form,
        frequency: med.frequency,
        duration: med.duration,
        instructions: med.instructions,
        status: med.status,
      },
      source: med.provenance.source as SourceMetadata,
      confidence: med.provenance.confidence,
      status: med.provenance.status,
    });
  }

  for (const diag of record.diagnoses) {
    if (diag.provenance?.source.doc_id !== docId) continue;
    fields.push({
      sk: diag.sk || diagnosisSk(diag.code_or_slug, diag.condition),
      category: 'diagnosis',
      value: {
        condition: diag.condition,
        code_or_slug: diag.code_or_slug,
        icd10: diag.icd10,
        status: diag.status,
        notes: diag.notes,
        display_name: diag.display_name,
      },
      source: diag.provenance.source as SourceMetadata,
      confidence: diag.provenance.confidence,
      status: diag.provenance.status,
    });
  }

  for (const lab of record.labResults) {
    if (lab.provenance?.source.doc_id !== docId) continue;
    fields.push({
      sk: lab.sk || `lab_${lab.test}`,
      category: 'lab_result',
      value: {
        test: lab.test,
        value: lab.value,
        unit: lab.unit,
        ref_low: lab.ref_low,
        ref_high: lab.ref_high,
        flag: lab.flag,
      },
      source: lab.provenance.source as SourceMetadata,
      confidence: lab.provenance.confidence,
      status: lab.provenance.status,
    });
  }

  return fields;
}

export const DocumentDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentMetadata | null>(null);
  const [extractedFields, setExtractedFields] = useState<ExtractedField<Record<string, unknown>>[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<SourceMetadata | null>(null);
  const [activeFieldSk, setActiveFieldSk] = useState<string | null>(null);

  const handleDelete = async () => {
    const confirmed = window.confirm(
      'Are you sure you want to delete this document? This will remove the file and associated clinical extractions.'
    );
    if (!confirmed || !id) return;
    try {
      setIsDeleting(true);
      await deleteDocument(id);
      navigate('/documents');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete document';
      alert(msg);
      setIsDeleting(false);
    }
  };

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const [doc, record] = await Promise.all([getDocument(id), getRecord()]);
      const fields = buildExtractedFields(record, id);

      if (doc.status === 'review_required' && fields.length > 0) {
        const hasUnconfirmed = fields.some((f) => f.status === 'needs_review');
        if (!hasUnconfirmed) {
          doc.status = 'ready';
        }
      }

      setDocument(doc);
      setExtractedFields(fields);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load document.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    setLoading(true); // eslint-disable-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  // Poll until terminal status
  useEffect(() => {
    if (!document) return;
    if (TERMINAL_STATUSES.has(document.status)) return;

    const interval = setInterval(async () => {
      try {
        const doc = await getDocument(id!);
        if (TERMINAL_STATUSES.has(doc.status)) {
          clearInterval(interval);
          const record = await getRecord();
          const fields = buildExtractedFields(record, id!);
          if (doc.status === 'review_required' && fields.length > 0) {
            const hasUnconfirmed = fields.some((f) => f.status === 'needs_review');
            if (!hasUnconfirmed) {
              doc.status = 'ready';
            }
          }
          setDocument(doc);
          setExtractedFields(fields);
        } else {
          setDocument(doc);
        }
      } catch {
        clearInterval(interval);
      }
    }, 4000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document?.status, id]);

  if (loading && !document) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <CardSkeleton />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--ct-blocked)' }}>
          <h3>Unable to load document</h3>
        </div>
        <p style={{ color: 'var(--ct-text-secondary)', marginTop: '8px' }}>{error || 'Document not found'}</p>
        <Link to="/documents" className="btn-secondary" style={{ display: 'inline-flex', marginTop: '16px' }}>
          ← Back to Documents
        </Link>
      </div>
    );
  }

  const isProcessing = !TERMINAL_STATUSES.has(document.status);
  const displayName = document.type
    ? document.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : `Clinical Document (${document.id.slice(0, 8)})`;

  const pageCount = Array.isArray(document.pages)
    ? document.pages.length
    : typeof document.pages === 'number'
    ? document.pages
    : 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Back Link and Header */}
      <div>
        <Link
          to="/documents"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--ct-text-muted)',
            fontSize: '13px',
            textDecoration: 'none',
            marginBottom: '12px',
          }}
        >
          ← Back to All Documents
        </Link>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
              {displayName}
            </h1>
            <div style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span>ID: <code style={{ color: 'var(--ct-text-secondary)' }}>{document.id}</code></span>
              <span>•</span>
              <span>{document.created_at ? new Date(document.created_at).toLocaleString() : 'Active'}</span>
              <span>•</span>
              <span className="tabular">{pageCount} Rasterised Page{pageCount > 1 ? 's' : ''}</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className={`ct-badge ${document.status === 'ready' ? 'confirmed' : document.status === 'failed' ? 'abnormal' : 'review'}`}>
              {document.status.replace(/_/g, ' ').toUpperCase()}
            </span>

            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                fontSize: '12.5px',
                fontWeight: 600,
                borderRadius: 'var(--ct-radius-sm)',
                color: '#f87171',
                backgroundColor: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.18)';
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.08)';
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.25)';
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                <line x1="10" y1="11" x2="10" y2="17" />
                <line x1="14" y1="11" x2="14" y2="17" />
              </svg>
              <span>{isDeleting ? 'Deleting...' : 'Delete Document'}</span>
            </button>
          </div>
        </div>
      </div>

      {document.errorReason && (
        <div
          style={{
            padding: '14px 18px',
            backgroundColor: 'var(--ct-blocked-bg)',
            border: '1px solid var(--ct-blocked-border)',
            borderRadius: 'var(--ct-radius-md)',
            color: 'var(--ct-blocked)',
            fontSize: '13.5px',
          }}
        >
          <strong>Processing Notice:</strong> {document.errorReason}
        </div>
      )}

      {isProcessing && (
        <div
          style={{
            padding: '16px 20px',
            backgroundColor: 'var(--ct-primary-subtle)',
            border: '1px solid var(--ct-primary-border)',
            borderRadius: 'var(--ct-radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: '#60a5fa',
            fontSize: '13.5px',
          }}
        >
          <span className="pulse-dot" />
          <span>Multimodal ingestion in progress. Extracted clinical fields will populate automatically once ready.</span>
        </div>
      )}

      {/* Dual Pane: Left = Original Document Viewer with Bounding Boxes, Right = Extracted Entities */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 1.3fr)', gap: '24px', alignItems: 'flex-start' }}>
        {/* Left: Document Viewer */}
        <section className="ct-card" style={{ padding: '20px' }}>
          <div className="ct-card-header">
            <h2 className="ct-card-title">
              <span>Original Document &amp; Citations</span>
            </h2>
          </div>
          <DocumentViewer
            pageUrls={document.page_urls || []}
            sourceHighlight={activeSource}
          />
        </section>

        {/* Right: Extracted Entities with Provenance */}
        <section className="ct-card" style={{ padding: '20px' }}>
          <div className="ct-card-header">
            <div>
              <h2 className="ct-card-title">
                <span>Extracted Clinical Entities ({extractedFields.length})</span>
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
                Every item is anchored to exact coordinates on the document. Click "Show original" to jump to bounding box.
              </p>
            </div>
          </div>

          {extractedFields.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--ct-text-muted)' }}>
              <p style={{ fontSize: '13.5px', margin: 0 }}>
                {document.status === 'ready'
                  ? 'No clinical medications, labs, or diagnoses were detected in this document.'
                  : 'Extracted clinical data will appear here once the ingestion pipeline finishes.'}
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {extractedFields.map((field) => (
                <ExtractedFieldCard
                  key={field.sk}
                  field={field}
                  isActiveSource={activeFieldSk === field.sk}
                  onShowOriginal={(source) => {
                    setActiveSource(source);
                    setActiveFieldSk(field.sk);
                  }}
                  onRefresh={fetchData}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
