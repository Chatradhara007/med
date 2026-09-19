import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { submitSubstitution } from '../../../api/medicine';
import { CameraCapture } from '../components/CameraCapture';
import '../Medicine.css';

export const MedicineScannerPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImageSelected = async (file: File) => {
    try {
      setLoading(true);
      setError(null);
      const res = await submitSubstitution({ brand: file.name }); // Mock trigger
      
      // Navigate to results page with data in state
      navigate('/medicine/result', { state: { result: res } });
    } catch {
      setError('Failed to analyze medicine. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="medicine-scanner-page">
      <div className="scanner-header">
        <h2>Medicine Scanner</h2>
        <Link to="/medicine/history" className="history-link">Previous Scans</Link>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="scanner-loading">
          <div className="spinner"></div>
          <p>Analyzing image and checking substitutions...</p>
        </div>
      ) : (
        <CameraCapture onImageSelected={handleImageSelected} />
      )}
    </div>
  );
};
