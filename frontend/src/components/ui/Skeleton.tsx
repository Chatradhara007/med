import type { CSSProperties } from 'react';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  style?: CSSProperties;
}

export const Skeleton = ({
  width = '100%',
  height = '18px',
  borderRadius = 'var(--ct-radius-sm)',
  className = '',
  style = {},
}: SkeletonProps) => {
  return (
    <div
      className={`skeleton-box ${className}`}
      style={{
        width,
        height,
        borderRadius,
        ...style,
      }}
    />
  );
};

export const CardSkeleton = () => (
  <div className="ct-card" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Skeleton width="40%" height="22px" />
      <Skeleton width="18%" height="22px" borderRadius="var(--ct-radius-pill)" />
    </div>
    <Skeleton width="80%" height="16px" />
    <Skeleton width="60%" height="16px" />
  </div>
);
