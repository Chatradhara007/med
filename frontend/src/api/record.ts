import { apiClient } from './client';
import type { PatientRecord, UpdateRecordFieldRequest } from '../types/api';

export const getRecord = async (): Promise<PatientRecord> => {
  return await apiClient.getRecord();
};

export const updateRecordField = async (req: UpdateRecordFieldRequest): Promise<void> => {
  return await apiClient.updateRecordField(req);
};

export const updateRecord = async (req: Record<string, string | number | boolean>): Promise<void> => {
  return await apiClient.updateRecord(req);
};
