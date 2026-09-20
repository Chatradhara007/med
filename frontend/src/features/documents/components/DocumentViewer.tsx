import { useState } from 'react';
import type { SourceMetadata } from '../../../types/api';

interface Props {
  /** Page image URLs from GET /documents/{id} response */
  pageUrls: string[];
  /** Page number to jump to when a source is highlighted (1-indexed) */
  sourceHighlight?: SourceMetadata | null;
}

/**
 * Converts backend bbox [ymin, xmin, ymax, xmax] (0-1000 scale)
 * to CSS percentage-based overlay coordinates.
 */
function bboxToStyle(bbox: [number, number, number, number]): React.CSSProperties {
  const [ymin, xmin, ymax, xmax] = bbox;
  return {
    top: `${ymin / 10}%`,
    left: `${xmin / 10}%`,
    width: `${(xmax - xmin) / 10}%`,
    height: `${(ymax - ymin) / 10}%`,
  };
}

export const DocumentViewer = ({ pageUrls, sourceHighlight }: Props) => {
  const [currentPage, setCurrentPage] = useState(1);

  // When a new source highlight arrives, jump to its page
  const displayPage = sourceHighlight?.page ?? currentPage;
  const pageIndex = displayPage - 1;
  const pageUrl = pageUrls && pageUrls.length > 0 ? pageUrls[pageIndex] || pageUrls[0] : null;

  if (!pageUrls || pageUrls.length === 0) {
    if (!sourceHighlight) {
      return (
        <div className="doc-viewer-container">
          <div className="doc-viewer-empty">
            <p>Select "Show original" on an extracted field to view its source.</p>
          </div>
        </div>
      );
    }
    return (
      <div className="doc-viewer-container">
        <div className="doc-viewer-empty">
          <p>Document pages are not yet available. Try again once processing is complete.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="doc-viewer-container">
      <div className="doc-viewer-toolbar">
        <span className="doc-page-label">
          Page {displayPage} of {pageUrls.length}
        </span>
        {pageUrls.length > 1 && (
          <div className="doc-page-nav">
            <button
              className="btn-page-nav"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={displayPage <= 1}
              aria-label="Previous page"
            >
              ←
            </button>
            <button
              className="btn-page-nav"
              onClick={() => setCurrentPage((p) => Math.min(pageUrls.length, p + 1))}
              disabled={displayPage >= pageUrls.length}
              aria-label="Next page"
            >
              →
            </button>
          </div>
        )}
      </div>

      <div className="doc-page-wrapper">
        {pageUrl ? (
          <>
            <img
              src={pageUrl}
              alt={`Document page ${displayPage}`}
              className="doc-page-image"
            />
            {sourceHighlight?.bbox && (
              <div
                className="bbox-highlight"
                style={bboxToStyle(sourceHighlight.bbox)}
                aria-label="Source region"
              >
                <span className="bbox-label">Source</span>
              </div>
            )}
          </>
        ) : (
          <div className="doc-viewer-empty">
            <p>Page {displayPage} could not be loaded.</p>
          </div>
        )}
      </div>
    </div>
  );
};
