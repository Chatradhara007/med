import type { CarePlanItem  } from '../../../types/api';
import { CarePlanCard } from './CarePlanCard';

interface Props {
  day: string;
  items: CarePlanItem[];
  onMarkDone: (id: string) => void;
}

export const TimelineDay = ({ day, items, onMarkDone }: Props) => {
  return (
    <div className="timeline-day">
      <h3>{day}</h3>
      <div className="day-items">
        {items.map(item => (
          <CarePlanCard key={item.id} item={item} onMarkDone={onMarkDone} />
        ))}
      </div>
    </div>
  );
};
