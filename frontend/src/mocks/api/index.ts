import type { 
  PatientRecord, CarePlanItem, DocumentMetadata, CreateDocumentRequest, CreateDocumentResponse, 
  ExtractedField, UpdateRecordFieldRequest, SubstitutionRequest, SubstitutionResponse, PreviousScanEntry 
} from '../../types/api';

const mockExtractedFields: ExtractedField<Record<string, unknown>>[] = [
  {
    sk: 'ext_diag_1',
    category: 'diagnosis',
    value: { condition: 'Type 2 Diabetes Mellitus', icd10: 'E11.9' },
    source: { doc_id: 'd_001', page: 1, bbox: [10, 15, 30, 5], verbatim: 'Diagnosis: Type 2 Diabetes Mellitus', doc_name: 'Discharge Summary.pdf' },
    confidence: 0.95,
    status: 'confirmed'
  },
  {
    sk: 'ext_med_1',
    category: 'medication',
    value: { name: 'Metformin', strength: '500mg', frequency: 'BD', duration: '30 days' },
    source: { doc_id: 'd_001', page: 1, bbox: [12, 34, 48, 4], verbatim: 'Tab. Metformin 500mg BD x 30 days', doc_name: 'Discharge Summary.pdf' },
    confidence: 0.91,
    status: 'confirmed'
  },
  {
    sk: 'ext_med_2',
    category: 'medication',
    value: { name: 'Amoxicillin', strength: '250mg', frequency: 'TDS' },
    source: { doc_id: 'd_001', page: 1, bbox: [12, 42, 40, 4], verbatim: 'Amoxil 250mg 3 times a day', doc_name: 'Discharge Summary.pdf' },
    confidence: 0.72,
    status: 'needs_review'
  },
  {
    sk: 'ext_followup_1',
    category: 'follow_up',
    value: { instruction: 'Follow up with PCP in 2 weeks', timeframe: '2 weeks' },
    source: { doc_id: 'd_001', page: 2, bbox: [10, 80, 50, 5], verbatim: 'Patient to follow up with primary care in 2 weeks.', doc_name: 'Discharge Summary.pdf' },
    confidence: 0.88,
    status: 'extracted'
  },
  {
    sk: 'ext_lab_1',
    category: 'lab_result',
    value: { test: 'HbA1c', value: '7.2', unit: '%' },
    source: { doc_id: 'd_001', verbatim: 'HbA1c was 7.2%', doc_name: 'Discharge Summary.pdf' },
    confidence: 0.99,
    status: 'confirmed'
  }
];

const mockDocuments: DocumentMetadata[] = [
  {
    id: 'd_001',
    name: 'Discharge Summary.pdf',
    type: 'application/pdf',
    status: 'ready',
    uploadedAt: '2023-09-30T10:00:00Z',
    extractedData: mockExtractedFields
  },
  {
    id: 'd_002',
    name: 'Blood Test Report.pdf',
    type: 'application/pdf',
    status: 'processing',
    uploadedAt: new Date().toISOString()
  },
  {
    id: 'd_003',
    name: 'Old Medical Report.pdf',
    type: 'application/pdf',
    status: 'failed',
    uploadedAt: '2023-01-15T08:30:00Z',
    errorReason: 'Processing failed due to unreadable text'
  }
];

const mockRecord: PatientRecord = {
  patient: {
    id: 'p_001',
    name: 'Jane Doe',
    dob: '1980-05-12'
  },
  alerts: [
    {
      id: 'a_001',
      message: 'Persistent fever > 101°F for 48h. Please contact your doctor immediately.',
      severity: 'critical',
      source: 'Discharge Plan Rules'
    }
  ],
  carePlan: [
    {
      id: 'cp_001',
      day: '2023-10-01',
      slot: 'morning',
      title: 'Metformin 500mg',
      description: 'Take one tablet with breakfast',
      status: 'completed',
      type: 'medication'
    },
    {
      id: 'cp_002',
      day: '2023-10-01',
      slot: 'evening',
      title: 'Metformin 500mg',
      description: 'Take one tablet with dinner',
      status: 'pending',
      type: 'medication'
    }
  ],
  recentDocuments: []
};

let scenarioCounter = 0;

export const mockApi = {
  getRecord: async (): Promise<PatientRecord> => {
    return new Promise(resolve => setTimeout(() => {
      const recentDocs = [...mockDocuments].sort((a, b) => new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime()).slice(0, 3);
      resolve({ ...mockRecord, recentDocuments: recentDocs });
    }, 500));
  },
  
  markPlanDone: async (id: string): Promise<CarePlanItem> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const item = mockRecord.carePlan.find(i => i.id === id);
        if (item) {
          item.status = 'completed';
          resolve({ ...item });
        } else {
          reject(new Error('Item not found'));
        }
      }, 300);
    });
  },

  updateRecordField: async (req: UpdateRecordFieldRequest): Promise<void> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        let found = false;
        for (const doc of mockDocuments) {
          if (doc.extractedData) {
            const field = doc.extractedData.find(f => f.sk === req.sk);
            if (field) {
              field.value = { ...(field.value as Record<string, unknown>), ...req.value };
              field.status = 'confirmed';
              found = true;
            }
          }
        }
        if (found) resolve();
        else reject(new Error('Field not found'));
      }, 400);
    });
  },

  getDocuments: async (): Promise<DocumentMetadata[]> => {
    return new Promise(resolve => setTimeout(() => resolve([...mockDocuments]), 400));
  },

  getDocument: async (id: string): Promise<DocumentMetadata> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const doc = mockDocuments.find(d => d.id === id);
        if (doc) resolve(JSON.parse(JSON.stringify(doc)));
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
          name: req.filename,
          type: req.content_type,
          status: 'uploaded',
          uploadedAt: new Date().toISOString()
        };
        mockDocuments.push(newDoc);
        
        setTimeout(() => {
          const docToUpdate = mockDocuments.find(d => d.id === newId);
          if (docToUpdate) docToUpdate.status = 'processing';
          
          setTimeout(() => {
            if (docToUpdate) {
              docToUpdate.status = 'ready';
              docToUpdate.extractedData = []; 
            }
          }, 5000);
        }, 3000);

        resolve({
          doc_id: newId,
          upload_url: 'mock://s3-upload-url'
        });
      }, 500);
    });
  },

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  submitSubstitution: async (_req: SubstitutionRequest): Promise<SubstitutionResponse> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        scenarioCounter = (scenarioCounter + 1) % 3;
        
        if (scenarioCounter === 1) { // Scenario A: Successful substitution
          resolve({
            detected: { brand: 'Tylenol', generic: 'Acetaminophen', strength: '500mg' },
            blocked: false,
            alternatives: [
              { brand: 'Generic Paracetamol', generic: 'Acetaminophen', strength: '500mg', priceEstimate: '$' },
              { brand: 'Panadol', generic: 'Acetaminophen', strength: '500mg', priceEstimate: '$$' }
            ],
            interactions: []
          });
        } else if (scenarioCounter === 2) { // Scenario B: Interaction warning
          resolve({
            detected: { brand: 'Advil', generic: 'Ibuprofen', strength: '400mg' },
            blocked: false,
            alternatives: [
              { brand: 'Motrin', generic: 'Ibuprofen', strength: '400mg', priceEstimate: '$$' }
            ],
            interactions: [
              {
                severity: 'high',
                message: 'May increase risk of bleeding or kidney issues when taken alongside current medications.',
                activeMedication: 'Metformin 500mg',
                newMedication: 'Ibuprofen 400mg'
              }
            ]
          });
        } else { // Scenario C: Blocked
          resolve({
            detected: { brand: 'Warfarin', generic: 'Warfarin Sodium', strength: '5mg' },
            blocked: true,
            reason: 'Substitution requires specialized clinical review for narrow therapeutic index drugs.',
            alternatives: [],
            interactions: []
          });
        }
      }, 1500);
    });
  },

  getPreviousScans: async (): Promise<PreviousScanEntry[]> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          { id: 's_001', date: new Date().toISOString(), detectedName: 'Tylenol 500mg', status: 'success' },
          { id: 's_002', date: new Date(Date.now() - 86400000).toISOString(), detectedName: 'Warfarin 5mg', status: 'blocked' }
        ]);
      }, 400);
    });
  }
};
