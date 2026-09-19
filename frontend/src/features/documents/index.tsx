import { Link, Outlet } from 'react-router-dom';

export const DocumentsList = () => {
  return (
    <div className="feature-page">
      <h2>Documents</h2>
      <ul>
        <li><Link to="/documents/1">Document 1</Link></li>
      </ul>
    </div>
  );
};

export const DocumentDetail = () => {
  return (
    <div className="feature-page">
      <h2>Document Detail</h2>
      <p>Extracted entities with provenance will be here.</p>
      <Link to="/documents">Back to Documents</Link>
    </div>
  );
};

export const DocumentsLayout = () => <Outlet />;
