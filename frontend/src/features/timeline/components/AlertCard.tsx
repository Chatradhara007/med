import type { Alert } from '../../../types/api';

interface AlertCardProps {
  alert: Alert;
}

const SEVERITY_ICON: Record<string, string> = {
  critical: '🚨',
  high: '⚠️',
  warning: '⚠️',
  info: 'ℹ️',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'CRITICAL',
  high: 'HIGH',
  warning: 'WARNING',
  info: 'INFO',
};

export const AlertCard = ({ alert }: AlertCardProps) => {
  const icon = SEVERITY_ICON[alert.severity] || '⚠️';
  const label = SEVERITY_LABEL[alert.severity] || alert.severity.toUpperCase();

  return (
    <div className={`alert-card ${alert.severity}`}>
      <h4>{icon} {label} ALERT</h4>
      <p>{alert.message}</p>
      {alert.source && <small>Source: {alert.source}</small>}
    </div>
  );
};
