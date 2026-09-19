import { Outlet } from 'react-router-dom';

export { MedicineScannerPage as MedicineScanner } from './pages/MedicineScannerPage';
export { SubstitutionResultPage as MedicineResult } from './pages/SubstitutionResultPage';
export { PreviousScansPage as PreviousScans } from './pages/PreviousScansPage';

export const MedicineLayout = () => <Outlet />;
