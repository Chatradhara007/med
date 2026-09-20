import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import type {
  DocumentMetadata,
  SourceMetadata,
  ExtractedField,
  PatientRecord,
} from '../../../types/api';
import { getDocument, TERMINAL_STATUSES } from '../../../api/documents';
import { getRecord } from '../../../api/record';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { ExtractedFieldCard } from '../components/ExtractedFieldCard';
import { DocumentViewer } from '../components/DocumentViewer';
import '../Documents.css';

// ─── Build ExtractedFields from canonical record filtered by doc_id ───────────

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
      // Backend does not serialize the @property sk field,
      // so derive the real DynamoDB SK from the canonical name.
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
      // Backend does not serialize the @property sk field,
      // so derive the real DynamoDB SK.
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
  const [document, setDocument] = useState<DocumentMetadata | null>(null);
  const [extractedFields, setExtractedFields] = useState<ExtractedField<Record<string, unknown>>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<SourceMetadata | null>(null);
  const [activeFieldSk, setActiveFieldSk] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const [doc, record] = await Promise.all([getDocument(id), getRecord()]);
      setDocument(doc);
      setExtractedFields(buildExtractedFields(record, id));
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
        setDocument(doc);
        if (TERMINAL_STATUSES.has(doc.status)) {
          clearInterval(interval);
          // Refresh record to pick up any newly extracted entities
          const record = await getRecord();
          setExtractedFields(buildExtractedFields(record, id!));
        }
      } catch {
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document?.status, id]);

  if (loading && !document) return <div className="loading">Loading document...</div>;
  if (error || !document) {
    return (
      <div className="document-detail-page">
        <Link to="/documents" className="back-link">← Back to Documents</Link>
        <div className="error-message">{error || 'Document not found'}</div>
      </div>
    );
  }

  const isProcessing = !TERMINAL_STATUSES.has(document.status);
  const displayName = document.type
    ? document.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : `Document ${document.id}`;

  return (
    <div className="document-detail-page">
      <Link to="/documents" className="back-link">← Back to Documents</Link>

      <header className="doc-detail-header">
        <h2>{displayName}</h2>
        <div className="doc-meta">
          <ProcessingStatus status={document.status} />
          {document.created_at && (
            <span>Uploaded: {new Date(document.created_at).toLocaleDateString()}</span>
          )}
        </div>
      </header>

      {document.errorReason && (
        <div className="doc-detail-error">
          <p><strong>Processing Failed:</strong> {document.errorReason}</p>
        </div>
      )}

      {isProcessing && (
        <div className="doc-processing-banner">
          <span className="spinner-small" />
          <p>We are currently extracting information from this document. This page will update automatically.</p>
        </div>
      )}

      <div className="doc-detail-content">
        <section className="doc-extracted-pane">
          <h3>Extracted Information</h3>
          {document.status === 'ready' || document.status === 'review_required' ? (
            <div className="extracted-fields-list">
              {extractedFields.length > 0 ? (
                extractedFields.map((field) => (
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
                ))
              ) : (
                <p className="not-ready-text">
                  No clinical entities were extracted from this document.
                </p>
              )}
            </div>
          ) : (
            <p className="not-ready-text">
              {document.status === 'failed'
                ? 'Extraction failed. See error above.'
                : document.status === 'unsupported'
                  ? 'This document type is not supported for extraction.'
                  : 'Extracted information will be available once processing completes.'}
            </p>
          )}
        </section>

        <section className="doc-original-pane">
          <h3>Original Document</h3>
          <DocumentViewer
            pageUrls={document.page_urls || []}
            sourceHighlight={activeSource}
          />
        </section>
      </div>
    </div>
  );
};
