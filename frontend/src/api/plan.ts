import { apiClient } from './client';
import type { CarePlanGenerateResponse } from '../types/api';

/**
 * Mark a care-plan task as done.
 * @param dayIndex - 0-6 post-discharge day
 * @param slot - morning | afternoon | evening | night
 */
export const markPlanDone = async (dayIndex: number, slot: string): Promise<void> => {
  return await apiClient.markPlanDone(dayIndex, slot);
};

/**
 * Trigger backend care-plan generation.
 * After success, refresh GET /record to get the new plan_entries.
 */
export const generateCarePlan = async (): Promise<CarePlanGenerateResponse> => {
  return await apiClient.generateCarePlan();
};
