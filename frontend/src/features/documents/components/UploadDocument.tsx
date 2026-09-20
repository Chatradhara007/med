import { useState } from 'react';
import { createDocument, uploadToS3 } from '../../../api/documents';

interface Props {
  onUploadComplete: (docId: string) => void;
}

export const UploadDocument = ({ onUploadComplete }: Props) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleCancel = () => {
    setFile(null);
    setError(null);
    setUploadProgress('');
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploading(true);
      setError(null);

      // Step 1: Request presigned upload URL from backend
      setUploadProgress('Requesting upload URL...');
      const res = await createDocument({
        filename: file.name,
        content_type: file.type || 'application/pdf',
      });

      // Step 2: PUT file directly to S3 using the presigned URL
      setUploadProgress('Uploading to secure storage...');
      await uploadToS3(res.upload_url, file);

      setUploadProgress('Upload complete. Processing started...');
      setFile(null);
      onUploadComplete(res.doc_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(`Failed to upload: ${msg}`);
    } finally {
      setUploading(false);
      setUploadProgress('');
    }
  };

  return (
    <div className="upload-zone">
      {!file ? (
        <div className="upload-prompt">
          <label className="upload-btn">
            Select Document
            <input type="file" accept=".pdf,image/*" onChange={handleFileChange} hidden />
          </label>
          <p>Upload a discharge summary, lab report, or other medical document to get started.</p>
        </div>
      ) : (
        <div className="upload-active">
          <div className="selected-file-info">
            <span className="file-icon">📄</span>
            <div className="file-details">
              <strong>{file.name}</strong>
              <small>{(file.size / 1024 / 1024).toFixed(2)} MB</small>
            </div>
          </div>

          {uploadProgress && <div className="upload-progress">{uploadProgress}</div>}
          {error && <div className="upload-error">{error}</div>}

          <div className="upload-actions">
            <button className="btn-cancel" onClick={handleCancel} disabled={uploading}>Cancel</button>
            <button className="btn-upload" onClick={handleUpload} disabled={uploading}>
              {uploading ? 'Uploading...' : 'Start Upload'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
