import type { ReactNode } from 'react';

export type BadgeVariant =
  | 'confirmed'
  | 'review'
  | 'abnormal'
  | 'blocked'
  | 'critical'
  | 'processing'
  | 'info'
  | 'provenance';

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  icon?: ReactNode;
  className?: string;
}

export const Badge = ({ variant = 'info', children, icon, className = '' }: BadgeProps) => {
  return (
    <span className={`ct-badge ${variant} ${className}`}>
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      {children}
    </span>
  );
};
