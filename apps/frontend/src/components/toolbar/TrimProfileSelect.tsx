/**
 * Trim behaviour control for export (v2 Part 60).
 *
 * A sibling of the format select, because the toolbar's format select IS the
 * export UI in this app — there is no export dialog to put it in. The option
 * labels and helper text come from one catalogue shared with the API client
 * (`lib/exportOptions`), so what the user reads and what the backend receives
 * cannot drift apart. The default is `conservative`; leaving this control
 * untouched sends a request byte-identical to what the app sent before the
 * control existed.
 */
import { TRIM_PROFILE_OPTIONS, type TrimProfile } from '../../lib/exportOptions';

export interface TrimProfileSelectProps {
  value: TrimProfile;
  onChange: (profile: TrimProfile) => void;
  disabled?: boolean;
}

export function TrimProfileSelect({ value, onChange, disabled }: TrimProfileSelectProps) {
  const current = TRIM_PROFILE_OPTIONS.find((o) => o.value === value) ?? TRIM_PROFILE_OPTIONS[0];
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as TrimProfile)}
      disabled={disabled}
      aria-label="Trim behaviour on export"
      title={current.help}
      className="format-select"
    >
      {TRIM_PROFILE_OPTIONS.map((o) => (
        <option key={o.value} value={o.value} title={o.help}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
