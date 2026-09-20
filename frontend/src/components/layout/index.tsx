import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { BottomNav } from './BottomNav';
import { getRecord } from '../../api/record';

export const AppLayout = () => {
  const [patientName, setPatientName] = useState<string | undefined>();

  useEffect(() => {
    let mounted = true;
    getRecord()
      .then((record) => {
        if (mounted && record?.patient?.name) {
          setPatientName(record.patient.name);
        }
      })
      .catch(() => {
        // Silently fall back to default patient label
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <Sidebar patientName={patientName} />
      <div className="app-main">
        <Header />
        <main className="workspace-content">
          <Outlet />
        </main>
      </div>
      <BottomNav />
    </div>
  );
};
