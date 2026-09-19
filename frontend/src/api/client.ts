import { mockApi } from '../mocks/api';
import { realApi } from './realApi';

const isMock = import.meta.env.VITE_USE_MOCK_API !== 'false';

// Switch seamlessly between Mock and Real API based on the environment variable
export const apiClient = isMock ? mockApi : realApi;
