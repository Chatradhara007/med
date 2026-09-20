import type { CarePlanItem } from '../../../types/api';

interface CarePlanCardProps {
  item: CarePlanItem;
  onMarkDone: (dayIndex: number, slot: string) => void;
}

const SLOT_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  morning: { label: 'Morning', icon: '🌅', color: '#f59e0b' },
  afternoon: { label: 'Afternoon', icon: '☀️', color: '#3b82f6' },
  evening: { label: 'Evening', icon: '🌆', color: '#8b5cf6' },
  night: { label: 'Night', icon: '🌙', color: '#6366f1' },
};

export const CarePlanCard = ({ item, onMarkDone }: CarePlanCardProps) => {
  const slotInfo = SLOT_CONFIG[item.slot] || { label: item.slot, icon: '⏰', color: '#64748b' };
  const medName = item.med_ref ? item.med_ref.replace(/^MED#/, '').replace(/_/g, ' ') : null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 18px',
        backgroundColor: item.done ? 'rgba(16, 185, 129, 0.04)' : 'var(--ct-surface)',
        border: '1px solid',
        borderColor: item.done ? 'var(--ct-confirmed-border)' : 'var(--ct-border)',
        borderRadius: 'var(--ct-radius-md)',
        transition: 'all var(--ct-transition-fast)',
        gap: '16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1 }}>
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: 'var(--ct-radius-sm)',
            backgroundColor: item.done ? 'var(--ct-confirmed-bg)' : 'var(--ct-surface-elevated)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            flexShrink: 0,
            border: '1px solid',
            borderColor: item.done ? 'var(--ct-confirmed-border)' : 'var(--ct-border-subtle)',
          }}
        >
          {item.done ? '✓' : slotInfo.icon}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '14px',
                fontWeight: 600,
                color: item.done ? 'var(--ct-text-muted)' : 'var(--ct-text-primary)',
                textDecoration: item.done ? 'line-through' : 'none',
              }}
            >
              {item.action}
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: slotInfo.color,
                letterSpacing: '0.04em',
              }}
            >
              {slotInfo.label}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', color: 'var(--ct-text-muted)' }}>
            {item.time_target && (
              <span className="tabular" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                {item.time_target}
              </span>
            )}
            {medName && (
              <span style={{ color: '#60a5fa', fontWeight: 500 }}>
                💊 {medName}
              </span>
            )}
            {item.done && item.completed_at && (
              <span style={{ color: 'var(--ct-confirmed)' }}>
                Recorded {new Date(item.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        </div>
      </div>

      <div>
        {item.done ? (
          <span className="ct-badge confirmed" style={{ gap: '4px' }}>
            <span>✓</span> Done
          </span>
        ) : (
          <button
            type="button"
            onClick={() => onMarkDone(item.day_index, item.slot)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'var(--ct-surface-elevated)',
              border: '1px solid var(--ct-border-hover)',
              color: 'var(--ct-text-primary)',
              padding: '6px 14px',
              borderRadius: 'var(--ct-radius-md)',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all var(--ct-transition-fast)',
            }}
          >
            Mark Done
          </button>
        )}
      </div>
    </div>
  );
};
