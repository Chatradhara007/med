import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { DocumentMetadata } from '../../../types/api';

interface Props {
  document: DocumentMetadata;
  onDelete?: (id: string) => Promise<void> | void;
}

const STATUS_CONFIG: Record<string, { label: string; badgeClass: string; icon: string }> = {
  ready: { label: 'CONFIRMED', badgeClass: 'ct-badge confirmed', icon: '✓' },
  review_required: { label: 'NEEDS REVIEW', badgeClass: 'ct-badge review', icon: '!' },
  failed: { label: 'INGESTION FAILED', badgeClass: 'ct-badge abnormal', icon: '✕' },
  unsupported: { label: 'UNSUPPORTED TYPE', badgeClass: 'ct-badge review', icon: '?' },
  classifying: { label: 'CLASSIFYING', badgeClass: 'ct-badge processing', icon: '⟳' },
  extracting: { label: 'EXTRACTING ENTITIES', badgeClass: 'ct-badge processing', icon: '⟳' },
  validating: { label: 'VALIDATING SCHEMA', badgeClass: 'ct-badge processing', icon: '⟳' },
  rasterising: { label: 'RASTERISING PAGES', badgeClass: 'ct-badge processing', icon: '⟳' },
  uploading: { label: 'UPLOADING TO S3', badgeClass: 'ct-badge processing', icon: '⟳' },
  uploaded: { label: 'INGESTION QUEUED', badgeClass: 'ct-badge processing', icon: '⟳' },
};

export const DocumentCard = ({ document, onDelete }: Props) => {
  const [isDeleting, setIsDeleting] = useState(false);

  const dateStr = document.updated_at || document.created_at
    ? new Date(document.updated_at || document.created_at || '').toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : 'Active Episode';

  const displayName = document.type && document.type !== 'unknown'
    ? document.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : `Clinical Document (${document.id.slice(0, 8)})`;

  const status = STATUS_CONFIG[document.status] || {
    label: document.status.toUpperCase(),
    badgeClass: 'ct-badge info',
    icon: '•',
  };

  const isTerminalSuccess = document.status === 'ready';

  const pageCount = Array.isArray(document.pages)
    ? document.pages.length
    : typeof document.pages === 'number'
    ? document.pages
    : 1;

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!onDelete) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete this document (${document.id.slice(0, 8)})? This will remove the file and associated ingestion records.`
    );
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      await onDelete(document.id);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Link
      to={`/documents/${document.id}`}
      className="ct-card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        textDecoration: 'none',
        padding: '18px 22px',
        borderLeft: isTerminalSuccess ? '3px solid var(--ct-confirmed)' : '1px solid var(--ct-border)',
        opacity: isDeleting ? 0.5 : 1,
        pointerEvents: isDeleting ? 'none' : 'auto',
        transition: 'all var(--ct-transition-fast)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: 'var(--ct-radius-md)',
              backgroundColor: 'var(--ct-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
              border: '1px solid var(--ct-border-subtle)',
              flexShrink: 0,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>

          <div>
            <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ct-text-primary)', margin: 0 }}>
              {displayName}
            </h4>
            <div style={{ fontSize: '12px', color: 'var(--ct-text-muted)', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>Uploaded {dateStr}</span>
              <span>•</span>
              <span className="tabular">{pageCount} Rasterised Page{pageCount > 1 ? 's' : ''}</span>
              <span>•</span>
              <span style={{ fontFamily: 'monospace' }}>ID: {document.id.slice(0, 8)}</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className={status.badgeClass}>
            <span>{status.icon}</span> {status.label}
          </span>

          {onDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              title="Delete this document"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 10px',
                fontSize: '11.5px',
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
              <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
            </button>
          )}

          <span style={{ color: 'var(--ct-text-muted)', fontSize: '16px', marginLeft: '4px' }}>→</span>
        </div>
      </div>

      {document.errorReason && (
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: 'var(--ct-blocked-bg)',
            border: '1px solid var(--ct-blocked-border)',
            borderRadius: 'var(--ct-radius-sm)',
            fontSize: '12px',
            color: 'var(--ct-blocked)',
            lineHeight: 1.4,
          }}
        >
          <strong>Reason:</strong> {document.errorReason}
        </div>
      )}
    </Link>
  );
};
