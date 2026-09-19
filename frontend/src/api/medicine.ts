import { apiClient } from './client';
import type { SubstitutionRequest, SubstitutionResponse, PreviousScanEntry } from '../types/api';

export const submitSubstitution = async (req: SubstitutionRequest): Promise<SubstitutionResponse> => {
  return await apiClient.submitSubstitution(req);
};

export const getPreviousScans = async (): Promise<PreviousScanEntry[]> => {
  return await apiClient.getPreviousScans();
};
