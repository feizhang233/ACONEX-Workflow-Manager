type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  id?: string;
};

/** Material Design style sliding switch */
export function Switch({ checked, onChange, label, disabled, id }: Props) {
  const switchId = id || (label ? `switch-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);

  return (
    <label className={`md-switch-row${disabled ? " is-disabled" : ""}`} htmlFor={switchId}>
      <span className="md-switch">
        <input
          id={switchId}
          type="checkbox"
          role="switch"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="md-switch-track" aria-hidden="true">
          <span className="md-switch-thumb" />
        </span>
      </span>
      {label ? <span className="md-switch-label">{label}</span> : null}
    </label>
  );
}
