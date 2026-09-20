import { useState, useRef } from 'react';
import { createDocument, uploadToS3, deleteDocument } from '../../../api/documents';

interface Props {
  onUploadComplete: (docId: string) => void;
}

export const UploadDocument = ({ onUploadComplete }: Props) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleCancel = () => {
    setFile(null);
    setError(null);
    setUploadProgress('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleUpload = async () => {
    if (!file) return;
    // Registered before the bytes exist. If the PUT then fails, this row is
    // what has to be cleaned up.
    let registeredDocId: string | null = null;
    try {
      setUploading(true);
      setError(null);

      // Step 1: Request presigned upload URL from backend
      setUploadProgress('Requesting secure presigned S3 URL...');
      const res = await createDocument({
        filename: file.name,
        content_type: file.type || 'application/pdf',
      });
      registeredDocId = res.doc_id;

      // Step 2: PUT file directly to S3 using the presigned URL
      setUploadProgress('Encrypting & uploading to S3 storage bucket...');
      await uploadToS3(res.upload_url, file);

      setUploadProgress('Uploaded! Ingestion state machine started...');
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      onUploadComplete(res.doc_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';

      // The pipeline is driven by the S3 object landing, so a document whose
      // PUT failed never starts one: it sits at `uploading` forever, showing
      // as In-Flight in the list with nothing behind it. Drop the row so a
      // failed upload leaves no trace and the message below is the only
      // outcome the patient has to act on.
      if (registeredDocId) {
        try {
          await deleteDocument(registeredDocId);
        } catch {
          // Best effort. A stranded row is better than losing the real error.
        }
      }

      setError(
        `Upload failed: ${msg}. The file was not stored -- please try again.`,
      );
    } finally {
      setUploading(false);
      setUploadProgress('');
    }
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      style={{
        border: '2px dashed',
        borderColor: isDragOver ? '#3b82f6' : file ? 'var(--ct-primary-border)' : 'var(--ct-border)',
        borderRadius: 'var(--ct-radius-lg)',
        padding: '36px 24px',
        backgroundColor: isDragOver ? 'var(--ct-primary-subtle)' : 'var(--ct-surface)',
        textAlign: 'center',
        transition: 'all var(--ct-transition-fast)',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,image/*"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {!file ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '50%',
              backgroundColor: 'var(--ct-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
              boxShadow: 'var(--ct-shadow-sm)',
            }}
          >
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>

          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--ct-text-primary)', margin: 0 }}>
              Upload Clinical Document
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--ct-text-muted)', marginTop: '4px', maxWidth: '420px', lineHeight: 1.5 }}>
              Drag and drop your PDF discharge summary, lab report, or prescription here, or browse your files.
            </p>
          </div>

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="btn-primary"
            style={{ padding: '9px 20px', fontSize: '13.5px' }}
          >
            Choose File to Upload
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: 'var(--ct-text-muted)', marginTop: '6px' }}>
            <span>Supports: PDF, PNG, JPEG</span>
            <span>•</span>
            <span>Zero PHI in Logs</span>
            <span>•</span>
            <span>Provenance Auto-Tagged</span>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 20px',
              backgroundColor: 'var(--ct-surface-elevated)',
              borderRadius: 'var(--ct-radius-md)',
              border: '1px solid var(--ct-border)',
              maxWidth: '480px',
              width: '100%',
              textAlign: 'left',
            }}
          >
            <div style={{ fontSize: '24px' }}>📄</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, color: 'var(--ct-text-primary)', fontSize: '13.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {file.name}
              </div>
              <div style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)' }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB • {file.type || 'Document'}
              </div>
            </div>
          </div>

          {uploadProgress && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12.5px', color: '#60a5fa' }}>
              <span className="pulse-dot" />
              <span>{uploadProgress}</span>
            </div>
          )}

          {error && (
            <div style={{ color: 'var(--ct-blocked)', fontSize: '13px', backgroundColor: 'var(--ct-blocked-bg)', padding: '8px 16px', borderRadius: 'var(--ct-radius-sm)' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              type="button"
              onClick={handleCancel}
              disabled={uploading}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleUpload}
              disabled={uploading}
              className="btn-primary"
            >
              {uploading ? 'Processing Upload...' : 'Submit to Ingest Pipeline'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
