import { apiClient } from './client';
import type { CarePlanItem  } from '../types/api';

export const markPlanDone = async (id: string): Promise<CarePlanItem> => {
  return await apiClient.markPlanDone(id);
};
