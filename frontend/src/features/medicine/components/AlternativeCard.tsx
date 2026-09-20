import type { AlternativeMedicine } from '../../../types/api';

interface Props {
  alternative: AlternativeMedicine;
}

export const AlternativeCard = ({ alternative }: Props) => {
  // salt → generic display, strength_mg → display strength, price_inr → INR price
  const generic = alternative.salt || '';
  const strength = alternative.strength_mg ? `${alternative.strength_mg}mg` : '';
  const price = alternative.price_inr ? `₹${alternative.price_inr}` : '';

  return (
    <div className="alternative-card">
      <div className="alt-info">
        <h4>{alternative.brand}</h4>
        {generic && <p className="alt-generic">{generic}</p>}
        <p className="alt-details">
          {[strength, alternative.form].filter(Boolean).join(' • ')}
        </p>
        {alternative.manufacturer && (
          <p className="alt-manufacturer">{alternative.manufacturer}</p>
        )}
        {alternative.nti && (
          <span className="nti-badge">⚠ Narrow Therapeutic Index</span>
        )}
      </div>
      {price && (
        <div className="alt-price">
          <span className="price-badge">{price}</span>
        </div>
      )}
    </div>
  );
};
