import { mockApi } from '../mocks/api';
import { realApi } from './realApi';
import type {
  PatientRecord,
  DocumentMetadata,
  CreateDocumentRequest,
  CreateDocumentResponse,
  UpdateRecordFieldRequest,
  SubstitutionRequest,
  SubstitutionResponse,
  CarePlanGenerateResponse,
  LabInterpretationReport,
} from '../types/api';

/**
 * The canonical API interface every backend implementation must satisfy.
 * Components must only call these methods — never fetch() directly.
 */
export interface CareThreadApi {
  getRecord(): Promise<PatientRecord>;
  updateRecordField(req: UpdateRecordFieldRequest): Promise<void>;
  getDocument(id: string): Promise<DocumentMetadata>;
  createDocument(req: CreateDocumentRequest): Promise<CreateDocumentResponse>;
  uploadToS3(uploadUrl: string, file: File): Promise<void>;
  markPlanDone(dayIndex: number, slot: string): Promise<void>;
  generateCarePlan(): Promise<CarePlanGenerateResponse>;
  submitSubstitution(req: SubstitutionRequest): Promise<SubstitutionResponse>;
  interpretLabs(): Promise<LabInterpretationReport>;
}

const isMock = import.meta.env.VITE_USE_MOCK_API !== 'false';

// Switch seamlessly between Mock and Real API based on the environment variable
export const apiClient: CareThreadApi = isMock ? mockApi : realApi;
