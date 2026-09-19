import type { SourceMetadata } from '../../../types/api';

interface Props {
  source: SourceMetadata;
  confidence: number;
}

export const ProvenanceInfo = ({ source, confidence }: Props) => {
  const confPercent = Math.round(confidence * 100);
  const isHighConf = confidence >= 0.85;

  return (
    <div className="provenance-info">
      <div className="prov-header">
        <span className="prov-label">Source</span>
        <span className={`prov-confidence ${isHighConf ? 'high' : 'low'}`}>
          Confidence: {confPercent}%
        </span>
      </div>
      
      <div className="prov-details">
        <span className="prov-doc">{source.doc_name || `Doc: ${source.doc_id}`}</span>
        {source.page && <span className="prov-page">• Page {source.page}</span>}
      </div>
      
      {source.verbatim && (
        <blockquote className="prov-verbatim">
          "{source.verbatim}"
        </blockquote>
      )}
    </div>
  );
};
