import { useState } from 'react';
import type { ExtractedField, SourceMetadata } from '../../../types/api';
import { ProvenanceInfo } from './ProvenanceInfo';
import { ReviewFieldPanel } from './ReviewFieldPanel';

interface Props {
  field: ExtractedField<Record<string, unknown>>;
  onShowOriginal: (source: SourceMetadata) => void;
  onRefresh: () => void;
  isActiveSource: boolean;
}

export const ExtractedFieldCard = ({ field, onShowOriginal, onRefresh, isActiveSource }: Props) => {
  const [isReviewing, setIsReviewing] = useState(false);

  const formatValue = () => {
    const v = field.value;
    switch (field.category) {
      case 'medication':
        return [v.name, v.strength, v.frequency].filter(Boolean).join(' • ');
      case 'diagnosis':
        return `${v.condition}${v.icd10 ? ` (${v.icd10})` : ''}`;
      case 'lab_result': {
        const range = v.ref_low != null && v.ref_high != null
          ? ` [ref: ${v.ref_low}–${v.ref_high} ${v.unit || ''}]`
          : '';
        return `${v.test}: ${v.value} ${v.unit || ''}${range}`;
      }
      case 'follow_up':
        return String(v.instruction || '');
      default:
        return JSON.stringify(v);
    }
  };

  return (
    <div className={`extracted-field-card ${field.status} ${isActiveSource ? 'active-source' : ''}`}>
      <div className="field-header">
        <span className="field-category">{field.category.replace(/_/g, ' ').toUpperCase()}</span>
        <span className={`field-status-badge ${field.status}`}>
          {field.status.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="field-main-value">{formatValue()}</div>

      <ProvenanceInfo source={field.source} confidence={field.confidence} />

      <div className="field-actions">
        <button className="btn-show-original" onClick={() => onShowOriginal(field.source)}>
          Show original
        </button>

        {field.status === 'needs_review' &&
          field.category !== 'lab_result' &&
          !isReviewing && (
            <button className="btn-review" onClick={() => setIsReviewing(true)}>
              Review &amp; Correct
            </button>
          )}
      </div>

      {isReviewing && (
        <ReviewFieldPanel
          field={field}
          onReviewed={() => {
            setIsReviewing(false);
            onRefresh();
          }}
          onCancel={() => setIsReviewing(false)}
        />
      )}
    </div>
  );
};
