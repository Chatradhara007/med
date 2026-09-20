import { Link } from 'react-router-dom';
import type { DocumentMetadata } from '../../../types/api';

interface Props {
  document: DocumentMetadata;
}

export const RecentDocumentCard = ({ document }: Props) => {
  const displayName = document.type
    ? document.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'Clinical Document';

  const statusMap: Record<string, { label: string; badgeClass: string }> = {
    ready: { label: 'CONFIRMED', badgeClass: 'ct-badge confirmed' },
    review_required: { label: 'NEEDS REVIEW', badgeClass: 'ct-badge review' },
    failed: { label: 'PROCESSING FAILED', badgeClass: 'ct-badge abnormal' },
    unsupported: { label: 'UNSUPPORTED TYPE', badgeClass: 'ct-badge review' },
    classifying: { label: 'CLASSIFYING', badgeClass: 'ct-badge processing' },
    extracting: { label: 'EXTRACTING', badgeClass: 'ct-badge processing' },
    validating: { label: 'VALIDATING', badgeClass: 'ct-badge processing' },
    rasterising: { label: 'RASTERISING', badgeClass: 'ct-badge processing' },
    uploading: { label: 'UPLOADING', badgeClass: 'ct-badge processing' },
  };

  const statusConfig = statusMap[document.status] || {
    label: document.status.toUpperCase(),
    badgeClass: 'ct-badge info',
  };

  const pageCount = Array.isArray(document.pages)
    ? document.pages.length
    : typeof document.pages === 'number'
    ? document.pages
    : 1;

  return (
    <Link
      to={`/documents/${document.id}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        backgroundColor: 'var(--ct-surface)',
        border: '1px solid var(--ct-border)',
        borderRadius: 'var(--ct-radius-md)',
        textDecoration: 'none',
        transition: 'all var(--ct-transition-fast)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--ct-radius-sm)',
            backgroundColor: 'var(--ct-surface-elevated)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--ct-text-secondary)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>

        <div>
          <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--ct-text-primary)' }}>
            {displayName}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)' }}>
            {document.created_at ? new Date(document.created_at).toLocaleDateString() : 'Active Episode'} • {pageCount} Page{pageCount > 1 ? 's' : ''}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span className={statusConfig.badgeClass}>{statusConfig.label}</span>
        <span style={{ color: 'var(--ct-text-muted)', fontSize: '14px' }}>→</span>
      </div>
    </Link>
  );
};
