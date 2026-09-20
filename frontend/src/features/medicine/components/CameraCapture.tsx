import { useState, useRef, useEffect, useCallback } from 'react';

interface Props {
  onImageSelected: (file: File) => void;
}

export const CameraCapture = ({ onImageSelected }: Props) => {
  const [mode, setMode] = useState<'prompt' | 'camera' | 'preview'>('prompt');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const startCamera = useCallback(async (facing: 'environment' | 'user' = 'environment') => {
    stopCamera();
    setCameraError(null);
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera access is not supported in this browser environment.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      streamRef.current = stream;
      setMode('camera');
      // Give React a tick to mount video element
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
      }, 50);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unable to access camera device.';
      setCameraError(msg);
      setMode('prompt');
    }
  }, [stopCamera]);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  const handleSnap = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const file = new File([blob], `strip_scan_${Date.now()}.jpg`, { type: 'image/jpeg' });
          const url = URL.createObjectURL(file);
          setPreviewUrl(url);
          setCapturedFile(file);
          stopCamera();
          setMode('preview');
        }
      },
      'image/jpeg',
      0.92
    );
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      stopCamera();
      setPreviewUrl(URL.createObjectURL(file));
      setCapturedFile(file);
      setMode('preview');
    }
  };

  const handleRetake = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setCapturedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setMode('prompt');
  };

  const handleSubmit = () => {
    if (capturedFile) {
      onImageSelected(capturedFile);
    }
  };

  const toggleCameraFacing = () => {
    const next = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(next);
    startCamera(next);
  };

  return (
    <div className="camera-capture-container">
      {/* Hidden processing canvas & file input */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/jpg"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {mode === 'prompt' && (
        <div className="capture-prompt">
          <div className="capture-icon">📷</div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
            Capture Medicine Packaging
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--ct-text-secondary)', marginTop: '6px', maxWidth: '380px', lineHeight: 1.5 }}>
            Open your device camera to snap a photo of the medicine strip or packaging, or select an existing image file.
          </p>

          {cameraError && (
            <div
              style={{
                margin: '12px 0 16px',
                padding: '8px 14px',
                backgroundColor: 'var(--ct-blocked-bg)',
                border: '1px solid var(--ct-blocked-border)',
                borderRadius: 'var(--ct-radius-sm)',
                color: 'var(--ct-blocked)',
                fontSize: '12.5px',
              }}
            >
              Camera note: {cameraError} (You can choose an image file below).
            </div>
          )}

          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={() => startCamera(facingMode)}
              className="btn-snap"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              <span>🎥</span>
              <span>Open Live Camera</span>
            </button>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="btn-file-select"
            >
              <span>📁</span>
              <span>Choose Photo from Device</span>
            </button>
          </div>
        </div>
      )}

      {mode === 'camera' && (
        <div>
          <div className="camera-preview-wrapper" style={{ position: 'relative' }}>
            <video
              ref={videoRef}
              className="camera-video"
              autoPlay
              playsInline
              muted
              style={{ backgroundColor: '#000', maxHeight: '380px' }}
            />
            {/* Viewfinder Guide Overlay */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '75%',
                height: '65%',
                border: '2px dashed rgba(96, 165, 250, 0.7)',
                borderRadius: '12px',
                pointerEvents: 'none',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                paddingTop: '8px',
              }}
            >
              <span
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.65)',
                  color: '#93c5fd',
                  padding: '3px 10px',
                  borderRadius: '4px',
                  fontSize: '11.5px',
                  fontWeight: 600,
                }}
              >
                Center medicine strip inside frame
              </span>
            </div>
          </div>

          <div className="camera-controls">
            <button
              type="button"
              onClick={handleSnap}
              className="btn-snap"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              <span>📸</span>
              <span>Capture Photo</span>
            </button>

            <button
              type="button"
              onClick={toggleCameraFacing}
              className="btn-file-select"
              title="Flip between front and rear camera"
            >
              <span>🔄 Flip</span>
            </button>

            <button
              type="button"
              onClick={() => {
                stopCamera();
                setMode('prompt');
              }}
              className="btn-file-select"
            >
              <span>Cancel</span>
            </button>
          </div>
        </div>
      )}

      {mode === 'preview' && previewUrl && (
        <div className="capture-preview">
          <img src={previewUrl} alt="Captured medicine packaging" className="preview-image" style={{ maxHeight: '380px' }} />
          <div className="preview-actions">
            <button type="button" className="btn-secondary" onClick={handleRetake}>
              Retake / Choose Another
            </button>
            <button type="button" className="btn-primary" onClick={handleSubmit}>
              Analyze Medicine &amp; Substitutes →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
