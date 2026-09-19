import type { SourceMetadata } from '../../../types/api';

interface Props {
  documentName: string;
  sourceHighlight?: SourceMetadata | null;
}

export const DocumentViewer = ({ documentName, sourceHighlight }: Props) => {
  if (!sourceHighlight) {
    return (
      <div className="doc-viewer-container">
        <div className="doc-viewer-empty">
          <p>Select "Show original" on an extracted field to view its source.</p>
        </div>
      </div>
    );
  }

  const { page, bbox } = sourceHighlight;
  
  return (
    <div className="doc-viewer-container">
      <div className="doc-viewer-toolbar">
        <h4>{documentName}</h4>
        {page && <span>Page {page}</span>}
      </div>
      
      <div className="doc-page-mock">
        <div className="doc-page-content">
          <p className="mock-text-bg">[Simulated Document Page Content]</p>
          <p className="mock-text-bg">Patient medical history and narrative text is rendered here visually.</p>
          
          {bbox && (
            <div 
              className="bbox-highlight" 
              style={{
                left: `${bbox[0]}%`,
                top: `${bbox[1]}%`,
                width: `${bbox[2]}%`,
                height: `${bbox[3]}%`
              }}
            >
              <span className="bbox-label">Source</span>
            </div>
          )}
        </div>
        {!page && (
          <div className="doc-no-page-overlay">
            <p>Specific page information unavailable.</p>
          </div>
        )}
      </div>
    </div>
  );
};
