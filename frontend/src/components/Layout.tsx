import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

type NavigationGroup = {
  label: string;
  links: {
    to: string;
    label: string;
    icon: string;
    end?: boolean;
    featured?: boolean;
  }[];
};

const groups: NavigationGroup[] = [
  {
    label: "Overview",
    links: [
      { to: "/", label: "Sync Center", icon: "space_dashboard", end: true },
      { to: "/guidance", label: "Guidance", icon: "explore", featured: true },
    ],
  },
  {
    label: "Set up",
    links: [
      { to: "/settings/aconex", label: "1. Connect ACONEX", icon: "vpn_key" },
      { to: "/settings/google-sheets", label: "2. Connect Google Sheets", icon: "table_chart" },
      { to: "/tracked", label: "3. Choose Workflows", icon: "track_changes" },
      { to: "/feedback-rules", label: "4. Define Rules", icon: "rule" },
    ],
  },
  {
    label: "Operate",
    links: [
      { to: "/schedules", label: "Scheduled Jobs", icon: "schedule" },
      { to: "/runs", label: "Run History", icon: "history" },
      { to: "/workflows", label: "Workflow Data", icon: "account_tree" },
    ],
  },
];

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <div className="layout">
      <header className="mobile-header">
        <button
          type="button"
          className="icon-button"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="material-symbols-outlined">{menuOpen ? "close" : "menu"}</span>
        </button>
        <Link to="/" className="mobile-brand">
          <span className="brand-mini">AW</span>
          <strong>ACONEX Manager</strong>
        </Link>
        <Link to="/guidance" className="icon-button" aria-label="Open guidance">
          <span className="material-symbols-outlined">help</span>
        </Link>
      </header>

      {menuOpen && (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label="Dismiss navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside className={`sidebar${menuOpen ? " is-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <span className="material-symbols-outlined">hub</span>
          </div>
          <div className="brand-text">
            <strong>ACONEX Manager</strong>
            <span>Workflow Automation</span>
          </div>
        </div>

        <nav className="nav" aria-label="Main navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-group-label">{group.label}</div>
              {group.links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `nav-link${isActive ? " active" : ""}${link.featured ? " featured" : ""}`
                  }
                >
                  <span className="material-symbols-outlined nav-icon">{link.icon}</span>
                  <span className="nav-label">{link.label}</span>
                  {link.featured && <span className="nav-new">Start here</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <Link to="/guidance" className="guidance-callout">
          <span className="material-symbols-outlined">lightbulb</span>
          <span>
            <strong>Not sure what to do?</strong>
            <small>Follow the guided setup</small>
          </span>
          <span className="material-symbols-outlined guidance-arrow">arrow_forward</span>
        </Link>
      </aside>

      <div className="main-shell">
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
