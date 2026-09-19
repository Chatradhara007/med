import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { AppLayout } from '../../components/layout';
import { Timeline } from '../../features/timeline';
import { DocumentsLayout, DocumentsList, DocumentDetail } from '../../features/documents';
import { MedicineLayout, MedicineScanner, MedicineResult, PreviousScans } from '../../features/medicine';
import { Profile } from '../../features/patient';
import { Auth } from '../../features/auth';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Timeline /> },
      {
        path: 'documents',
        element: <DocumentsLayout />,
        children: [
          { index: true, element: <DocumentsList /> },
          { path: ':id', element: <DocumentDetail /> },
        ],
      },
      {
        path: 'medicine',
        element: <MedicineLayout />,
        children: [
          { index: true, element: <MedicineScanner /> },
          { path: 'result', element: <MedicineResult /> },
          { path: 'history', element: <PreviousScans /> },
        ],
      },
      { path: 'profile', element: <Profile /> },
    ],
  },
  {
    path: '/auth',
    element: <Auth />,
  }
]);

export const AppRouter = () => {
  return <RouterProvider router={router} />;
};
