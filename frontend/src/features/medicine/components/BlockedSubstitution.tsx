interface Props {
  reason: string;
}

export const BlockedSubstitution = ({ reason }: Props) => {
  return (
    <div className="blocked-substitution">
      <div className="blocked-header">
        <span className="blocked-icon">🛑</span>
        <h3>Substitution Unavailable</h3>
      </div>
      <p className="blocked-desc">This medicine cannot be substituted through the current CareThread workflow.</p>
      <div className="blocked-reason">
        <strong>Reason:</strong> {reason}
      </div>
      <p className="blocked-advisory">Please consult your pharmacist or clinician.</p>
    </div>
  );
};
