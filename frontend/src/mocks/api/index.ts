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
  BackendDocumentStatus,
} from '../../types/api';
import type { CareThreadApi } from '../../api/client';

// ─── Mock data ────────────────────────────────────────────────────────────────

const mockDocuments: DocumentMetadata[] = [
  {
    id: 'd_001',
    type: 'discharge_summary',
    status: 'ready',
    created_at: '2026-09-15T10:00:00Z',
    updated_at: '2026-09-15T10:05:00Z',
    pages: 2,
    page_urls: [],
  },
  {
    id: 'd_002',
    type: 'lab_report',
    status: 'processing' as BackendDocumentStatus,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'd_003',
    type: 'discharge_summary',
    status: 'failed',
    created_at: '2026-09-01T08:30:00Z',
    updated_at: '2026-09-01T08:35:00Z',
    errorReason: 'Processing failed due to unreadable text',
  },
];

const mockRecord: PatientRecord = {
  patient: {
    id: 'p_001',
    name: 'Jane Doe',
    age: 46,
    sex: 'Female',
    language: 'English',
    phone: '+91-98765-43210',
  },
  alerts: [
    {
      id: 'a_001',
      message: 'Persistent fever > 101°F for 48h. Please contact your doctor immediately.',
      severity: 'high',
      source: 'Discharge Plan Rules',
    },
    {
      id: 'a_002',
      message: 'Blood glucose reading above target. Monitor and contact your care team if it persists.',
      severity: 'warning',
      source: 'Discharge Plan Rules',
    },
  ],
  carePlan: [
    {
      id: '0_morning',
      day_index: 0,
      slot: 'morning',
      action: 'Take Metformin 500mg with breakfast',
      med_ref: 'MED#metformin',
      time_target: '08:00',
      done: true,
      completed_at: new Date().toISOString(),
      provenance: {
        source: { doc_id: 'd_001', page: 1, bbox: [120, 340, 480, 362], verbatim: 'Tab. Metformin 500mg BD x 30 days' },
        confidence: 0.91,
        status: 'confirmed',
      },
    },
    {
      id: '0_evening',
      day_index: 0,
      slot: 'evening',
      action: 'Take Metformin 500mg with dinner',
      med_ref: 'MED#metformin',
      time_target: '20:00',
      done: false,
      provenance: {
        source: { doc_id: 'd_001', page: 1, bbox: [120, 340, 480, 362], verbatim: 'Tab. Metformin 500mg BD x 30 days' },
        confidence: 0.91,
        status: 'confirmed',
      },
    },
    {
      id: '1_morning',
      day_index: 1,
      slot: 'morning',
      action: 'Take Atorvastatin 20mg',
      med_ref: 'MED#atorvastatin',
      time_target: '08:00',
      done: false,
      provenance: {
        source: { doc_id: 'd_001', page: 1 },
        confidence: 0.88,
        status: 'confirmed',
      },
    },
  ],
  recentDocuments: [...mockDocuments].sort(
    (a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
  ),
  activeMedications: [
    {
      sk: 'MED#metformin',
      name: 'Metformin',
      salt: 'Metformin Hydrochloride',
      strength: '500mg',
      form: 'tablet',
      frequency: 'BD',
      duration: 30,
      instructions: 'Take with food',
      provenance: {
        source: { doc_id: 'd_001', page: 1, bbox: [120, 340, 480, 362], verbatim: 'Tab. Metformin 500mg BD x 30 days' },
        confidence: 0.91,
        status: 'confirmed',
      },
    },
    {
      sk: 'MED#atorvastatin',
      name: 'Atorvastatin',
      salt: 'Atorvastatin Calcium',
      strength: '20mg',
      form: 'tablet',
      frequency: 'OD',
      duration: 30,
      instructions: 'Take at night',
      provenance: {
        source: { doc_id: 'd_001', page: 1 },
        confidence: 0.88,
        status: 'confirmed',
      },
    },
    {
      sk: 'MED#amoxicillin',
      name: 'Amoxicillin',
      salt: 'Amoxicillin Trihydrate',
      strength: '250mg',
      form: 'capsule',
      frequency: 'TDS',
      duration: 7,
      provenance: {
        source: { doc_id: 'd_001', page: 1, bbox: [120, 420, 480, 440], verbatim: 'Amoxil 250mg 3 times a day' },
        confidence: 0.72,
        status: 'needs_review',
      },
    },
  ],
  diagnoses: [
    {
      sk: 'DIAG#dm2',
      condition: 'Type 2 Diabetes Mellitus',
      icd10: 'E11.9',
      status: 'active',
      provenance: {
        source: { doc_id: 'd_001', page: 1, bbox: [100, 150, 300, 165], verbatim: 'Diagnosis: Type 2 Diabetes Mellitus' },
        confidence: 0.95,
        status: 'confirmed',
      },
    },
    {
      sk: 'DIAG#htn',
      condition: 'Essential Hypertension',
      icd10: 'I10',
      status: 'active',
      provenance: {
        source: { doc_id: 'd_001', page: 1 },
        confidence: 0.89,
        status: 'confirmed',
      },
    },
  ],
  labResults: [
    {
      sk: 'LAB#hba1c',
      test: 'HbA1c',
      value: '7.2',
      unit: '%',
      ref_low: 4.0,
      ref_high: 5.6,
      ref_source: 'WHO 2024',
      flag: 'H',
      deviation_score: 0.62,
      provenance: {
        source: { doc_id: 'd_001', page: 2, verbatim: 'HbA1c was 7.2%' },
        confidence: 0.99,
        status: 'confirmed',
      },
    },
    {
      sk: 'LAB#glucose',
      test: 'Fasting Blood Glucose',
      value: '138',
      unit: 'mg/dL',
      ref_low: 70,
      ref_high: 100,
      flag: 'H',
      deviation_score: 0.45,
      provenance: {
        source: { doc_id: 'd_001', page: 2 },
        confidence: 0.93,
        status: 'confirmed',
      },
    },
  ],
  profile_complete: true,
};

// Store needs_review state for the Amoxicillin mock
let amoxReviewStatus: 'needs_review' | 'confirmed' = 'needs_review';

let scenarioCounter = 0;

// ─── Mock API implementation ──────────────────────────────────────────────────

export const mockApi: CareThreadApi = {
  getRecord: async (): Promise<PatientRecord> => {
    return new Promise((resolve) =>
      setTimeout(() => {
        const record = { ...mockRecord };
        // Apply any in-flight review updates
        record.activeMedications = record.activeMedications.map((m) => {
          if (m.sk === 'MED#amoxicillin' && m.provenance) {
            return { ...m, provenance: { ...m.provenance, status: amoxReviewStatus } };
          }
          return m;
        });
        resolve(record);
      }, 500)
    );
  },

  updateRecordField: async (req: UpdateRecordFieldRequest): Promise<void> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        if (req.sk === 'MED#amoxicillin') {
          amoxReviewStatus = 'confirmed';
          resolve();
        } else if (req.sk === 'PROFILE') {
          // Profile update
          const patient = mockRecord.patient;
          if (req.field === 'name') patient.name = String(req.value);
          else if (req.field === 'age') patient.age = Number(req.value);
          else if (req.field === 'phone') patient.phone = String(req.value);
          else if (req.field === 'language') patient.language = String(req.value);
          else if (req.field === 'sex') patient.sex = String(req.value);
          resolve();
        } else {
          // Generic success for other fields
          resolve();
        }
      }, 400);
    });
  },

  getDocument: async (id: string): Promise<DocumentMetadata> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const doc = mockDocuments.find((d) => d.id === id);
        if (doc) resolve({ ...doc });
        else reject(new Error('Document not found'));
      }, 300);
    });
  },

  createDocument: async (req: CreateDocumentRequest): Promise<CreateDocumentResponse> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const newId = `d_${Math.random().toString(36).substr(2, 9)}`;
        const newDoc: DocumentMetadata = {
          id: newId,
          type: req.content_type.includes('image') ? 'medicine_strip' : 'discharge_summary',
          status: 'uploaded',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        mockDocuments.push(newDoc);
        mockRecord.recentDocuments = [...mockDocuments].sort(
          (a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
        );

        // Simulate pipeline progression
        setTimeout(() => {
          const d = mockDocuments.find((x) => x.id === newId);
          if (d) { d.status = 'rasterising'; d.updated_at = new Date().toISOString(); }
          setTimeout(() => {
            if (d) { d.status = 'extracting'; d.updated_at = new Date().toISOString(); }
            setTimeout(() => {
              if (d) { d.status = 'ready'; d.pages = 2; d.page_urls = []; d.updated_at = new Date().toISOString(); }
            }, 5000);
          }, 3000);
        }, 2000);

        resolve({ doc_id: newId, upload_url: 'mock://s3-upload-url' });
      }, 500);
    });
  },

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  uploadToS3: async (_uploadUrl: string, _file: File): Promise<void> => {
    // Mock: simulate upload delay
    return new Promise((resolve) => setTimeout(resolve, 800));
  },

  markPlanDone: async (dayIndex: number, slot: string): Promise<void> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const item = mockRecord.carePlan.find(
          (i) => i.day_index === dayIndex && i.slot === slot
        );
        if (item) {
          item.done = true;
          item.completed_at = new Date().toISOString();
        }
        resolve();
      }, 300);
    });
  },

  generateCarePlan: async (): Promise<CarePlanGenerateResponse> => {
    return new Promise((resolve) =>
      setTimeout(() => {
        resolve({
          patient_id: 'p_001',
          days_covered: 7,
          entries: mockRecord.carePlan.map((e) => ({
            day_index: e.day_index,
            slot: e.slot,
            action: e.action,
            med_ref: e.med_ref,
            time_target: e.time_target,
            done: e.done,
            completed_at: e.completed_at,
          })),
          alerts: [],
          reminders_scheduled: true,
        });
      }, 800)
    );
  },

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  submitSubstitution: async (_req: SubstitutionRequest): Promise<SubstitutionResponse> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        scenarioCounter = (scenarioCounter + 1) % 3;

        if (scenarioCounter === 1) {
          // Scenario A: Successful substitution
          resolve({
            blocked: false,
            alternatives: [
              {
                brand: 'Glycomet',
                salt: 'Metformin Hydrochloride',
                strength_mg: 500,
                form: 'tablet',
                manufacturer: 'USV Pvt. Ltd.',
                price_inr: 32,
                nti: false,
                common_interactions: [],
              },
              {
                brand: 'Glucophage',
                salt: 'Metformin Hydrochloride',
                strength_mg: 500,
                form: 'tablet',
                manufacturer: 'Merck',
                price_inr: 48,
                nti: false,
                common_interactions: [],
              },
            ],
            interactions: [],
          });
        } else if (scenarioCounter === 2) {
          // Scenario B: Interaction warning
          resolve({
            blocked: false,
            alternatives: [
              {
                brand: 'Brufen',
                salt: 'Ibuprofen',
                strength_mg: 400,
                form: 'tablet',
                manufacturer: 'Abbott',
                price_inr: 28,
                nti: false,
                common_interactions: ['May affect kidney function'],
              },
            ],
            interactions: [
              'Ibuprofen may increase risk of bleeding when taken with current medications.',
              'Monitor renal function closely if using NSAIDs alongside Metformin.',
            ],
          });
        } else {
          // Scenario C: Blocked (NTI drug)
          resolve({
            blocked: true,
            reason: 'Substitution requires specialized clinical review for narrow therapeutic index drugs.',
            alternatives: [],
            interactions: [],
          });
        }
      }, 1200);
    });
  },

  interpretLabs: async (): Promise<LabInterpretationReport> => {
    return new Promise((resolve) =>
      setTimeout(() => {
        resolve({
          patient_id: 'p_001',
          total_findings: 2,
          abnormal_count: 2,
          top_findings: [
            {
              analyte: 'HbA1c',
              value: '7.2',
              unit: '%',
              ref_low: 4.0,
              ref_high: 5.6,
              ref_source: 'WHO 2024',
              status: 'high',
              deviation_score: 0.62,
              rank: 1,
              context_diagnoses: ['Type 2 Diabetes Mellitus'],
              context_medications: ['Metformin 500mg BD'],
              explanation: 'HbA1c of 7.2% indicates suboptimal glycaemic control. Metformin therapy should be continued and dietary modifications reinforced.',
              confidence: 0.99,
              review_status: 'confirmed',
            },
            {
              analyte: 'Fasting Blood Glucose',
              value: '138',
              unit: 'mg/dL',
              ref_low: 70,
              ref_high: 100,
              ref_source: 'ADA 2024',
              status: 'high',
              deviation_score: 0.45,
              rank: 2,
              context_diagnoses: ['Type 2 Diabetes Mellitus'],
              context_medications: ['Metformin 500mg BD'],
              explanation: 'Fasting glucose of 138 mg/dL is above target. Continue current medication and avoid refined carbohydrates.',
              confidence: 0.93,
              review_status: 'confirmed',
            },
          ],
          all_findings: [],
          cross_module_alerts: [
            'Elevated HbA1c may increase cardiovascular risk — monitor blood pressure closely.',
          ],
          generated_at: new Date().toISOString(),
        });
      }, 1200)
    );
  },
};
