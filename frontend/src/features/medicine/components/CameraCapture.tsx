import { useState, useRef } from 'react';

interface Props {
  onImageSelected: (file: File) => void;
}

export const CameraCapture = ({ onImageSelected }: Props) => {
  const [preview, setPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPreview(URL.createObjectURL(file));
    }
  };

  const handleRetake = () => {
    setPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = () => {
    const file = fileInputRef.current?.files?.[0];
    if (file) onImageSelected(file);
  };

  return (
    <div className="camera-capture-container">
      {!preview ? (
        <div className="capture-prompt">
          <div className="capture-icon">📷</div>
          <h3>Scan Medicine</h3>
          <p>Take a clear photo of the medicine strip or packaging.</p>
          <label className="btn-capture">
            Take Photo / Choose File
            <input 
              ref={fileInputRef}
              type="file" 
              accept="image/*" 
              capture="environment" 
              onChange={handleFileChange} 
              hidden 
            />
          </label>
        </div>
      ) : (
        <div className="capture-preview">
          <img src={preview} alt="Medicine preview" className="preview-image" />
          <div className="preview-actions">
            <button className="btn-retake" onClick={handleRetake}>Retake</button>
            <button className="btn-submit" onClick={handleSubmit}>Analyze Medicine</button>
          </div>
        </div>
      )}
    </div>
  );
};
