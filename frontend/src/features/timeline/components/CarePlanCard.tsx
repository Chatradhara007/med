import type { CarePlanItem } from '../../../types/api';

interface CarePlanCardProps {
  item: CarePlanItem;
  onMarkDone: (dayIndex: number, slot: string) => void;
}

const SLOT_ICON: Record<string, string> = {
  morning: '🌅',
  afternoon: '☀️',
  evening: '🌆',
  night: '🌙',
};

export const CarePlanCard = ({ item, onMarkDone }: CarePlanCardProps) => {
  const icon = SLOT_ICON[item.slot] || '⏰';

  return (
    <div className={`care-plan-card ${item.done ? 'completed' : 'pending'}`}>
      <div className="card-content">
        <div className="card-slot-icon">{icon}</div>
        <div className="card-body">
          <h4>{item.action}</h4>
          {item.time_target && <p className="card-time">Target: {item.time_target}</p>}
          {item.med_ref && <p className="card-med-ref">Medicine: {item.med_ref.replace(/^MED#/, '')}</p>}
          <span className={`status-badge ${item.done ? 'completed' : 'pending'}`}>
            {item.done ? 'Done' : 'Pending'}
          </span>
        </div>
      </div>
      {!item.done && (
        <button className="btn-done" onClick={() => onMarkDone(item.day_index, item.slot)}>
          Mark Done
        </button>
      )}
      {item.done && item.completed_at && (
        <small className="completed-at">
          Completed at {new Date(item.completed_at).toLocaleTimeString()}
        </small>
      )}
    </div>
  );
};
