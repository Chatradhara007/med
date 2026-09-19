import type { PatientRecord, CarePlanItem  } from '../../types/api';

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
  recentDocuments: [
    {
      id: 'd_001',
      name: 'Discharge Summary',
      type: 'application/pdf',
      status: 'ready',
      uploadedAt: '2023-09-30T10:00:00Z'
    }
  ]
};

export const mockApi = {
  getRecord: async (): Promise<PatientRecord> => {
    return new Promise(resolve => setTimeout(() => resolve({ ...mockRecord }), 500));
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
  }
};
