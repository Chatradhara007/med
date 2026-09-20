import { fetchAuthSession } from 'aws-amplify/auth';
import { config } from '../config';
import type {
  BackendPatientRecord,
  BackendDocumentDetail,
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
import {
  createApiError,
  type CarePlanItem,
  type Alert,
  type MedicationValue,
  type DiagnosisValue,
  type LabResultValue,
} from '../types/api';

/**
 * An empty base URL silently turns `/record` into a same-origin request that
 * the dev server answers with index.html, so `response.json()` fails on an
 * HTML document and the real cause -- no API URL -- never surfaces.
 */
const getBaseUrl = (): string => {
  if (!config.apiBaseUrl) {
    throw new Error(
      'VITE_API_GATEWAY_URL is not set. Copy frontend/.env.example to ' +
        'frontend/.env, fill in the stack outputs, and restart the dev server.',
    );
  }
  return config.apiBaseUrl;
};

// ─── Authenticated fetch helper ───────────────────────────────────────────────

const fetchWithAuth = async (path: string, options: RequestInit = {}): Promise<unknown> => {
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();

  if (!token) {
    throw new Error('Not authenticated');
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw createApiError(response.status, body);
  }

  return response.json();
};

// ─── Backend → Frontend adapter ───────────────────────────────────────────────

function adaptRecord(raw: BackendPatientRecord): PatientRecord {
  const patient = {
    id: raw.patient.patient_id,
    name: raw.patient.name,
    age: raw.patient.age,
    sex: raw.patient.sex,
    language: raw.patient.language,
    phone: raw.patient.phone,
  };

  const alerts: Alert[] = (raw.alerts || []).map((a) => ({
    id: a.alert_id,
    message: a.message,
    severity: a.severity,
    source: a.rule_id,
  }));

  const carePlan: CarePlanItem[] = (raw.plan_entries || []).map((e) => ({
    id: `${e.day_index}_${e.slot}`,
    day_index: e.day_index,
    slot: e.slot,
    action: e.action,
    med_ref: e.med_ref,
    time_target: e.time_target,
    done: e.done,
    completed_at: e.completed_at,
    provenance: e.provenance,
  }));

  const recentDocuments: DocumentMetadata[] = (raw.documents || [])
    .map((d) => ({
      id: d.doc_id,
      type: d.type,
      status: d.status,
      created_at: d.created_at,
      updated_at: d.updated_at,
    }))
    .sort((a, b) => {
      const aTime = new Date(a.updated_at || a.created_at || 0).getTime();
      const bTime = new Date(b.updated_at || b.created_at || 0).getTime();
      return bTime - aTime;
    });

  const activeMedications: MedicationValue[] = (raw.medications || []).map((m) => ({
    sk: m.sk,
    name: m.name,
    salt: m.salt,
    strength: m.strength,
    form: m.form,
    frequency: m.freq,
    duration: m.duration_days,
    start_date: m.start_date,
    instructions: m.instructions,
    status: m.status,
    provenance: m.provenance,
  }));

  const diagnoses: DiagnosisValue[] = (raw.diagnoses || []).map((d) => ({
    sk: d.sk,
    condition: d.label,
    code_or_slug: d.code_or_slug,
    icd10: d.icd_hint,
    status: d.status,
    notes: d.notes,
    display_name: d.display_name,
    provenance: d.provenance,
  }));

  const labResults: LabResultValue[] = (raw.lab_results || []).map((l) => ({
    sk: l.sk,
    test: l.analyte,
    value: l.value,
    unit: l.unit,
    ref_low: l.ref_low,
    ref_high: l.ref_high,
    ref_source: l.ref_source,
    deviation_score: l.deviation_score,
    flag: l.flag,
    provenance: l.provenance,
  }));

  return {
    patient,
    alerts,
    carePlan,
    recentDocuments,
    activeMedications,
    diagnoses,
    labResults,
    profile_complete: raw.profile_complete,
  };
}

function adaptDocument(raw: BackendDocumentDetail): DocumentMetadata {
  return {
    id: raw.doc_id,
    type: raw.type,
    status: raw.status,
    pages: raw.pages,
    page_urls: raw.page_urls,
    errorReason: raw.error,
  };
}

// ─── Real API implementation ──────────────────────────────────────────────────

export const realApi = {
  getRecord: async (): Promise<PatientRecord> => {
    const raw = (await fetchWithAuth('/record')) as BackendPatientRecord;
    return adaptRecord(raw);
  },

  updateRecordField: async (req: UpdateRecordFieldRequest): Promise<void> => {
    await fetchWithAuth('/record/field', {
      method: 'PATCH',
      body: JSON.stringify(req),
    });
  },

  getDocument: async (id: string): Promise<DocumentMetadata> => {
    const raw = (await fetchWithAuth(`/documents/${id}`)) as BackendDocumentDetail;
    return adaptDocument(raw);
  },

  createDocument: async (req: CreateDocumentRequest): Promise<CreateDocumentResponse> => {
    return (await fetchWithAuth('/documents', {
      method: 'POST',
      body: JSON.stringify(req),
    })) as CreateDocumentResponse;
  },

  /**
   * Upload a file directly to S3 using the presigned URL.
   * This must NOT go through API Gateway.
   */
  uploadToS3: async (uploadUrl: string, file: File): Promise<void> => {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    });
    if (!response.ok) {
      throw createApiError(response.status, { error: { message: 'S3 upload failed' } });
    }
  },

  markPlanDone: async (dayIndex: number, slot: string): Promise<void> => {
    await fetchWithAuth(`/plan/${dayIndex}/${slot}/done`, {
      method: 'POST',
    });
  },

  generateCarePlan: async (): Promise<CarePlanGenerateResponse> => {
    return (await fetchWithAuth('/plan/generate', {
      method: 'POST',
    })) as CarePlanGenerateResponse;
  },

  submitSubstitution: async (req: SubstitutionRequest): Promise<SubstitutionResponse> => {
    return (await fetchWithAuth('/substitution', {
      method: 'POST',
      body: JSON.stringify(req),
    })) as SubstitutionResponse;
  },

  interpretLabs: async (): Promise<LabInterpretationReport> => {
    return (await fetchWithAuth('/labs/interpret', {
      method: 'POST',
    })) as LabInterpretationReport;
  },

  deleteDocument: async (id: string): Promise<void> => {
    try {
      await fetchWithAuth(`/documents/${id}`, {
        method: 'DELETE',
      });
    } catch {
      await fetchWithAuth(`/documents/${id}/delete`, {
        method: 'POST',
      });
    }
  },
};
