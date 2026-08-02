import { useEffect, useState } from 'react';
import {
  fetchDashboard,
  isDashboardEmpty,
  relativeTime,
  type DashboardData,
} from '../../lib/dashboard';
import { designAnalytics, formatMinutes } from '../../lib/analytics';
import { useAuthStore } from '../../store/authStore';
import { useDesignStore } from '../../store/designStore';

/** Landing view: your library at a glance + the design open in the Studio. */
export function OverviewPage() {
  const session = useAuthStore((s) => s.session);
  const design = useDesignStore((s) => s.design);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchDashboard({ loggedIn: !!session })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [session]);

  const current = design ? designAnalytics(design) : null;

  return (
    <>
      <section className="dz-tiles" aria-label="Library statistics">
        <StatTile
          label="My designs"
          value={data ? String(data.designCount) : '—'}
          hint={data?.source === 'cloud' ? 'cloud library' : 'saved in this browser'}
        />
        <StatTile
          label="Total stitches"
          value={data?.totalStitches != null ? data.totalStitches.toLocaleString() : '—'}
          hint="across saved designs"
        />
        <StatTile
          label="Colours used"
          value={data?.totalColors != null ? String(data.totalColors) : '—'}
          hint={data?.source === 'cloud' ? 'across saved designs' : 'sign in for colour totals'}
        />
        <StatTile
          label="Est. sew time"
          value={current ? formatMinutes(current.stream.estMinutes) : '—'}
          hint={design ? `current: ${design.name}` : 'no design open'}
        />
      </section>

      <div className="dz-grid2">
        <section className="dz-card" aria-label="Current design">
          <h2 className="dz-card-title">In the Studio now</h2>
          {design && current ? (
            <>
              <div className="dz-current-name">{design.name}</div>
              <p className="dz-muted">
                {design.widthMm.toFixed(0)}×{design.heightMm.toFixed(0)} mm ·{' '}
                {current.stream.stitches.toLocaleString()} stitches · {design.colorStops.length}{' '}
                colours · {current.stream.trims} trims
              </p>
              {design.warnings?.length ? (
                <div className="dz-warnings" role="status">
                  {design.warnings.map((w) => (
                    <div key={w}>⚠ {w}</div>
                  ))}
                </div>
              ) : null}
              <div className="dz-actions">
                <a className="dz-btn dz-btn-primary" href="#/dashboard/analytics">
                  Full analytics
                </a>
                <a className="dz-btn" href="#/studio">
                  Continue editing
                </a>
              </div>
            </>
          ) : (
            <>
              <p className="dz-muted">
                Nothing open yet. Digitize an image, open a machine file, or type lettering — the
                full analysis lands here.
              </p>
              <div className="dz-actions">
                <a className="dz-btn dz-btn-primary" href="#/studio">
                  Open the Studio
                </a>
              </div>
            </>
          )}
        </section>

        <section className="dz-card" aria-label="Recent activity">
          <h2 className="dz-card-title">Recent activity</h2>
          {error ? <p className="dz-muted">Couldn’t load: {error}</p> : null}
          {data && !isDashboardEmpty(data) ? (
            <ul className="dz-activity">
              {data.activity.slice(0, 6).map((a) => (
                <li key={a.id} className="dz-activity-row">
                  <span className="dz-activity-name">{a.name}</span>
                  <span className="dz-muted">
                    {a.stitchCount.toLocaleString()} st · {relativeTime(a.savedAt)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dz-muted">
              {session
                ? 'No saved designs yet — Save one from the Studio.'
                : 'Sign in to sync your library across devices, or Save locally from the Studio.'}
            </p>
          )}
        </section>
      </div>
    </>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="dz-tile">
      <div className="dz-tile-label">{label}</div>
      <div className="dz-tile-value">{value}</div>
      {hint ? <div className="dz-tile-hint">{hint}</div> : null}
    </div>
  );
}
