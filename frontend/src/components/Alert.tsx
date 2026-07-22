type Props = {
  type?: "error" | "success" | "info";
  children: React.ReactNode;
};

const icons: Record<string, string> = {
  error: "error",
  success: "check_circle",
  info: "info",
};

export function Alert({ type = "info", children }: Props) {
  if (!children) return null;
  return (
    <div className={`md-alert md-alert-${type}`} role="alert">
      <span className="material-symbols-outlined md-alert-icon">{icons[type] || "info"}</span>
      <div className="md-alert-body">{children}</div>
    </div>
  );
}
