import type { CarePlanItem } from '../../../types/api';
import { CarePlanCard } from './CarePlanCard';

interface Props {
  dayIndex: number;
  items: CarePlanItem[];
  onMarkDone: (dayIndex: number, slot: string) => void;
}

export const TimelineDay = ({ dayIndex, items, onMarkDone }: Props) => {
  const label = dayIndex === 0 ? 'Day 0 (Today)' : `Day ${dayIndex}`;

  return (
    <div className="timeline-day">
      <h3>{label}</h3>
      <div className="day-items">
        {items.map((item) => (
          <CarePlanCard key={item.id} item={item} onMarkDone={onMarkDone} />
        ))}
      </div>
    </div>
  );
};
