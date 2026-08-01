import { useDesignStore } from '../../store/designStore';
import {
  CAPABILITIES,
  designAnalytics,
  formatMinutes,
  formatThreadLength,
} from '../../lib/analytics';

/**
 * Current-design analytics (v2 Part 26) — the dashboard's live section.
 *
 * Chart discipline (dataviz method): a single series carries the chart colour
 * token and no legend; values/labels wear text tokens, never the series
 * colour; bars are thin with a 2px surface gap and rounded data ends anchored
 * to the baseline; only the peak bin is direct-labeled; every mark carries a
 * hover tooltip via <title>. Thread-usage bars are the one exception to the
 * palette: their colour IS the data (the actual thread hex), with the name and
 * length in text tokens beside them.
 */
export function DesignAnalytics() {
  const design = useDesignStore((s) => s.design);
  const quality = useDesignStore((s) => s.quality);

  if (!design) {
    return (
      <div className="panel da-empty">
        <h2 className="panel-title">Current design</h2>
        <p className="muted small">
          Open, digitize or letter a design in the Studio — its full analysis appears here.
        </p>
      </div>
    );
  }

  const { stream, histogram, usage } = designAnalytics(design);
  const maxBin = Math.max(1, ...histogram.map((b) => b.count));
  const peakIdx = histogram.findIndex((b) => b.count === maxBin);
  const maxUsage = Math.max(1, ...usage.map((u) => u.lengthMm));

  const tiles = [
    { label: 'Quality', value: quality ? `${quality.score}` : '—', hint: quality ? `grade ${quality.grade}` : 'run Quality in the Studio' },
    { label: 'Stitches', value: stream.stitches.toLocaleString(), hint: `${design.widthMm.toFixed(0)}×${design.heightMm.toFixed(0)} mm` },
    { label: 'Est. time', value: formatMinutes(stream.estMinutes), hint: 'incl. trims + re-threads' },
    { label: 'Colours', value: String(design.colorStops.length), hint: `${stream.colorChanges} change${stream.colorChanges === 1 ? '' : 's'}` },
    { label: 'Trims', value: String(stream.trims), hint: `${stream.jumps} jumps` },
    { label: 'Travel', value: `${(stream.travelShare * 100).toFixed(1)}%`, hint: `longest jump ${stream.longestJumpMm.toFixed(1)} mm` },
  ];

  // Histogram geometry: fixed viewBox, bars with a 2px gap, 4px-radius data
  // ends anchored to the baseline (clip so the rounding never lifts the base).
  const W = 560;
  const H = 132;
  const PAD_L = 8;
  const PAD_B = 22;
  const bw = (W - PAD_L * 2) / histogram.length;

  return (
    <div className="panel da-panel">
      <h2 className="panel-title">Current design — {design.name}</h2>

      {design.warnings?.length ? (
        <div className="design-warnings da-warnings" role="status">
          {design.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      ) : null}

      <div className="da-tiles">
        {tiles.map((t) => (
          <div key={t.label} className="stat-card">
            <div className="stat-label">{t.label}</div>
            <div className="stat-value">{t.value}</div>
            <div className="stat-hint muted">{t.hint}</div>
          </div>
        ))}
      </div>

      <div className="da-charts">
        <figure className="da-chart">
          <figcaption className="da-chart-title">
            Stitch length distribution <span className="muted small">(mm — machine cap 12.7)</span>
          </figcaption>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Histogram of stitch lengths in half-millimetre bins">
            {histogram.map((b, i) => {
              const h = Math.round(((H - PAD_B - 18) * b.count) / maxBin);
              const x = PAD_L + i * bw;
              const y = H - PAD_B - h;
              return (
                <g key={b.from}>
                  <rect
                    className="da-bar"
                    x={x + 1}
                    y={y}
                    width={Math.max(1, bw - 2)}
                    height={Math.max(h, b.count > 0 ? 2 : 0)}
                    rx={h > 4 ? 4 : 0}
                  >
                    <title>{`${b.from.toFixed(1)}–${b.to.toFixed(1)} mm: ${b.count.toLocaleString()} stitches`}</title>
                  </rect>
                  {i === peakIdx && b.count > 0 ? (
                    <text className="da-bar-label" x={x + bw / 2} y={y - 4} textAnchor="middle">
                      {b.count.toLocaleString()}
                    </text>
                  ) : null}
                  {i % 4 === 0 ? (
                    <text className="da-axis" x={x + 1} y={H - 8}>
                      {b.from.toFixed(0)}
                    </text>
                  ) : null}
                </g>
              );
            })}
            <line className="da-baseline" x1={PAD_L} y1={H - PAD_B} x2={W - PAD_L} y2={H - PAD_B} />
          </svg>
        </figure>

        <figure className="da-chart">
          <figcaption className="da-chart-title">
            Thread usage by colour <span className="muted small">(sewn path)</span>
          </figcaption>
          <div className="da-usage">
            {usage.map((u) => (
              <div key={u.stop} className="da-usage-row" title={`Stop ${u.stop} · ${u.name} · ${formatThreadLength(u.lengthMm)}`}>
                <span className="da-swatch" style={{ background: u.hex }} />
                <span className="da-usage-name">{u.name}</span>
                <span className="da-usage-track">
                  <span className="da-usage-fill" style={{ width: `${(u.lengthMm / maxUsage) * 100}%`, background: u.hex }} />
                </span>
                <span className="da-usage-len">{formatThreadLength(u.lengthMm)}</span>
              </div>
            ))}
          </div>
        </figure>
      </div>

      <details className="da-caps">
        <summary className="da-chart-title">Capabilities vs desktop suites</summary>
        <table className="da-caps-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th>STITCHIQ</th>
              <th>Wilcom / Hatch / Embird</th>
            </tr>
          </thead>
          <tbody>
            {CAPABILITIES.map((c) => (
              <tr key={c.feature}>
                <td>{c.feature}</td>
                <td>
                  <span className={`da-cap da-cap-${c.us}`}>
                    {c.us === 'yes' ? '✓' : c.us === 'partial' ? '◐' : '✗'} {c.us}
                  </span>
                  <span className="muted small"> — {c.usNote}</span>
                </td>
                <td>
                  <span className={`da-cap da-cap-${c.competitors}`}>
                    {c.competitors === 'yes' ? '✓' : c.competitors === 'partial' ? '◐' : '✗'} {c.competitors}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small">
          Every row traces to a measured audit in <code>docs/</code> — “yes” means generated and tested, not declared.
        </p>
      </details>
    </div>
  );
}
