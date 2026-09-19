import type { PatientRecord, CarePlanItem, DocumentMetadata, CreateDocumentRequest, CreateDocumentResponse } from '../../types/api';

const mockDocuments: DocumentMetadata[] = [
  {
    id: 'd_001',
    name: 'Discharge Summary.pdf',
    type: 'application/pdf',
    status: 'ready',
    uploadedAt: '2023-09-30T10:00:00Z'
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
    },
    {
      id: 'cp_003',
      day: '2023-10-02',
      slot: 'morning',
      title: 'Metformin 500mg',
      description: 'Take one tablet with breakfast',
      status: 'pending',
      type: 'medication'
    }
  ],
  recentDocuments: []
};

export const mockApi = {
  getRecord: async (): Promise<PatientRecord> => {
    return new Promise(resolve => setTimeout(() => {
      // Refresh recent docs dynamically
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

  getDocuments: async (): Promise<DocumentMetadata[]> => {
    return new Promise(resolve => setTimeout(() => resolve([...mockDocuments]), 400));
  },

  getDocument: async (id: string): Promise<DocumentMetadata> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const doc = mockDocuments.find(d => d.id === id);
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
          name: req.filename,
          type: req.content_type,
          status: 'uploaded',
          uploadedAt: new Date().toISOString()
        };
        mockDocuments.push(newDoc);
        
        // Simulate processing flow
        setTimeout(() => {
          const docToUpdate = mockDocuments.find(d => d.id === newId);
          if (docToUpdate) docToUpdate.status = 'processing';
          
          setTimeout(() => {
            if (docToUpdate) docToUpdate.status = 'ready';
          }, 5000); // 5s processing -> ready
        }, 3000); // 3s uploaded -> processing

        resolve({
          doc_id: newId,
          upload_url: 'mock://s3-upload-url'
        });
      }, 500);
    });
  }
};
