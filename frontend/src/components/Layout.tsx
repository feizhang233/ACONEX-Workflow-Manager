import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/settings/aconex", label: "ACONEX Settings", icon: "vpn_key" },
  { to: "/settings/google-sheets", label: "Google Sheets", icon: "table_chart" },
  { to: "/tracked", label: "Tracked Workflows", icon: "track_changes" },
  { to: "/feedback-rules", label: "Step / Feedback Rules", icon: "rule" },
  { to: "/schedules", label: "Scheduled Jobs", icon: "schedule" },
  { to: "/runs", label: "Run History", icon: "history" },
  { to: "/workflows", label: "Workflow Data", icon: "account_tree" },
];

export function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
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
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span className="material-symbols-outlined nav-icon">{l.icon}</span>
              <span className="nav-label">{l.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="material-symbols-outlined">cloud_done</span>
          <span>Material Design UI</span>
        </div>
      </aside>

      <div className="main-shell">
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
