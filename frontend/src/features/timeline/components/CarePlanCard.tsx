import type { CarePlanItem  } from '../../../types/api';

interface CarePlanCardProps {
  item: CarePlanItem;
  onMarkDone: (id: string) => void;
}

export const CarePlanCard = ({ item, onMarkDone }: CarePlanCardProps) => {
  return (
    <div className={`care-plan-card ${item.status}`}>
      <div className="card-content">
        <h4>{item.title}</h4>
        <p>{item.description}</p>
        <span className="status-badge">{item.status}</span>
      </div>
      {item.status === 'pending' && (
        <button className="btn-done" onClick={() => onMarkDone(item.id)}>Mark Done</button>
      )}
    </div>
  );
};
