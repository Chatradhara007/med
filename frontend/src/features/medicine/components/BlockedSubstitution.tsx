interface Props {
  reason: string;
}

export const BlockedSubstitution = ({ reason }: Props) => {
  return (
    <div
      style={{
        padding: '24px',
        backgroundColor: 'var(--ct-blocked-bg)',
        border: '1px solid var(--ct-blocked-border)',
        borderRadius: 'var(--ct-radius-lg)',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: 'rgba(239, 68, 68, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ef4444',
            fontSize: '18px',
            fontWeight: 700,
          }}
        >
          🛑
        </div>
        <div>
          <span className="ct-badge blocked" style={{ marginBottom: '4px' }}>
            SAFETY RAIL ENFORCED
          </span>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
            Automated Substitution Blocked
          </h3>
        </div>
      </div>

      <p style={{ color: 'var(--ct-text-primary)', fontSize: '13.5px', lineHeight: 1.6, margin: 0 }}>
        CareThread strict clinical safety policy prevents bioequivalent substitution for this medication.
      </p>

      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'rgba(0, 0, 0, 0.25)',
          borderRadius: 'var(--ct-radius-md)',
          borderLeft: '4px solid #ef4444',
          fontSize: '13px',
          color: 'var(--ct-text-primary)',
        }}
      >
        <strong style={{ color: '#fca5a5', display: 'block', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>
          Enforcement Trigger
        </strong>
        {reason}
      </div>

      <div style={{ fontSize: '12px', color: 'var(--ct-text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>⚠️</span>
        <span>Narrow Therapeutic Index (NTI) medications require precise dose titration and brand-consistent dispensing. Do not switch brands without explicit clinician approval.</span>
      </div>
    </div>
  );
};
