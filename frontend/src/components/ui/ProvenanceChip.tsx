import { useState } from 'react';
import { Link } from 'react-router-dom';

interface ProvenanceChipProps {
  docId?: string;
  docTitle?: string;
  page?: number;
  confidence?: number;
  quote?: string;
  bbox?: number[];
  category?: string;
  interactive?: boolean;
}

export const ProvenanceChip = ({
  docId,
  docTitle = 'Document',
  page,
  confidence,
  quote,
  interactive = true,
}: ProvenanceChipProps) => {
  const [showPopover, setShowPopover] = useState(false);

  const confPercent = confidence != null ? Math.round(confidence * 100) : null;
  const label = page ? `${docTitle} · P.${page}` : docTitle;

  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <button
        type="button"
        className="provenance-pill"
        onClick={(e) => {
          if (!interactive) return;
          e.stopPropagation();
          setShowPopover((v) => !v);
        }}
        title="View clinical source provenance"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
        <span>{label}</span>
        {confPercent != null && (
          <span style={{ opacity: 0.75, fontSize: '10px', marginLeft: '2px' }}>
            {confPercent}%
          </span>
        )}
      </button>

      {showPopover && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)',
            left: '0',
            zIndex: 100,
            width: '280px',
            backgroundColor: 'var(--ct-surface-overlay)',
            border: '1px solid var(--ct-border-hover)',
            borderRadius: 'var(--ct-radius-md)',
            boxShadow: 'var(--ct-shadow-lg)',
            padding: '14px',
            fontSize: '12px',
            color: 'var(--ct-text-secondary)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 600, color: 'var(--ct-text-primary)' }}>Source Provenance</span>
            <button
              type="button"
              onClick={() => setShowPopover(false)}
              style={{ background: 'none', border: 'none', color: 'var(--ct-text-muted)', cursor: 'pointer', fontSize: '14px' }}
            >
              ✕
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div>
              <span style={{ color: 'var(--ct-text-muted)' }}>Document: </span>
              <span style={{ color: 'var(--ct-text-primary)', fontWeight: 500 }}>{docTitle}</span>
            </div>
            {page != null && (
              <div>
                <span style={{ color: 'var(--ct-text-muted)' }}>Location: </span>
                <span style={{ color: 'var(--ct-text-primary)' }}>Page {page}</span>
              </div>
            )}
            {confPercent != null && (
              <div>
                <span style={{ color: 'var(--ct-text-muted)' }}>Extraction Confidence: </span>
                <span style={{ color: confPercent >= 85 ? 'var(--ct-confirmed)' : 'var(--ct-review)', fontWeight: 600 }}>
                  {confPercent}%
                </span>
              </div>
            )}
            {quote && (
              <div style={{ marginTop: '4px', padding: '6px 8px', backgroundColor: 'var(--ct-surface-elevated)', borderRadius: 'var(--ct-radius-xs)', fontStyle: 'italic', color: 'var(--ct-text-primary)' }}>
                "{quote}"
              </div>
            )}
            {docId && (
              <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid var(--ct-border-subtle)' }}>
                <Link
                  to={`/documents/${docId}`}
                  style={{ color: '#60a5fa', textDecoration: 'none', fontWeight: 500, fontSize: '11.5px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                >
                  Inspect in Document Viewer →
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
