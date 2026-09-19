import { Outlet } from 'react-router-dom';

export { DocumentsPage as DocumentsList } from './pages/DocumentsPage';
export { DocumentDetailPage as DocumentDetail } from './pages/DocumentDetailPage';

export const DocumentsLayout = () => <Outlet />;
