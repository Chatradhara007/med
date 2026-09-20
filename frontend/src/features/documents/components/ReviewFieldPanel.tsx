import { useState } from 'react';
import type { ExtractedField } from '../../../types/api';
import { updateRecordField } from '../../../api/record';

interface Props {
  field: ExtractedField<Record<string, unknown>>;
  onReviewed: () => void;
  onCancel: () => void;
}

/**
 * Returns the editable attributes for a given entity category.
 * These map directly to backend field names used in PATCH /record/field.
 */
function getEditableFields(category: string): string[] {
  switch (category) {
    case 'medication':
      return ['strength', 'freq', 'instructions', 'duration_days', 'status'];
    case 'diagnosis':
      return ['code_or_slug', 'status', 'notes', 'display_name'];
    case 'lab_result':
      return ['value', 'unit', 'flag'];
    case 'follow_up':
      return ['instruction', 'timeframe'];
    default:
      return Object.keys({});
  }
}

/**
 * Maps frontend field names to backend field names for the PATCH payload.
 * (The frontend stores some fields under different keys than the backend.)
 */
function frontendKeyToBackendField(category: string, key: string): string {
  if (category === 'medication' && key === 'frequency') return 'freq';
  if (category === 'medication' && key === 'duration') return 'duration_days';
  if (category === 'diagnosis' && key === 'condition') return 'label';
  if (category === 'diagnosis' && key === 'icd10') return 'icd_hint';
  if (category === 'lab_result' && key === 'test') return 'analyte';
  return key;
}

export const ReviewFieldPanel = ({ field, onReviewed, onCancel }: Props) => {
  const editableKeys = getEditableFields(field.category);

  // Initialize form from the field value — only keep editable keys that exist in value
  const initialForm: Record<string, string> = {};
  for (const key of editableKeys) {
    const val = field.value[key] ?? field.value[frontendKeyToBackendField(field.category, key)];
    if (val != null) {
      initialForm[key] = String(val);
    }
  }

  const [formData, setFormData] = useState<Record<string, string>>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (key: string, val: string) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
  };

  /**
   * Submits one PATCH /record/field call per changed attribute.
   * Payload: { sk, field: attributeName, value: correctedValue }
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!field.sk) {
      setError('Cannot update: missing entity key.');
      return;
    }
    try {
      setSubmitting(true);
      setError(null);

      const changedKeys = Object.keys(formData).filter((k) => {
        const original = field.value[k] ?? field.value[frontendKeyToBackendField(field.category, k)];
        return String(original ?? '') !== formData[k];
      });

      if (changedKeys.length === 0) {
        onReviewed();
        return;
      }

      // Send one PATCH per changed field (backend expects per-attribute updates)
      await Promise.all(
        changedKeys.map((k) =>
          updateRecordField({
            sk: field.sk,
            field: frontendKeyToBackendField(field.category, k),
            value: formData[k],
          })
        )
      );

      onReviewed();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update field.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="review-field-panel" onSubmit={handleSubmit}>
      <h4>Review &amp; Correct</h4>
      {error && <div className="review-error">{error}</div>}

      <div className="review-form-fields">
        {Object.entries(formData).map(([k, v]) => (
          <div key={k} className="review-input-group">
            <label>{k.replace(/_/g, ' ')}</label>
            <input
              type="text"
              value={v}
              onChange={(e) => handleChange(k, e.target.value)}
            />
          </div>
        ))}
      </div>

      {Object.keys(formData).length === 0 && (
        <p className="review-no-fields">No editable fields available for this entity type.</p>
      )}

      <div className="review-actions">
        <button type="button" className="btn-cancel" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn-confirm" disabled={submitting}>
          {submitting ? 'Saving...' : 'Confirm & Save'}
        </button>
      </div>
    </form>
  );
};
