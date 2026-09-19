import type { CareTeamMember } from '../../../types/api';

interface Props {
  team?: CareTeamMember[];
}

export const CareTeamCard = ({ team }: Props) => {
  if (!team || team.length === 0) return null;

  return (
    <section className="profile-card team-card">
      <h3>Care Team</h3>
      <div className="team-list">
        {team.map((member, i) => (
          <div key={i} className="team-item">
            <div className="team-role">{member.role}</div>
            <div className="team-name">{member.name}</div>
            <div className="team-dept">{member.department}</div>
          </div>
        ))}
      </div>
    </section>
  );
};
