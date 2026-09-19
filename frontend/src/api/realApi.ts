import { fetchAuthSession } from 'aws-amplify/auth';
import type { 
  PatientRecord, CarePlanItem, DocumentMetadata, CreateDocumentRequest, 
  CreateDocumentResponse, UpdateRecordFieldRequest, SubstitutionRequest, 
  SubstitutionResponse, PreviousScanEntry 
} from '../types/api';

const getBaseUrl = () => import.meta.env.VITE_API_GATEWAY_URL || '';

const fetchWithAuth = async (path: string, options: RequestInit = {}) => {
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  
  if (!token) {
    throw new Error('Not authenticated');
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...options.headers,
  };

  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    throw new Error(`API Request failed: ${response.statusText}`);
  }

  return response.json();
};

export const realApi = {
  getRecord: async (): Promise<PatientRecord> => fetchWithAuth('/record'),
  
  markPlanDone: async (id: string): Promise<CarePlanItem> => 
    fetchWithAuth(`/plan/today/morning/done`, { // Stubbed day/slot
      method: 'POST',
      body: JSON.stringify({ id })
    }),

  updateRecordField: async (req: UpdateRecordFieldRequest): Promise<void> => 
    fetchWithAuth('/record/field', {
      method: 'PATCH',
      body: JSON.stringify(req)
    }),

  getDocuments: async (): Promise<DocumentMetadata[]> => fetchWithAuth('/documents'),

  getDocument: async (id: string): Promise<DocumentMetadata> => fetchWithAuth(`/documents/${id}`),

  createDocument: async (req: CreateDocumentRequest): Promise<CreateDocumentResponse> => 
    fetchWithAuth('/documents', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  submitSubstitution: async (req: SubstitutionRequest): Promise<SubstitutionResponse> => 
    fetchWithAuth('/substitution', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  getPreviousScans: async (): Promise<PreviousScanEntry[]> => fetchWithAuth('/medicine/scans')
};
