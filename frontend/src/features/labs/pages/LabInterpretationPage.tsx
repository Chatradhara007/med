import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { LabInterpretationReport, LabFinding } from '../../../types/api';
import { interpretLabs } from '../../../api/labs';
import { CardSkeleton } from '../../../components/ui';

const FindingCard = ({ finding }: { finding: LabFinding }) => {
  const isAbnormal =
    finding.status === 'below' ||
    finding.status === 'above' ||
    finding.status === 'high' ||
    finding.status === 'low' ||
    finding.status === 'critical';

  const refLow = finding.ref_low;
  const refHigh = finding.ref_high;
  const numVal = typeof finding.value === 'number' ? finding.value : parseFloat(String(finding.value));
  const hasValidRange = !isNaN(numVal) && refLow != null && refHigh != null && refHigh > refLow;

  // Calculate percentage along the gauge (clamped 0 to 100)
  let gaugePercent = 50;
  if (hasValidRange) {
    const rangeSpan = refHigh! - refLow!;
    const offset = numVal - refLow!;
    gaugePercent = Math.max(5, Math.min(95, (offset / rangeSpan) * 100));
  }

  const statusLabel = finding.status === 'within' ? 'NORMAL' : (finding.status || 'NORMAL').toUpperCase();

  return (
    <div
      style={{
        padding: '20px',
        backgroundColor: 'var(--ct-surface)',
        border: '1px solid',
        borderColor: isAbnormal ? 'var(--ct-abnormal-border)' : 'var(--ct-border)',
        borderRadius: 'var(--ct-radius-md)',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        boxShadow: 'var(--ct-shadow-sm)',
      }}
    >
      {/* Finding Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
              {finding.analyte}
            </h4>
            {finding.rank && (
              <span style={{ fontSize: '11px', color: 'var(--ct-text-muted)', fontFamily: 'monospace' }}>
                Priority #{finding.rank}
              </span>
            )}
          </div>
          {finding.ref_source && (
            <div style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)', marginTop: '2px' }}>
              Standard: {finding.ref_source}
            </div>
          )}
        </div>

        <span className={`ct-badge ${isAbnormal ? 'abnormal' : 'confirmed'}`}>
          {statusLabel}
        </span>
      </div>

      {/* Numeric Value & Visual Gauge */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span className="tabular" style={{ fontSize: '1.6rem', fontWeight: 700, color: isAbnormal ? 'var(--ct-abnormal)' : 'var(--ct-text-primary)' }}>
            {finding.value}
          </span>
          <span style={{ fontSize: '13px', color: 'var(--ct-text-secondary)' }}>
            {finding.unit || ''}
          </span>
          {refLow != null && refHigh != null && (
            <span style={{ fontSize: '12px', color: 'var(--ct-text-muted)', marginLeft: '8px' }}>
              (Ref: {refLow} – {refHigh} {finding.unit || ''})
            </span>
          )}
        </div>

        {/* Visual Reference Gauge */}
        {hasValidRange && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'var(--ct-surface-elevated)',
                borderRadius: 'var(--ct-radius-pill)',
                position: 'relative',
                overflow: 'visible',
              }}
            >
              {/* Normal range highlight in center */}
              <div
                style={{
                  position: 'absolute',
                  left: '20%',
                  right: '20%',
                  top: 0,
                  bottom: 0,
                  backgroundColor: 'rgba(16, 185, 129, 0.25)',
                  borderRadius: 'var(--ct-radius-pill)',
                }}
              />
              {/* Patient value marker */}
              <div
                style={{
                  position: 'absolute',
                  left: `${gaugePercent}%`,
                  top: '-4px',
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  backgroundColor: isAbnormal ? 'var(--ct-abnormal)' : 'var(--ct-confirmed)',
                  border: '2px solid white',
                  transform: 'translateX(-50%)',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
                }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10.5px', color: 'var(--ct-text-muted)' }}>
              <span>Low ({refLow})</span>
              <span style={{ color: 'var(--ct-confirmed)' }}>Normal Range</span>
              <span>High ({refHigh})</span>
            </div>
          </div>
        )}
      </div>

      {/* Clinical Interpretation Narrative */}
      {finding.explanation && (
        <div
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--ct-surface-elevated)',
            borderRadius: 'var(--ct-radius-sm)',
            borderLeft: '3px solid #3b82f6',
            fontSize: '13px',
            color: 'var(--ct-text-primary)',
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: '#60a5fa', display: 'block', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>
            Clinical Context Interpretation
          </strong>
          {finding.explanation}
        </div>
      )}

      {/* Linked Diagnoses & Medications */}
      {(finding.context_diagnoses?.length || finding.context_medications?.length) ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '12px', paddingTop: '6px', borderTop: '1px solid var(--ct-border-subtle)' }}>
          {finding.context_diagnoses?.length ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: 'var(--ct-text-muted)' }}>Related Condition:</span>
              <span style={{ color: 'var(--ct-text-primary)', fontWeight: 500 }}>
                {finding.context_diagnoses.join(', ')}
              </span>
            </div>
          ) : null}

          {finding.context_medications?.length ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: 'var(--ct-text-muted)' }}>Related Medication:</span>
              <span style={{ color: '#60a5fa', fontWeight: 500 }}>
                💊 {finding.context_medications.join(', ')}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Confidence Footer */}
      {finding.confidence != null && (
        <div style={{ fontSize: '11px', color: 'var(--ct-text-muted)', display: 'flex', justifyContent: 'flex-end' }}>
          Extraction Confidence: <strong style={{ color: 'var(--ct-text-secondary)', marginLeft: '4px' }}>{Math.round(finding.confidence * 100)}%</strong>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Header */}
      <div>
        <Link
          to="/"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--ct-text-muted)',
            fontSize: '13px',
            textDecoration: 'none',
            marginBottom: '12px',
          }}
        >
          ← Back to Timeline
        </Link>
        <h1 style={{ fontSize: '1.65rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ct-text-primary)', margin: 0 }}>
          Clinical Laboratory Interpretation
        </h1>
        <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', marginTop: '4px', maxWidth: '650px', lineHeight: 1.5 }}>
          Cross-references extracted lab analytes against standardized reference intervals and your active episode diagnoses and medications.
        </p>
      </div>

      {/* Initial Interpretation Call-to-Action */}
      {!report && !loading && (
        <div
          className="ct-card"
          style={{
            padding: '36px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '16px',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: 'var(--ct-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8',
              fontSize: '24px',
            }}
          >
            🧪
          </div>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--ct-text-primary)', margin: 0 }}>
              Analyze Episode Lab Results
            </h3>
            <p style={{ fontSize: '13.5px', color: 'var(--ct-text-secondary)', maxWidth: '460px', marginTop: '6px', lineHeight: 1.5 }}>
              Compile all extracted laboratory values in your partition and calculate deviation scores against clinical reference ranges.
            </p>
          </div>

          <button onClick={handleInterpret} className="btn-primary" style={{ padding: '10px 24px', fontSize: '14px' }}>
            Run Clinical Lab Interpreter
          </button>

          <p style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)', margin: 0 }}>
            Deterministic reference analysis • Zero generative clinical diagnostic invention
          </p>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ padding: '16px', backgroundColor: 'var(--ct-primary-subtle)', borderRadius: 'var(--ct-radius-md)', color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="pulse-dot" />
            <span>Analyzing laboratory observations against reference ranges and active conditions...</span>
          </div>
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="ct-card" style={{ borderColor: 'var(--ct-blocked-border)' }}>
          <p style={{ color: 'var(--ct-blocked)', margin: 0 }}>{error}</p>
          <button onClick={handleInterpret} className="btn-primary" style={{ marginTop: '12px' }}>
            Retry Analysis
          </button>
        </div>
      )}

      {/* Interpreted Report View */}
      {report && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Summary Stat Banner */}
          <div
            className="ct-card"
            style={{
              padding: '20px 24px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
              <div>
                <span style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Total Findings
                </span>
                <div className="tabular" style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--ct-text-primary)' }}>
                  {report.total_findings}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '11.5px', color: 'var(--ct-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Abnormal / Out of Range
                </span>
                <div className="tabular" style={{ fontSize: '1.5rem', fontWeight: 700, color: report.abnormal_count > 0 ? 'var(--ct-abnormal)' : 'var(--ct-confirmed)' }}>
                  {report.abnormal_count}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '12px', color: 'var(--ct-text-muted)' }}>
                Generated {new Date(report.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <button onClick={handleInterpret} disabled={loading} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>
                ↻ Refresh Analysis
              </button>
            </div>
          </div>

          {/* Cross-Module Alerts if any */}
          {report.cross_module_alerts.length > 0 && (
            <div
              style={{
                padding: '16px 20px',
                backgroundColor: 'var(--ct-review-bg)',
                border: '1px solid var(--ct-review-border)',
                borderRadius: 'var(--ct-radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <strong style={{ color: 'var(--ct-review)', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                ⚠️ Cross-Module Clinical Alerts
              </strong>
              {report.cross_module_alerts.map((alert, i) => (
                <p key={i} style={{ color: 'var(--ct-text-primary)', margin: 0, fontSize: '13.5px' }}>
                  {alert}
                </p>
              ))}
            </div>
          )}

          {/* Top Priority Findings */}
          {report.top_findings.length > 0 && (
            <section>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--ct-abnormal)' }} />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--ct-text-primary)', margin: 0 }}>
                  Priority Findings ({report.top_findings.length})
                </h2>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {report.top_findings.map((finding, i) => (
                  <FindingCard key={finding.analyte + i} finding={finding} />
                ))}
              </div>
            </section>
          )}

          {/* Other Findings */}
          {report.all_findings.length > report.top_findings.length && (
            <section>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--ct-text-primary)', marginBottom: '14px' }}>
                All Laboratory Analytes
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {report.all_findings
                  .filter((f) => !report.top_findings.some((t) => t.analyte === f.analyte))
                  .map((finding, i) => (
                    <FindingCard key={finding.analyte + i} finding={finding} />
                  ))}
              </div>
            </section>
          )}

          {/* Medical Advisory Banner */}
          <div
            style={{
              padding: '16px 20px',
              backgroundColor: 'var(--ct-surface)',
              border: '1px solid var(--ct-border)',
              borderRadius: 'var(--ct-radius-md)',
              fontSize: '12px',
              color: 'var(--ct-text-muted)',
              lineHeight: 1.5,
            }}
          >
            <strong style={{ color: 'var(--ct-text-secondary)', display: 'block', marginBottom: '2px' }}>
              CLINICAL ADVISORY NOTE
            </strong>
            CareThread restructures and contextualizes laboratory findings against baseline documentation. It does not provide medical diagnoses or alter treatment regimens. Discuss any out-of-range values directly with your care team.
          </div>
        </div>
      )}
    </div>
  );
};
