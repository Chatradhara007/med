import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { createDocument, uploadToS3, getDocument, TERMINAL_STATUSES } from '../../../api/documents';
import { submitSubstitution } from '../../../api/medicine';
import { CameraCapture } from '../components/CameraCapture';
import '../Medicine.css';

type ScanStep = 'capture' | 'uploading' | 'processing' | 'submitting' | 'error';

export const MedicineScannerPage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<ScanStep>('capture');
  const [stepMessage, setStepMessage] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Manual entry fallback
  const [manualBrand, setManualBrand] = useState('');
  const [manualStrength, setManualStrength] = useState('');
  const [showManual, setShowManual] = useState(false);
  const [manualLoading, setManualLoading] = useState(false);

  /**
   * Full upload flow for medicine image:
   * 1. POST /documents → get doc_id + upload_url
   * 2. PUT image to S3 presigned URL
   * 3. Poll GET /documents/{doc_id} until ready
   * 4. POST /substitution { doc_id }
   */
  const handleImageSelected = async (file: File) => {
    try {
      setError(null);

      // Step 1: Create document record
      setStep('uploading');
      setStepMessage('Requesting secure upload URL...');
      const { doc_id, upload_url } = await createDocument({
        filename: file.name,
        content_type: file.type || 'image/jpeg',
      });

      // Step 2: Upload image to S3
      setStepMessage('Uploading medicine image...');
      await uploadToS3(upload_url, file);

      // Step 3: Poll until terminal
      setStep('processing');
      setStepMessage('Analysing medicine image...');

      let finalDoc = await getDocument(doc_id);
      let attempts = 0;
      while (!TERMINAL_STATUSES.has(finalDoc.status) && attempts < 40) {
        await new Promise((r) => setTimeout(r, 3000));
        finalDoc = await getDocument(doc_id);
        attempts++;
      }

      if (finalDoc.status === 'failed' || finalDoc.status === 'unsupported') {
        throw new Error(finalDoc.errorReason || `Document processing ${finalDoc.status}.`);
      }

      // Step 4: Submit substitution with doc_id
      setStep('submitting');
      setStepMessage('Checking substitution options...');
      const result = await submitSubstitution({ doc_id });

      navigate('/medicine/result', { state: { result } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to analyse medicine. Please try again.';
      setError(msg);
      setStep('error');
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualBrand && !manualStrength) return;
    try {
      setManualLoading(true);
      setError(null);
      const result = await submitSubstitution({ brand: manualBrand, strength: manualStrength });
      navigate('/medicine/result', { state: { result } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to check substitution.';
      setError(msg);
    } finally {
      setManualLoading(false);
    }
  };

  const handleRetry = () => {
    setStep('capture');
    setError(null);
    setStepMessage('');
  };

  return (
    <div className="medicine-scanner-page">
      <div className="scanner-header">
        <h2>Medicine Scanner</h2>
        <Link to="/medicine/history" className="history-link">Previous Scans</Link>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button className="btn-retry" onClick={handleRetry}>Try again</button>
        </div>
      )}

      {(step === 'uploading' || step === 'processing' || step === 'submitting') && (
        <div className="scanner-loading">
          <div className="spinner" />
          <p>{stepMessage}</p>
        </div>
      )}

      {step === 'capture' && (
        <>
          <CameraCapture onImageSelected={handleImageSelected} />

          <div className="manual-entry-section">
            <button
              className="btn-manual-toggle"
              onClick={() => setShowManual((v) => !v)}
            >
              {showManual ? 'Hide manual entry' : 'Enter brand & strength manually'}
            </button>

            {showManual && (
              <form className="manual-entry-form" onSubmit={handleManualSubmit}>
                <div className="manual-field">
                  <label>Brand name</label>
                  <input
                    type="text"
                    value={manualBrand}
                    onChange={(e) => setManualBrand(e.target.value)}
                    placeholder="e.g. Tylenol"
                  />
                </div>
                <div className="manual-field">
                  <label>Strength</label>
                  <input
                    type="text"
                    value={manualStrength}
                    onChange={(e) => setManualStrength(e.target.value)}
                    placeholder="e.g. 500mg"
                  />
                </div>
                <button type="submit" className="btn-check" disabled={manualLoading}>
                  {manualLoading ? 'Checking...' : 'Check Substitutions'}
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </div>
  );
};
