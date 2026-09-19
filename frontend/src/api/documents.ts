import { apiClient } from './client';
import type { DocumentMetadata, CreateDocumentRequest, CreateDocumentResponse } from '../types/api';

export const getDocuments = async (): Promise<DocumentMetadata[]> => {
  return await apiClient.getDocuments();
};

export const getDocument = async (id: string): Promise<DocumentMetadata> => {
  return await apiClient.getDocument(id);
};

export const createDocument = async (req: CreateDocumentRequest): Promise<CreateDocumentResponse> => {
  return await apiClient.createDocument(req);
};
