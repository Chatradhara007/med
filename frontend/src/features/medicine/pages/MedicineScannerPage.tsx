import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createDocument,
  uploadToS3,
  pollDocumentUntilTerminal,
} from '../../../api/documents';
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

  const handleImageSelected = async (file: File) => {
    try {
      setError(null);

      // Step 1: Create document record
      setStep('uploading');
      setStepMessage('Requesting secure presigned upload URL...');
      const { doc_id, upload_url } = await createDocument({
        filename: file.name,
        content_type: file.type || 'image/jpeg',
      });

      // Step 2: Upload image to S3
      setStepMessage('Uploading medicine package photo to S3...');
      await uploadToS3(upload_url, file);

      // Step 3: Poll until terminal
      setStep('processing');
      setStepMessage('Multimodal AI analyzing medicine brand, active salt, and strength...');

      const finalDoc = await pollDocumentUntilTerminal(
        doc_id,
        3000,
        180,
      );

      if (finalDoc.status === 'failed' || finalDoc.status === 'unsupported') {
        throw new Error(
          finalDoc.errorReason ||
          `Document processing ${finalDoc.status}.`
        );
      }

      // Step 4: Submit substitution with doc_id
      setStep('submitting');
      setStepMessage('Cross-referencing formulary, NTI database, and interaction rules...');
      const result = await submitSubstitution({ doc_id });

      navigate('/medicine/result', { state: { result } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to analyze medicine. Please try again.';
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <div>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)', margin: 0 }}>
          Medicine Scanner &amp; Safety Check
        </h1>
        <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '4px', maxWidth: '650px', lineHeight: 1.5 }}>
          Scan a pharmacy strip or packaging to extract salt, check bioequivalent alternatives in stock, and enforce Narrow Therapeutic Index (NTI) safety rails.
        </p>
      </div>

      {step === 'error' && (
        <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--ct-blocked)' }}>
            <span style={{ fontSize: '18px' }}>✕</span>
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Medicine Analysis Failed</h3>
          </div>
          <p style={{ color: 'var(--ct-text-secondary)', marginTop: '8px', marginBottom: '16px' }}>{error}</p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={handleRetry} className="btn-primary">
              Try Another Scan
            </button>
            <button onClick={() => setShowManual(true)} className="btn-secondary">
              Enter Details Manually
            </button>
          </div>
        </div>
      )}

      {(step === 'uploading' || step === 'processing' || step === 'submitting') && (
        <div
          className="ct-card"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'var(--ct-primary-subtle)',
              border: '1px solid var(--ct-primary-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
              fontSize: '24px',
            }}
          >
            <span className="pulse-dot" style={{ width: '12px', height: '12px' }} />
          </div>

          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
              Analyzing Medicine Packaging
            </h3>
            <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '6px', maxWidth: '420px', lineHeight: 1.5 }}>
              {stepMessage}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--ct-text-muted)' }}>
            <span>Vision OCR</span>
            <span>→</span>
            <span>Bioequivalence</span>
            <span>→</span>
            <span>NTI Safety Rail</span>
            <span>→</span>
            <span>Interactions</span>
          </div>
        </div>
      )}

      {step === 'capture' && (
        <div style={{ display: 'grid', gridTemplateColumns: showManual ? '1fr 1fr' : '1fr', gap: '24px' }}>
          {/* Visual Scan / Upload Card */}
          <div className="ct-card">
            <div className="ct-card-header">
              <div>
                <h2 className="ct-card-title">
                  <span>Photo / Camera Scan</span>
                </h2>
                <p style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
                  Upload a photo of the medicine box, blister pack, or strip
                </p>
              </div>

              {!showManual && (
                <button
                  type="button"
                  onClick={() => setShowManual(true)}
                  className="btn-secondary"
                  style={{ fontSize: '12px', padding: '6px 12px' }}
                >
                  Switch to Manual Entry
                </button>
              )}
            </div>

            <CameraCapture onImageSelected={handleImageSelected} />
          </div>

          {/* Manual Entry Option */}
          {showManual && (
            <div className="ct-card">
              <div className="ct-card-header">
                <div>
                  <h2 className="ct-card-title">
                    <span>Manual Formulary Lookup</span>
                  </h2>
                  <p style={{ fontSize: '12.5px', color: 'var(--ct-text-muted)', margin: 0, marginTop: '2px' }}>
                    Type the brand or generic name to evaluate substitution
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setShowManual(false)}
                  style={{ background: 'none', border: 'none', color: 'var(--ct-text-muted)', cursor: 'pointer', fontSize: '14px' }}
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleManualSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: 'var(--ct-text-secondary)', marginBottom: '6px' }}>
                    Brand or Salt Name
                  </label>
                  <input
                    type="text"
                    className="ct-input"
                    placeholder="e.g. Warfarin, Lipitor, Metformin"
                    value={manualBrand}
                    onChange={(e) => setManualBrand(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: 'var(--ct-text-secondary)', marginBottom: '6px' }}>
                    Strength (optional)
                  </label>
                  <input
                    type="text"
                    className="ct-input"
                    placeholder="e.g. 5mg, 500mg, 20mg"
                    value={manualStrength}
                    onChange={(e) => setManualStrength(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  disabled={manualLoading || !manualBrand}
                  className="btn-primary"
                  style={{ marginTop: '8px' }}
                >
                  {manualLoading ? 'Checking...' : 'Check Substitution & Safety'}
                </button>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
