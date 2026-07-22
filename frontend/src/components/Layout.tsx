import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/settings/aconex", label: "ACONEX 设置" },
  { to: "/settings/google-sheets", label: "Google Sheets" },
  { to: "/tracked", label: "Workflow 追踪" },
  { to: "/feedback-rules", label: "Step / 反馈规则" },
  { to: "/schedules", label: "定时任务" },
  { to: "/runs", label: "运行历史" },
  { to: "/workflows", label: "Workflow 数据" },
];

export function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          ACONEX Manager
          <span>Workflow Automation</span>
        </div>
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            {l.label}
          </NavLink>
        ))}
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
