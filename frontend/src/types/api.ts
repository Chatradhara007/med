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

export interface DocumentMetadata {
  id: string;
  name: string;
  type: string;
  status: 'ready' | 'processing' | 'failed';
  uploadedAt: string;
}

export interface PatientRecord {
  patient: Patient;
  alerts: Alert[];
  carePlan: CarePlanItem[];
  recentDocuments: DocumentMetadata[];
}
