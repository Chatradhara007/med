import { apiClient } from './client';
import type { SubstitutionRequest, SubstitutionResponse } from '../types/api';

/**
 * Submit a substitution check.
 *
 * For medicine scan flow: pass { doc_id } after the image has been uploaded and processed.
 * For manual entry: pass { brand, strength }.
 *
 * Do NOT pass the local filename as the brand.
 */
export const submitSubstitution = async (req: SubstitutionRequest): Promise<SubstitutionResponse> => {
  return await apiClient.submitSubstitution(req);
};
