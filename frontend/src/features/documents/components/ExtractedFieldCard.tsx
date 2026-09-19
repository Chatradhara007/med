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
  
  // Format the value nicely based on category
  const formatValue = () => {
    const v = field.value;
    if (field.category === 'medication') return `${v.name} ${v.strength || ''} ${v.frequency || ''}`;
    if (field.category === 'diagnosis') return `${v.condition} ${v.icd10 ? '(' + v.icd10 + ')' : ''}`;
    if (field.category === 'lab_result') return `${v.test}: ${v.value} ${v.unit || ''}`;
    if (field.category === 'follow_up') return `${v.instruction}`;
    return JSON.stringify(v);
  };

  return (
    <div className={`extracted-field-card ${field.status} ${isActiveSource ? 'active-source' : ''}`}>
      <div className="field-header">
        <span className="field-category">{field.category.replace('_', ' ').toUpperCase()}</span>
        <span className={`field-status-badge ${field.status}`}>
          {field.status.replace('_', ' ')}
        </span>
      </div>
      
      <div className="field-main-value">
        {formatValue()}
      </div>

      <ProvenanceInfo source={field.source} confidence={field.confidence} />

      <div className="field-actions">
        <button className="btn-show-original" onClick={() => onShowOriginal(field.source)}>
          Show original
        </button>
        
        {field.status === 'needs_review' && !isReviewing && (
          <button className="btn-review" onClick={() => setIsReviewing(true)}>
            Review
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
