import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { LabInterpretationReport, LabFinding } from '../../../types/api';
import { interpretLabs } from '../../../api/labs';

const FindingCard = ({ finding }: { finding: LabFinding }) => {
  const isAbnormal = finding.status && finding.status !== 'normal';
  const refRange = finding.ref_low != null && finding.ref_high != null
    ? `${finding.ref_low} – ${finding.ref_high} ${finding.unit || ''}`
    : null;

  return (
    <div className={`lab-finding-card ${isAbnormal ? 'abnormal' : 'normal'}`}>
      <div className="finding-header">
        <div className="finding-analyte">
          <strong>{finding.analyte}</strong>
          {finding.rank && <span className="finding-rank">#{finding.rank}</span>}
        </div>
        {finding.status && (
          <span className={`finding-status-badge ${finding.status}`}>
            {finding.status.toUpperCase()}
          </span>
        )}
      </div>

      <div className="finding-value">
        <span className="value-main">{finding.value} {finding.unit || ''}</span>
        {refRange && <span className="value-ref">Ref: {refRange}</span>}
        {finding.ref_source && <small className="ref-source">Source: {finding.ref_source}</small>}
      </div>

      {finding.explanation && (
        <p className="finding-explanation">{finding.explanation}</p>
      )}

      {(finding.context_diagnoses?.length || finding.context_medications?.length) ? (
        <div className="finding-context">
          {finding.context_diagnoses?.length ? (
            <div className="context-item">
              <label>Relevant diagnoses:</label>
              <span>{finding.context_diagnoses.join(', ')}</span>
            </div>
          ) : null}
          {finding.context_medications?.length ? (
            <div className="context-item">
              <label>Relevant medications:</label>
              <span>{finding.context_medications.join(', ')}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {finding.confidence != null && (
        <div className="finding-confidence">
          Confidence: {Math.round(finding.confidence * 100)}%
        </div>
      )}
    </div>
  );
};

export const LabInterpretationPage = () => {
  const [report, setReport] = useState<LabInterpretationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInterpret = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await interpretLabs();
      setReport(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to interpret lab results.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lab-interpretation-page">
      <div className="lab-nav">
        <Link to="/" className="back-link">← Back to Timeline</Link>
      </div>

      <header className="lab-header">
        <h2>Lab Interpretation</h2>
        <p className="lab-subtitle">AI-assisted interpretation of your lab results in context of your diagnoses and medications.</p>
      </header>

      {!report && !loading && (
        <div className="lab-cta">
          <p>Your lab results will be interpreted in context of your active diagnoses and medications.</p>
          <button className="btn-interpret" onClick={handleInterpret}>
            Interpret My Labs
          </button>
          <p className="advisory-note">
            This is for informational purposes only. Consult your clinician for medical advice.
          </p>
        </div>
      )}

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p>Interpreting your lab results...</p>
        </div>
      )}

      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button className="btn-retry" onClick={handleInterpret}>Try again</button>
        </div>
      )}

      {report && (
        <div className="lab-report">
          <div className="lab-summary-bar">
            <div className="summary-stat">
              <span className="stat-number">{report.total_findings}</span>
              <span className="stat-label">Total findings</span>
            </div>
            <div className="summary-stat abnormal">
              <span className="stat-number">{report.abnormal_count}</span>
              <span className="stat-label">Abnormal</span>
            </div>
            <div className="summary-stat">
              <small>Generated: {new Date(report.generated_at).toLocaleString()}</small>
            </div>
          </div>

          {report.cross_module_alerts.length > 0 && (
            <section className="lab-alerts-section">
              <h3>⚠️ Cross-Module Alerts</h3>
              {report.cross_module_alerts.map((alert, i) => (
                <div key={i} className="alert-card warning">
                  <p>{alert}</p>
                </div>
              ))}
            </section>
          )}

          {report.top_findings.length > 0 && (
            <section className="lab-findings-section">
              <h3>Top Findings</h3>
              {report.top_findings.map((finding, i) => (
                <FindingCard key={finding.analyte + i} finding={finding} />
              ))}
            </section>
          )}

          {report.all_findings.length > report.top_findings.length && (
            <section className="lab-all-findings-section">
              <h3>All Findings</h3>
              {report.all_findings
                .filter((f) => !report.top_findings.some((t) => t.analyte === f.analyte))
                .map((finding, i) => (
                  <FindingCard key={finding.analyte + i} finding={finding} />
                ))}
            </section>
          )}

          <button className="btn-reinterpret" onClick={handleInterpret} disabled={loading}>
            ↻ Re-interpret
          </button>

          <div className="advisory-banner">
            <strong>IMPORTANT</strong>
            <p>This interpretation is generated by AI and is for informational purposes only. Contact your clinician for medical advice.</p>
          </div>
        </div>
      )}
    </div>
  );
};
