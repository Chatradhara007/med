/**
 * Renders a single interaction warning string from the backend.
 * Backend returns interactions as string[] — not structured objects.
 */
interface Props {
  message: string;
}

export const InteractionWarning = ({ message }: Props) => {
  return (
    <div className="interaction-warning high">
      <div className="warn-header">
        <span className="warn-icon">⚠</span>
        <strong>Interaction Warning</strong>
      </div>
      <p className="warn-message">{message}</p>
    </div>
  );
};
