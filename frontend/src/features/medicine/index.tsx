import { Link, Outlet } from 'react-router-dom';

export const MedicineScanner = () => {
  return (
    <div className="feature-page">
      <h2>Medicine Scanner</h2>
      <p>Capture or select medicine-strip photo.</p>
      <Link to="/medicine/result">Scan Mock Medicine</Link>
    </div>
  );
};

export const MedicineResult = () => {
  return (
    <div className="feature-page">
      <h2>Substitution Result</h2>
      <p>Alternatives and interactions will be here.</p>
      <Link to="/medicine">Back to Scanner</Link>
    </div>
  );
};

export const MedicineLayout = () => <Outlet />;
