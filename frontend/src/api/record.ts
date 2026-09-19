import { apiClient } from './client';
import type { PatientRecord  } from '../types/api';

export const getRecord = async (): Promise<PatientRecord> => {
  return await apiClient.getRecord();
};
