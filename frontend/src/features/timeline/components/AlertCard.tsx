import type { Alert } from '../../../types/api';

interface AlertCardProps {
  alert: Alert;
}

const SEVERITY_CONFIG: Record<string, { label: string; badgeClass: string; borderClass: string }> = {
  critical: { label: 'CRITICAL', badgeClass: 'ct-badge critical', borderClass: 'var(--ct-blocked-border)' },
  high: { label: 'HIGH PRIORITY', badgeClass: 'ct-badge abnormal', borderClass: 'var(--ct-abnormal-border)' },
  warning: { label: 'ADVISORY', badgeClass: 'ct-badge review', borderClass: 'var(--ct-review-border)' },
  info: { label: 'INFORMATION', badgeClass: 'ct-badge info', borderClass: 'var(--ct-processing-border)' },
};

export const AlertCard = ({ alert }: AlertCardProps) => {
  const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.warning;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '14px',
        padding: '14px 18px',
        backgroundColor: 'var(--ct-surface)',
        border: '1px solid',
        borderColor: config.borderClass,
        borderRadius: 'var(--ct-radius-md)',
        boxShadow: 'var(--ct-shadow-sm)',
        marginBottom: '10px',
      }}
    >
      <div style={{ marginTop: '2px', flexShrink: 0 }}>
        {alert.severity === 'critical' || alert.severity === 'high' ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        )}
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span className={config.badgeClass}>{config.label}</span>
          {alert.source && (
            <span style={{ fontSize: '11px', color: 'var(--ct-text-muted)', fontFamily: 'monospace' }}>
              Rule: {alert.source}
            </span>
          )}
        </div>
        <p style={{ color: 'var(--ct-text-primary)', fontSize: '13.5px', lineHeight: 1.5, margin: 0 }}>
          {alert.message}
        </p>
      </div>
    </div>
  );
};
