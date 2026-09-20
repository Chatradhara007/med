import type { CarePlanItem } from '../../../types/api';
import { CarePlanCard } from './CarePlanCard';

interface Props {
  dayIndex: number;
  items: CarePlanItem[];
  onMarkDone: (dayIndex: number, slot: string) => void;
}

export const TimelineDay = ({ dayIndex, items, onMarkDone }: Props) => {
  const isToday = dayIndex === 0;
  const label = isToday ? 'Today · Day 0' : `Episode Day ${dayIndex}`;

  const completedCount = items.filter((i) => i.done).length;
  const progressPercent = items.length > 0 ? Math.round((completedCount / items.length) * 100) : 0;

  return (
    <div style={{ marginBottom: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13.5px', fontWeight: 700, color: isToday ? '#60a5fa' : 'var(--ct-text-primary)' }}>
            {label}
          </span>
          {isToday && (
            <span style={{ fontSize: '10.5px', fontWeight: 600, color: '#38bdf8', backgroundColor: 'var(--ct-processing-bg)', padding: '2px 6px', borderRadius: 'var(--ct-radius-pill)' }}>
              CURRENT
            </span>
          )}
        </div>
        <span style={{ fontSize: '12px', color: 'var(--ct-text-muted)' }}>
          {completedCount} of {items.length} completed ({progressPercent}%)
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {items.map((item) => (
          <CarePlanCard key={item.id} item={item} onMarkDone={onMarkDone} />
        ))}
      </div>
    </div>
  );
};
