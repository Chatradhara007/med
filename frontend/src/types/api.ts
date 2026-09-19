export interface Patient {
  id: string;
  name: string;
  dob: string;
}

export interface Alert {
  id: string;
  message: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  source: string;
}

export interface CarePlanItem {
  id: string;
  day: string; // ISO Date string YYYY-MM-DD
  slot: string; // morning, afternoon, evening
  title: string;
  description: string;
  status: 'pending' | 'completed';
  type: 'medication' | 'task';
}

export type BoundingBox = [number, number, number, number];

export interface SourceMetadata {
  doc_id: string;
  page?: number;
  bbox?: BoundingBox;
  verbatim?: string;
  doc_name?: string;
}

export type FieldStatus = 'extracted' | 'confirmed' | 'needs_review';

export interface ExtractedField<T> {
  sk: string;
  category: 'diagnosis' | 'medication' | 'follow_up' | 'restriction' | 'discharge_instruction' | 'lab_result';
  value: T;
  source: SourceMetadata;
  confidence: number;
  status: FieldStatus;
}

export interface MedicationValue {
  name: string;
  strength?: string;
  frequency?: string;
  duration?: string;
}

export interface DiagnosisValue {
  condition: string;
  icd10?: string;
}

export interface FollowUpValue {
  instruction: string;
  timeframe?: string;
}

export interface LabResultValue {
  test: string;
  value: string;
  unit?: string;
}

export interface DocumentMetadata {
  id: string;
  name: string;
  type: string;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  uploadedAt: string;
  errorReason?: string;
  extractedData?: ExtractedField<Record<string, unknown>>[];
}

export interface CreateDocumentRequest {
  filename: string;
  content_type: string;
}

export interface CreateDocumentResponse {
  doc_id: string;
  upload_url: string;
}

export interface UpdateRecordFieldRequest {
  sk: string;
  field: string;
  value: Record<string, unknown>;
}

export interface PatientRecord {
  patient: Patient;
  alerts: Alert[];
  carePlan: CarePlanItem[];
  recentDocuments: DocumentMetadata[];
}

// Phase 5: Substitution Types
export interface SubstitutionRequest {
  doc_id?: string;
  brand?: string;
  strength?: string;
}

export interface AlternativeMedicine {
  brand: string;
  generic: string;
  strength: string;
  priceEstimate?: string;
}

export interface InteractionWarning {
  severity: 'low' | 'medium' | 'high';
  message: string;
  activeMedication: string;
  newMedication: string;
}

export interface SubstitutionResponse {
  detected?: AlternativeMedicine;
  blocked: boolean;
  reason?: string;
  alternatives: AlternativeMedicine[];
  interactions: InteractionWarning[];
}

export interface PreviousScanEntry {
  id: string;
  date: string;
  detectedName: string;
  status: 'success' | 'blocked' | 'error';
}
