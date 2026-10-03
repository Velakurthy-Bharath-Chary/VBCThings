import { useAuth } from '../context/auth-context';

function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar navbar-expand-lg bg-white border-bottom sticky-top">
      <div className="container-fluid px-3 px-lg-4">
        <a className="navbar-brand fw-bold" href="/">
          VBC Things
        </a>

        <div className="d-flex align-items-center gap-3">
          <span className="text-muted small d-none d-md-block">
            {user?.email}
          </span>

          <button
            type="button"
            className="btn btn-outline-dark btn-sm"
            onClick={logout}
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;

// FILE PURPOSE:
// Provides the authenticated top navigation bar with VBC Things branding,
// current-user information, and logout functionality.
