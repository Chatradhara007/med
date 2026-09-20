import { apiClient } from './client';
import type { DocumentMetadata, CreateDocumentRequest, CreateDocumentResponse } from '../types/api';

/**
 * Creates a new document record and returns the doc_id + presigned S3 upload URL.
 * Caller must then call uploadToS3() to push the file bytes.
 */
export const createDocument = async (req: CreateDocumentRequest): Promise<CreateDocumentResponse> => {
  return await apiClient.createDocument(req);
};

/**
 * Upload the file bytes directly to S3 via the presigned URL.
 * Does NOT go through API Gateway.
 */
export const uploadToS3 = async (uploadUrl: string, file: File): Promise<void> => {
  return await apiClient.uploadToS3(uploadUrl, file);
};

/**
 * Get document detail (status, page_urls, error) for a specific document.
 */
export const getDocument = async (id: string): Promise<DocumentMetadata> => {
  return await apiClient.getDocument(id);
};

/** Backend terminal statuses — polling should stop on these */
export const TERMINAL_STATUSES = new Set([
  'ready',
  'review_required',
  'unsupported',
  'failed',
]);

/**
 * Poll GET /documents/{id} until a terminal status is reached.
 * Returns the final DocumentMetadata.
 * @param id - doc_id
 * @param intervalMs - polling interval (default 3000)
 * @param maxAttempts - max polls before giving up
 */
export const pollDocumentUntilTerminal = async (
  id: string,
  intervalMs = 3000,
  maxAttempts = 60,
): Promise<DocumentMetadata> => {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const doc = await getDocument(id);
    if (TERMINAL_STATUSES.has(doc.status)) {
      return doc;
    }
    await new Promise<void>((r) => setTimeout(r, intervalMs));
  }
  // Return last known state even if not terminal
  return getDocument(id);
};

/**
 * Delete a document from patient record and storage.
 */
export const deleteDocument = async (id: string): Promise<void> => {
  return await apiClient.deleteDocument(id);
};
