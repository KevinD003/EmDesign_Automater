import {
  CAPABILITIES,
  designAnalytics,
  formatMinutes,
  formatThreadLength,
} from '../../lib/analytics';
import { useDesignStore } from '../../store/designStore';
import { StatTile } from './OverviewPage';

/**
 * Current-design analytics, rebuilt on the dataviz method (v2 Part 35):
 * single-series charts carry --dz-series-1 and no legend; values and labels
 * wear text tokens, never the series colour; bars are thin with 2px surface
 * gaps and 4px rounded data ends anchored to the baseline; only the peak bin
 * is direct-labeled; every mark has a <title> tooltip. Thread-usage bars are
 * the documented exception: their colour IS the data (the actual thread hex),
 * with name and length in text tokens beside them.
 */
export function AnalyticsPage() {
  const design = useDesignStore((s) => s.design);
  const quality = useDesignStore((s) => s.quality);

  if (!design) {
    return (
      <section className="dz-card">
        <h2 className="dz-card-title">No design open</h2>
        <p className="dz-muted">
          Open, digitize or letter a design in the Studio — its full analysis appears here.
        </p>
        <div className="dz-actions">
          <a className="dz-btn dz-btn-primary" href="#/studio">
            Open the Studio
          </a>
        </div>
      </section>
    );
  }

  const { stream, histogram, usage } = designAnalytics(design);
  const maxBin = Math.max(1, ...histogram.map((b) => b.count));
  const peakIdx = histogram.findIndex((b) => b.count === maxBin);
  const maxUsage = Math.max(1, ...usage.map((u) => u.lengthMm));
  const sewShare = stream.sewMm + stream.travelMm > 0 ? stream.sewMm / (stream.sewMm + stream.travelMm) : 1;

  const W = 560;
  const H = 148;
  const PAD_L = 8;
  const PAD_B = 22;
  const bw = (W - PAD_L * 2) / histogram.length;

  return (
    <>
      {design.warnings?.length ? (
        <div className="dz-warnings" role="status">
          {design.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      ) : null}

      <section className="dz-tiles" aria-label="Design statistics">
        <StatTile label="Quality" value={quality ? String(quality.score) : '—'} hint={quality ? `grade ${quality.grade}` : 'run Quality in the Studio'} />
        <StatTile label="Stitches" value={stream.stitches.toLocaleString()} hint={`${design.widthMm.toFixed(0)}×${design.heightMm.toFixed(0)} mm`} />
        <StatTile label="Est. time" value={formatMinutes(stream.estMinutes)} hint="incl. trims + re-threads" />
        <StatTile label="Colours" value={String(design.colorStops.length)} hint={`${stream.colorChanges} change${stream.colorChanges === 1 ? '' : 's'}`} />
        <StatTile label="Trims" value={String(stream.trims)} hint={`${stream.jumps} jumps`} />
        <StatTile label="Travel" value={`${(stream.travelShare * 100).toFixed(1)}%`} hint={`longest jump ${stream.longestJumpMm.toFixed(1)} mm`} />
      </section>

      <div className="dz-grid2">
        <figure className="dz-card dz-chart">
          <figcaption className="dz-card-title">
            Stitch length distribution <span className="dz-muted dz-small">(mm — machine cap 12.7)</span>
          </figcaption>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Histogram of stitch lengths in half-millimetre bins">
            {histogram.map((b, i) => {
              const h = Math.round(((H - PAD_B - 20) * b.count) / maxBin);
              const x = PAD_L + i * bw;
              const y = H - PAD_B - h;
              return (
                <g key={b.from}>
                  <rect
                    className="dz-bar"
                    x={x + 1}
                    y={y}
                    width={Math.max(1, bw - 2)}
                    height={Math.max(h, b.count > 0 ? 2 : 0)}
                    rx={h > 4 ? 4 : 0}
                  >
                    <title>{`${b.from.toFixed(1)}–${b.to.toFixed(1)} mm: ${b.count.toLocaleString()} stitches`}</title>
                  </rect>
                  {i === peakIdx && b.count > 0 ? (
                    <text className="dz-bar-label" x={x + bw / 2} y={y - 5} textAnchor="middle">
                      {b.count.toLocaleString()}
                    </text>
                  ) : null}
                  {i % 4 === 0 ? (
                    <text className="dz-axis" x={x + 1} y={H - 8}>
                      {b.from.toFixed(0)}
                    </text>
                  ) : null}
                </g>
              );
            })}
            <line className="dz-baseline" x1={PAD_L} y1={H - PAD_B} x2={W - PAD_L} y2={H - PAD_B} />
          </svg>
        </figure>

        <figure className="dz-card dz-chart">
          <figcaption className="dz-card-title">
            Thread usage by colour <span className="dz-muted dz-small">(sewn path)</span>
          </figcaption>
          <div className="dz-usage">
            {usage.map((u) => (
              <div key={u.stop} className="dz-usage-row" title={`Stop ${u.stop} · ${u.name} · ${formatThreadLength(u.lengthMm)}`}>
                <span className="dz-swatch" style={{ background: u.hex }} />
                <span className="dz-usage-name">{u.name}</span>
                <span className="dz-usage-track">
                  <span className="dz-usage-fill" style={{ width: `${(u.lengthMm / maxUsage) * 100}%`, background: u.hex }} />
                </span>
                <span className="dz-usage-len">{formatThreadLength(u.lengthMm)}</span>
              </div>
            ))}
          </div>

          <figcaption className="dz-card-title dz-mt">
            Needle-down vs travel <span className="dz-muted dz-small">(path length)</span>
          </figcaption>
          <div
            className="dz-split"
            role="img"
            aria-label={`Sewing ${(sewShare * 100).toFixed(1)} percent of path length, travel ${((1 - sewShare) * 100).toFixed(1)} percent`}
            title={`Sewing ${formatThreadLength(stream.sewMm)} · travel ${formatThreadLength(stream.travelMm)}`}
          >
            <span className="dz-split-sew" style={{ width: `${sewShare * 100}%` }} />
            <span className="dz-split-travel" style={{ width: `${(1 - sewShare) * 100}%` }} />
          </div>
          <div className="dz-split-legend">
            <span>
              <span className="dz-key dz-key-sew" /> Sewing {(sewShare * 100).toFixed(1)}%
            </span>
            <span>
              <span className="dz-key dz-key-travel" /> Travel {((1 - sewShare) * 100).toFixed(1)}%
            </span>
          </div>
        </figure>
      </div>

      <details className="dz-card dz-caps">
        <summary className="dz-card-title">Capabilities vs desktop suites</summary>
        <div className="dz-table-wrap">
          <table className="dz-table">
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
                    <span className={`dz-cap dz-cap-${c.us}`}>
                      {c.us === 'yes' ? '✓' : c.us === 'partial' ? '◐' : '✗'} {c.us}
                    </span>{' '}
                    <span className="dz-muted dz-small">— {c.usNote}</span>
                  </td>
                  <td>
                    <span className={`dz-cap dz-cap-${c.competitors}`}>
                      {c.competitors === 'yes' ? '✓' : c.competitors === 'partial' ? '◐' : '✗'} {c.competitors}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="dz-muted dz-small">
          Every row traces to a measured audit in <code>docs/</code> — “yes” means generated and tested, not declared.
        </p>
      </details>
    </>
  );
}
