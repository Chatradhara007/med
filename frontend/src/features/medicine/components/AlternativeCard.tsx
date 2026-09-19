import type { AlternativeMedicine } from '../../../types/api';

interface Props {
  alternative: AlternativeMedicine;
}

export const AlternativeCard = ({ alternative }: Props) => {
  return (
    <div className="alternative-card">
      <div className="alt-info">
        <h4>{alternative.brand}</h4>
        <p className="alt-generic">{alternative.generic} • {alternative.strength}</p>
      </div>
      {alternative.priceEstimate && (
        <div className="alt-price">
          <span className="price-badge">{alternative.priceEstimate}</span>
        </div>
      )}
    </div>
  );
};
