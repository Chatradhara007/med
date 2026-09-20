interface CareEpisode {
  title: string;
  startDate: string;
  status: string;
  department: string;
}

interface Props {
  episode?: CareEpisode;
}

export const CareEpisodeCard = ({ episode }: Props) => {
  if (!episode) return null;

  const formattedDate = new Date(episode.startDate).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric'
  });

  return (
    <section className="profile-card episode-card">
      <h3>Current Care Episode</h3>
      <h4>{episode.title}</h4>
      <div className="meta-grid">
        <div className="meta-item">
          <label>Started</label>
          <span>{formattedDate}</span>
        </div>
        <div className="meta-item">
          <label>Status</label>
          <span className="status-pill">{episode.status}</span>
        </div>
        <div className="meta-item">
          <label>Care Team</label>
          <span>{episode.department}</span>
        </div>
      </div>
    </section>
  );
};
