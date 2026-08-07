/**
 * Export-time trim behaviour (v2 Part 60, surfacing the Part 59 backend).
 *
 * The backend applies the profile at export: `conservative` leaves the file
 * exactly as generated (safe on any machine), `aggressive` drops trim commands
 * whose carried thread is under 10 mm — Part 48's measured point — for
 * machines with an auto-trimmer. Stitching is identical either way; only the
 * trim schedule differs (panel: 663 → 559 trims).
 *
 * One catalogue, consumed by the toolbar control and the API client alike, so
 * the labels the user reads and the values the backend receives cannot drift
 * apart. Labels are user language on purpose; the wire values are the API's.
 */

export type TrimProfile = 'conservative' | 'aggressive';

export const DEFAULT_TRIM_PROFILE: TrimProfile = 'conservative';

export interface TrimProfileOption {
  value: TrimProfile;
  label: string;
  help: string;
}

export const TRIM_PROFILE_OPTIONS: readonly TrimProfileOption[] = [
  {
    value: 'conservative',
    label: 'Trims: safe (any machine)',
    help: 'Keep every trim. The safest choice when you don’t know which machine will sew the file.',
  },
  {
    value: 'aggressive',
    label: 'Trims: fewer (auto-trim machines)',
    help:
      'For machines with an auto-trimmer: short connecting threads (under 10 mm) are carried instead of ' +
      'trimmed, saving machine time. Stitching is identical — only the trim commands change.',
  },
] as const;

/**
 * Query string for the export endpoints.
 *
 * The default profile is deliberately OMITTED from the URL: the backend
 * defaults to `conservative`, so an untouched control produces a request
 * byte-identical to what the app sent before the control existed — not merely
 * an equivalent one.
 */
export function exportQuery(format: string, trimProfile: TrimProfile = DEFAULT_TRIM_PROFILE): string {
  const params = new URLSearchParams({ format });
  if (trimProfile !== DEFAULT_TRIM_PROFILE) {
    params.set('trim_profile', trimProfile);
  }
  return params.toString();
}
