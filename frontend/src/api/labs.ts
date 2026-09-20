import { apiClient } from './client';
import type { LabInterpretationReport } from '../types/api';

/**
 * Request a lab interpretation from the backend.
 * The backend reads lab_results, diagnoses, and medications from the patient record.
 * Do NOT generate interpretations in the browser.
 */
export const interpretLabs = async (): Promise<LabInterpretationReport> => {
  return await apiClient.interpretLabs();
};
