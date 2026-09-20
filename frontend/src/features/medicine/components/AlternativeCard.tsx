import type { AlternativeMedicine } from '../../../types/api';

interface Props {
  alternative: AlternativeMedicine;
}

export const AlternativeCard = ({ alternative }: Props) => {
  const generic = alternative.salt || '';
  const strength = alternative.strength_mg ? `${alternative.strength_mg}mg` : '';
  const price = alternative.price_inr ? `₹${alternative.price_inr}` : null;

  return (
    <div
      style={{
        padding: '18px 20px',
        backgroundColor: 'var(--ct-surface)',
        border: '1px solid var(--ct-border)',
        borderRadius: 'var(--ct-radius-md)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '16px',
        transition: 'border-color var(--ct-transition-fast)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
            {alternative.brand}
          </h4>
          <span className="ct-badge confirmed" style={{ fontSize: '10.5px' }}>
            ✓ Bioequivalent
          </span>
          {alternative.nti && (
            <span className="ct-badge abnormal" style={{ fontSize: '10.5px' }}>
              ⚠ NTI Strict Monitor
            </span>
          )}
        </div>

        {generic && (
          <div style={{ fontSize: '12.5px', color: '#60a5fa', fontWeight: 500 }}>
            Active Salt: {generic}
          </div>
        )}

        <div style={{ fontSize: '12px', color: 'var(--ct-text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {[strength, alternative.form].filter(Boolean).join(' • ')}
          {alternative.manufacturer && <span>• Mfr: {alternative.manufacturer}</span>}
        </div>
      </div>

      {price && (
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <span
            className="tabular"
            style={{
              display: 'inline-block',
              fontSize: '15px',
              fontWeight: 700,
              color: 'var(--ct-confirmed)',
              backgroundColor: 'var(--ct-confirmed-bg)',
              border: '1px solid var(--ct-confirmed-border)',
              padding: '4px 10px',
              borderRadius: 'var(--ct-radius-sm)',
            }}
          >
            {price}
          </span>
          <div style={{ fontSize: '10.5px', color: 'var(--ct-text-muted)', marginTop: '2px' }}>
            Retail Price
          </div>
        </div>
      )}
    </div>
  );
};
