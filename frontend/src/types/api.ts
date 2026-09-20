// ─── Backend canonical types ─────────────────────────────────────────────────
// These represent the exact shapes returned by the backend API.
// Do NOT modify without reference to the backend contract.

/** Raw backend Patient object */
export interface BackendPatient {
  patient_id: string;
  name: string;
  age?: number;
  sex?: string;
  language?: string;
  phone?: string;
  created_at?: string;
}

/** Backend PlanEntry (day_index is 0-6, slot is morning|afternoon|evening|night) */
export interface BackendPlanEntry {
  day_index: number;
  slot: 'morning' | 'afternoon' | 'evening' | 'night';
  action: string;
  med_ref?: string;
  time_target?: string;
  done: boolean;
  completed_at?: string;
  provenance?: Provenance;
}

/** Backend Alert */
export interface BackendAlert {
  alert_id: string;
  rule_id: string;
  severity: 'info' | 'warning' | 'high' | 'critical';
  message: string;
  fired_at: string;
  acknowledged: boolean;
  cross_module_context?: Record<string, unknown>;
}

/** Backend Medication entity */
export interface BackendMedication {
  sk?: string;
  name: string;
  salt?: string;
  strength?: string;
  form?: string;
  freq?: string;
  duration_days?: number;
  start_date?: string;
  instructions?: string;
  status?: string;
  provenance?: Provenance;
}

/** Backend Diagnosis entity */
export interface BackendDiagnosis {
  sk?: string;
  label: string;
  code_or_slug?: string;
  icd_hint?: string;
  status?: string;
  notes?: string;
  display_name?: string;
  provenance?: Provenance;
}

/** Backend LabResult entity */
export interface BackendLabResult {
  sk?: string;
  analyte: string;
  value: string | number;
  unit?: string;
  ref_low?: number;
  ref_high?: number;
  ref_source?: string;
  deviation_score?: number;
  flag?: string;
  provenance?: Provenance;
}

/** Backend document status — all pipeline stages */
export type BackendDocumentStatus =
  | 'uploading'
  | 'uploaded'
  | 'rasterising'
  | 'classifying'
  | 'extracting'
  | 'validating'
  | 'review_required'
  | 'ready'
  | 'unsupported'
  | 'failed';

/** Backend document entry in the record (minimal, from GET /record) */
export interface BackendDocumentRecord {
  doc_id: string;
  type?: string;
  status: BackendDocumentStatus;
  created_at?: string;
  updated_at?: string;
}

/** Backend document detail (from GET /documents/{id}) */
export interface BackendDocumentDetail {
  doc_id: string;
  status: BackendDocumentStatus;
  type?: string;

  // Backend returns the actual S3 page keys.
  pages?: string[];

  // Backend returns short-lived presigned GET URLs.
  page_urls?: string[];

  error?: string;
}

/** Backend canonical record (GET /record response) */
export interface BackendPatientRecord {
  patient: BackendPatient;
  documents: BackendDocumentRecord[];
  diagnoses: BackendDiagnosis[];
  medications: BackendMedication[];
  lab_results: BackendLabResult[];
  plan_entries: BackendPlanEntry[];
  alerts: BackendAlert[];
  profile_complete: boolean;
}

// ─── Provenance ───────────────────────────────────────────────────────────────

/** BBox order: [ymin, xmin, ymax, xmax], normalized to 0-1000 */
export type BoundingBox = [number, number, number, number];

export interface Provenance {
  field?: string;
  value?: unknown;
  source: {
    doc_id: string;
    page?: number;
    bbox?: BoundingBox;
    verbatim?: string;
  };
  confidence: number;
  status: 'extracted' | 'confirmed' | 'needs_review';
}

// ─── Frontend UI model types ───────────────────────────────────────────────────
// These are the shapes consumed by React components.
// The adapter in realApi.ts converts backend → frontend.

/** Frontend Patient model */
export interface Patient {
  id: string; // mapped from patient_id
  name: string;
  age?: number;
  sex?: string;
  language?: string;
  phone?: string;
}

/** Frontend Alert (backend severity values preserved) */
export interface Alert {
  id: string;
  message: string;
  severity: 'info' | 'warning' | 'high' | 'critical';
  source?: string;
}

/** Frontend CarePlanItem (adapted from backend PlanEntry) */
export interface CarePlanItem {
  id: string; // synthetic: `${day_index}_${slot}`
  day_index: number; // 0-6 post-discharge days
  slot: 'morning' | 'afternoon' | 'evening' | 'night';
  action: string;
  med_ref?: string;
  time_target?: string;
  done: boolean;
  completed_at?: string;
  provenance?: Provenance;
}

/** Frontend Medication model */
export interface MedicationValue {
  sk?: string;
  name: string;
  salt?: string;
  strength?: string;
  form?: string;
  frequency?: string; // mapped from freq
  duration?: number; // mapped from duration_days
  start_date?: string;
  instructions?: string;
  status?: string;
  provenance?: Provenance;
}

/** Frontend Diagnosis model */
export interface DiagnosisValue {
  sk?: string;
  condition: string; // mapped from label
  code_or_slug?: string;
  icd10?: string; // mapped from icd_hint
  status?: string;
  notes?: string;
  display_name?: string;
  provenance?: Provenance;
}

/** Frontend LabResult model */
export interface LabResultValue {
  sk?: string;
  test: string; // mapped from analyte
  value: string | number;
  unit?: string;
  ref_low?: number;
  ref_high?: number;
  ref_source?: string;
  deviation_score?: number;
  flag?: string;
  provenance?: Provenance;
}

/** Document status groupings for the UI */
export type DocumentStatusGroup = 'processing' | 'needs_review' | 'ready' | 'unsupported' | 'failed';

/** Frontend DocumentMetadata */
export interface DocumentMetadata {
  id: string; // mapped from doc_id
  type?: string;
  status: BackendDocumentStatus;
  created_at?: string;
  updated_at?: string;
  // Only available from GET /documents/{id}
  pages?: number | string[];
  page_urls?: string[];
  errorReason?: string; // mapped from error
}

// ─── Extracted fields (for document detail view) ─────────────────────────────

export type FieldStatus = 'extracted' | 'confirmed' | 'needs_review';

export interface SourceMetadata {
  doc_id: string;
  page?: number;
  bbox?: BoundingBox;
  verbatim?: string;
}

/**
 * Generic extracted field shape used in the document detail UI.
 * Clinical entities are built by the document-detail page from the
 * canonical /record data filtered by provenance.source.doc_id.
 */
export interface ExtractedField<T> {
  sk: string;
  category: 'diagnosis' | 'medication' | 'lab_result' | 'follow_up' | 'restriction' | 'discharge_instruction';
  value: T;
  source: SourceMetadata;
  confidence: number;
  status: FieldStatus;
}

// ─── PatientRecord (frontend UI model) ───────────────────────────────────────

export interface PatientRecord {
  patient: Patient;
  alerts: Alert[];
  carePlan: CarePlanItem[]; // from plan_entries
  recentDocuments: DocumentMetadata[]; // from documents
  activeMedications: MedicationValue[]; // from medications
  diagnoses: DiagnosisValue[]; // from diagnoses
  labResults: LabResultValue[]; // from lab_results
  profile_complete: boolean;
}

// ─── API request/response types ───────────────────────────────────────────────

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
  value: string | number | boolean;
}

export interface UpdateRecordRequest {
  sk: string;
  [key: string]: string | number | boolean;
}

export interface SubstitutionRequest {
  doc_id?: string;
  brand?: string;
  strength?: string;
}

/** Backend alternative medicine */
export interface AlternativeMedicine {
  brand: string;
  salt?: string; // generic display
  strength_mg?: number | string;
  form?: string;
  manufacturer?: string;
  price_inr?: number;
  nti?: boolean;
  common_interactions?: string[];
}

export interface SubstitutionResponse {
  blocked: boolean;
  reason?: string;
  alternatives: AlternativeMedicine[];
  interactions: string[]; // array of plain strings
}

/** Derived from record.documents where type === 'medicine_strip' */
export interface PreviousScanEntry {
  id: string; // doc_id
  date: string; // created_at or updated_at
  status: BackendDocumentStatus;
  type: string;
}

// ─── Care Plan generation ─────────────────────────────────────────────────────

export interface CarePlanGenerateResponse {
  patient_id: string;
  days_covered: number;
  entries: BackendPlanEntry[];
  alerts: BackendAlert[];
  reminders_scheduled?: boolean;
}

// ─── Lab Interpretation ───────────────────────────────────────────────────────

export interface LabFinding {
  analyte: string;
  value: string | number;
  unit?: string;
  ref_low?: number;
  ref_high?: number;
  ref_source?: string;
  status?: string;
  deviation_score?: number;
  rank?: number;
  context_diagnoses?: string[];
  context_medications?: string[];
  context_notes?: string;
  explanation?: string;
  provenance?: Provenance;
  confidence?: number;
  review_status?: string;
}

export interface LabInterpretationReport {
  patient_id: string;
  total_findings: number;
  abnormal_count: number;
  top_findings: LabFinding[];
  all_findings: LabFinding[];
  cross_module_alerts: string[];
  generated_at: string;
}

// ─── Structured API error ─────────────────────────────────────────────────────

export interface ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown[];
}

export function createApiError(status: number, body: unknown): ApiError {
  let code: string | undefined;
  let message = `HTTP ${status}`;
  let details: unknown[] | undefined;

  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    if (b.error && typeof b.error === 'object') {
      const err = b.error as Record<string, unknown>;
      code = err.code as string | undefined;
      message = (err.message as string) || message;
      details = err.details as unknown[] | undefined;
    } else if (b.message) {
      message = b.message as string;
    }
  }

  const error = new Error(message) as ApiError;
  error.name = 'ApiError';
  error.status = status;
  error.code = code;
  error.details = details;
  return error;
}
