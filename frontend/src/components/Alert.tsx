type Props = {
  type?: "error" | "success" | "info";
  children: React.ReactNode;
};

export function Alert({ type = "info", children }: Props) {
  if (!children) return null;
  return <div className={`alert ${type === "info" ? "" : type}`.trim()}>{children}</div>;
}
