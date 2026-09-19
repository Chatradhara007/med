import type { Alert  } from '../../../types/api';

interface AlertCardProps {
  alert: Alert;
}

export const AlertCard = ({ alert }: AlertCardProps) => {
  return (
    <div className={`alert-card ${alert.severity}`}>
      <h4>🚨 {alert.severity.toUpperCase()} ALERT</h4>
      <p>{alert.message}</p>
      <small>Source: {alert.source}</small>
    </div>
  );
};
