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
      return ['status', 'notes', 'display_name'];
    case 'lab_result':
      return [];
    case 'follow_up':
      return ['instruction', 'timeframe'];
    default:
      return Object.keys({});
  }
}

/**
 * Backend field name -> the key the adapter stores it under on `field.value`.
 *
 * `getEditableFields` returns *backend* names, but `field.value` is built by
 * the record adapter using *frontend* names. Looking one up in the other needs
 * this direction. It used to map the other way, so `freq` and `duration_days`
 * resolved to themselves, found nothing on the value object, and were dropped
 * from the form -- frequency and duration silently became uneditable.
 */
function backendFieldToValueKey(category: string, field: string): string {
  if (category === 'medication' && field === 'freq') {
    return 'frequency';
  }

  if (category === 'medication' && field === 'duration_days') {
    return 'duration';
  }

  if (category === 'diagnosis' && field === 'label') {
    return 'condition';
  }

  if (category === 'diagnosis' && field === 'icd_hint') {
    return 'icd10';
  }

  if (category === 'lab_result' && field === 'analyte') {
    return 'test';
  }

  return field;
}

export const ReviewFieldPanel = ({ field, onReviewed, onCancel }: Props) => {
  const editableKeys = getEditableFields(field.category);

  // Initialize form from the field value — only keep editable keys that exist in value
  const initialForm: Record<string, string> = {};
  for (const key of editableKeys) {
    const val = field.value[key] ?? field.value[backendFieldToValueKey(field.category, key)];
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
        const original = field.value[k] ?? field.value[backendFieldToValueKey(field.category, k)];
        return String(original ?? '') !== formData[k];
      });

      if (changedKeys.length === 0) {
        // Accepting a correct extraction is still a review decision and has to
        // reach the backend. Returning here used to close the panel without
        // sending anything, so the chip stayed amber and the button came
        // straight back -- there was no way to resolve a correct value at all.
        await updateRecordField({ sk: field.sk, confirm: true });
        onReviewed();
        return;
      }

      // One PATCH per changed field; the backend takes one attribute at a time
      // and confirms the entity's provenance on each write.
      await Promise.all(
        changedKeys.map((k) =>
          updateRecordField({
            sk: field.sk,
            field: k,
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
