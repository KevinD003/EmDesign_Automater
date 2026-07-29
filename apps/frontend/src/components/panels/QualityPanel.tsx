import { useDesignStore } from '../../store/designStore';
import { findingClass, hoopFitLabel, qualityMetricRows, scoreTone } from '../../lib/quality';

/**
 * Quality panel (Phase 8): score + metrics + findings for the current design.
 * Fed from the design store — populated automatically after Digitize/Text and
 * refreshed by the toolbar's Quality button.
 */
export function QualityPanel() {
  const design = useDesignStore((s) => s.design);
  const quality = useDesignStore((s) => s.quality);

  if (!quality) {
    return (
      <section className="panel quality-panel">
        <h2 className="panel-title">Quality</h2>
        <p className="muted small">
          {design
            ? 'Hit Quality in the toolbar to score this design.'
            : 'Open or digitize a design to see its quality score.'}
        </p>
      </section>
    );
  }

  const tone = scoreTone(quality.score);
  const hoopLine = hoopFitLabel(quality.hoopFit);
  return (
    <section className="panel quality-panel">
      <h2 className="panel-title">Quality</h2>
      <div className="quality-score">
        <span className={`quality-number q-${tone}`}>{quality.score}</span>
        <span className={`quality-grade q-${tone}`}>{quality.grade}</span>
        <span className="muted small">/ 100</span>
      </div>
      <div className="quality-grid">
        {qualityMetricRows(quality).map((row) => (
          <div key={row.label} className="quality-cell">
            <span className="muted small">{row.label}</span>
            <span className="quality-value">{row.value}</span>
          </div>
        ))}
      </div>
      {hoopLine && (
        <div
          className={`small quality-hoop ${
            quality.hoopFit === false ? 'vr-issue' : quality.hoopFit ? 'vr-ok' : 'muted'
          }`}
        >
          {hoopLine}
        </div>
      )}
      {quality.findings.length > 0 ? (
        <ul className="quality-findings">
          {quality.findings.map((f, i) => (
            <li key={`${f.code}-${i}`} className={`small ${findingClass(f.severity)}`}>
              {f.message}
              {f.count > 1 ? ` (×${f.count})` : ''}
            </li>
          ))}
        </ul>
      ) : (
        <p className="vr-ok small">No findings.</p>
      )}
    </section>
  );
}
