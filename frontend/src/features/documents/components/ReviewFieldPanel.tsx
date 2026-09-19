import { useState } from 'react';
import type { ExtractedField } from '../../../types/api';
import { updateRecordField } from '../../../api/record';

interface Props {
  field: ExtractedField<Record<string, unknown>>;
  onReviewed: () => void;
  onCancel: () => void;
}

export const ReviewFieldPanel = ({ field, onReviewed, onCancel }: Props) => {
  // Simple dynamic form based on the object keys
  const [formData, setFormData] = useState<Record<string, unknown>>(field.value);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (key: string, val: string) => {
    setFormData((prev: Record<string, unknown>) => ({ ...prev, [key]: val }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      await updateRecordField({ sk: field.sk, field: field.category, value: formData });
      onReviewed();
    } catch {
      setError('Failed to update field.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="review-field-panel" onSubmit={handleSubmit}>
      <h4>Review & Correct</h4>
      {error && <div className="review-error">{error}</div>}
      
      <div className="review-form-fields">
        {Object.entries(formData).map(([k, v]) => (
          <div key={k} className="review-input-group">
            <label>{k}</label>
            <input 
              type="text" 
              value={(v as string) || ''} 
              onChange={e => handleChange(k, e.target.value)} 
            />
          </div>
        ))}
      </div>
      
      <div className="review-actions">
        <button type="button" className="btn-cancel" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn-confirm" disabled={submitting}>
          {submitting ? 'Saving...' : 'Confirm & Save'}
        </button>
      </div>
    </form>
  );
};
