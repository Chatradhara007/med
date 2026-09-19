import { NavLink } from 'react-router-dom';

export const BottomNav = () => {
  return (
    <nav className="bottom-nav">
      <NavLink to="/">Home</NavLink>
      <NavLink to="/documents">Documents</NavLink>
      <NavLink to="/medicine">Medicine</NavLink>
      <NavLink to="/profile">Profile</NavLink>
    </nav>
  );
};
