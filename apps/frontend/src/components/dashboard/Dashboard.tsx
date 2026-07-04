import { useQuery } from '@tanstack/react-query';
import { buildStatCards, fetchDashboard, isDashboardEmpty, relativeTime } from '../../lib/dashboard';

/**
 * Studio dashboard (Phase 6 groundwork): revenue / users / conversion KPI tiles + recent activity.
 * KPIs have no source yet → they render "—" (never a fake 0); recent activity is real, read from
 * the locally saved designs. Loading / error / empty states all handled. All values flow through
 * `lib/dashboard.ts` — no hardcoded metrics here.
 */
export function Dashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => fetchDashboard(),
  });

  if (isLoading) {
    return (
      <section className="dashboard">
        <h1 className="dashboard-title">Dashboard</h1>
        <p className="muted">Loading dashboard…</p>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="dashboard">
        <h1 className="dashboard-title">Dashboard</h1>
        <p className="muted">Couldn’t load the dashboard.</p>
        <button type="button" className="tool-btn" onClick={() => refetch()}>
          Retry
        </button>
      </section>
    );
  }

  const cards = buildStatCards(data);
  const empty = isDashboardEmpty(data);

  return (
    <section className="dashboard">
      <h1 className="dashboard-title">Dashboard</h1>

      {empty ? (
        <p className="muted">No data yet — save a design to start tracking activity.</p>
      ) : (
        <>
          <div className="dashboard-grid">
            {cards.map((c) => (
              <div key={c.key} className="stat-card">
                <div className="stat-label">{c.label}</div>
                <div className="stat-value">{c.value}</div>
                <div className="stat-hint muted">{c.hint}</div>
              </div>
            ))}
          </div>

          <div className="panel dashboard-activity">
            <h2 className="panel-title">Recent activity</h2>
            {data.activity.length === 0 ? (
              <p className="muted small">No saved designs yet.</p>
            ) : (
              <ul className="activity-list">
                {data.activity.map((a) => (
                  <li key={a.id} className="activity-row">
                    <span className="activity-name">{a.name}</span>
                    <span className="activity-meta muted">{a.stitchCount.toLocaleString()} st</span>
                    <span className="activity-meta muted">{relativeTime(a.savedAt)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}
