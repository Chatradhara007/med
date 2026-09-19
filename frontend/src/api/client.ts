import { mockApi } from '../mocks/api';

// For now, apiClient simply passes through to the mockApi.
export const apiClient = {
  ...mockApi
};
