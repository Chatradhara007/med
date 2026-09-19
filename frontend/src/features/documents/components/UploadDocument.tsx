import { useState } from 'react';
import { createDocument } from '../../../api/documents';

interface Props {
  onUploadStarted: () => void;
}

export const UploadDocument = ({ onUploadStarted }: Props) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
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
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploading(true);
      setError(null);
      // Simulating getting the presigned URL
      const res = await createDocument({
        filename: file.name,
        content_type: file.type || 'application/pdf'
      });
      // (Mock) We would now upload the file to `res.upload_url`
      console.log(`Mock uploading ${file.name} to ${res.upload_url}`);
      
      // Artificial delay for upload UX
      await new Promise(r => setTimeout(r, 1000));
      
      setFile(null);
      onUploadStarted(); // Notify parent to refresh list
    } catch {
      setError('Failed to initiate upload. Please try again.');
    } finally {
      setUploading(false);
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
