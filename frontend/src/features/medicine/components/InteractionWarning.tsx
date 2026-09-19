import type { InteractionWarning as IWarn } from '../../../types/api';

interface Props {
  interaction: IWarn;
}

export const InteractionWarning = ({ interaction }: Props) => {
  return (
    <div className={`interaction-warning ${interaction.severity}`}>
      <div className="warn-header">
        <span className="warn-icon">⚠</span>
        <strong>Interaction Warning</strong>
      </div>
      <p className="warn-message">{interaction.message}</p>
      <div className="warn-details">
        <span className="warn-pill">Active: {interaction.activeMedication}</span>
        <span className="warn-pill">New: {interaction.newMedication}</span>
      </div>
    </div>
  );
};
