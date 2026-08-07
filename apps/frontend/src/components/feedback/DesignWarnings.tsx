/**
 * The digitizer's warnings, verbatim (v2 Part 25 mechanism, extracted Part 60).
 *
 * Everything the backend puts in `Design.warnings` renders here unchanged —
 * the colour-limit message from Part 59 included. This is the ONLY warning
 * surface: the backend list is the single source, and this component adds no
 * filtering, rewording or second channel. Extracted from App.tsx so the
 * present/absent contract is unit-testable; the markup is unchanged.
 */

export function DesignWarnings({ warnings }: { warnings?: string[] | null }) {
  if (!warnings?.length) return null;
  return (
    <div className="design-warnings" role="status">
      {warnings.map((w) => (
        <div key={w}>⚠ {w}</div>
      ))}
    </div>
  );
}
