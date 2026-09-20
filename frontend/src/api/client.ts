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
  deleteDocument(id: string): Promise<void>;
}

// There is one implementation. The app always talks to the deployed backend,
// so a missing or misspelt environment variable can never silently serve
// fixture data that looks real.
export const apiClient: CareThreadApi = realApi;
