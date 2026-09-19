interface Props {
  allergies?: string[];
}

export const AllergyCard = ({ allergies }: Props) => {
  return (
    <section className="profile-card allergy-card">
      <h3>Allergies</h3>
      {allergies && allergies.length > 0 ? (
        <ul className="allergy-list">
          {allergies.map((allergy, i) => (
            <li key={i} className="allergy-item">
              <span className="allergy-icon">⚠</span>
              {allergy}
            </li>
          ))}
        </ul>
      ) : (
        <p className="no-data">No recorded allergies</p>
      )}
    </section>
  );
};
