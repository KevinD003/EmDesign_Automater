/** Bottom stitch player — animate the stitch sequence (spec §3). Stub. */
export function StitchPlayer() {
  // TODO: scrub through Design.stitches, reveal stitches up to the cursor, play/pause/speed.
  return (
    <footer className="stitch-player">
      <button type="button" disabled title="Stub">
        ▶ Play
      </button>
      <input type="range" min={0} max={100} defaultValue={0} disabled aria-label="Stitch progress" />
      <span className="muted">Stitch player — stub</span>
    </footer>
  );
}
