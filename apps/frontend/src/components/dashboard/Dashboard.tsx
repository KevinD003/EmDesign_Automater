import { useQuery } from '@tanstack/react-query';
import { buildStatCards, fetchDashboard, isDashboardEmpty, relativeTime } from '../../lib/dashboard';
import { useAuthStore } from '../../store/authStore';

/**
 * Studio dashboard: the signed-in user's real metrics — My designs / Total stitches / Colors
 * used — pulled live from their Supabase cloud account. Signed out, it falls back to designs
 * saved in this browser (colors have no local source → "—"). Recent activity is real either way.
 * Loading / error / empty states handled. All values flow through `lib/dashboard.ts`.
 */
export function Dashboard() {
  const session = useAuthStore((s) => s.session);
  const loggedIn = !!session;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard', session?.userId ?? 'local'],
    queryFn: () => fetchDashboard({ loggedIn }),
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
      <p className="muted small dashboard-source">
        {data.source === 'cloud'
          ? `☁ ${session?.email ?? 'your cloud account'}`
          : 'Local (this browser) — sign in to see your cloud designs'}
      </p>

      {empty ? (
        <p className="muted">
          {loggedIn
            ? 'No cloud designs yet — hit ☁ Save in the studio to start tracking.'
            : 'No designs saved in this browser yet — save one, or sign in for cloud stats.'}
        </p>
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
