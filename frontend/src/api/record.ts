import { apiClient } from './client';
import type { PatientRecord, UpdateRecordFieldRequest } from '../types/api';

export const getRecord = async (): Promise<PatientRecord> => {
  return await apiClient.getRecord();
};

export const updateRecordField = async (req: UpdateRecordFieldRequest): Promise<void> => {
  return await apiClient.updateRecordField(req);
};
