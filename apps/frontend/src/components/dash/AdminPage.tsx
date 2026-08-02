import { useCallback, useEffect, useState } from 'react';
import { api, type AdminStats, type AdminUser } from '../../api/client';
import { useAccount } from './useAccount';
import { StatTile } from './OverviewPage';

/** Operator tools: user list with plan/role assignment + platform counters. */
export function AdminPage() {
  const { account, loading } = useAccount();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    Promise.all([api.adminUsers(), api.adminStats()])
      .then(([u, s]) => {
        setUsers(u);
        setStats(s);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    if (account?.role === 'admin') load();
  }, [account, load]);

  if (loading) return <p className="dz-muted">Checking access…</p>;
  if (account?.role !== 'admin') {
    return (
      <section className="dz-card">
        <h2 className="dz-card-title">Admin access required</h2>
        <p className="dz-muted">
          This area is for the workspace operator. The first profile created on a fresh install is
          the admin; admins can promote others from here.
        </p>
      </section>
    );
  }

  const change = async (u: AdminUser, kind: 'plan' | 'role', value: string) => {
    setErr(null);
    try {
      const updated =
        kind === 'plan' ? await api.adminSetPlan(u.userId, value) : await api.adminSetRole(u.userId, value);
      setUsers((prev) => prev?.map((x) => (x.userId === updated.userId ? updated : x)) ?? null);
      api.adminStats().then(setStats).catch(() => undefined); // keep the counters live
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      load(); // resync after a refused change (e.g. demoting the only admin)
    }
  };

  return (
    <>
      {stats ? (
        <section className="dz-tiles" aria-label="Platform statistics">
          <StatTile label="Users" value={String(stats.users)} hint={`${stats.admins} admin${stats.admins === 1 ? '' : 's'}`} />
          <StatTile label="Free" value={String(stats.byPlan.free ?? 0)} />
          <StatTile label="Pro" value={String(stats.byPlan.pro ?? 0)} />
          <StatTile label="Studio" value={String(stats.byPlan.studio ?? 0)} />
          <StatTile
            label="Plan gates"
            value={stats.enforcing ? 'ENFORCED' : 'OPEN'}
            hint={stats.enforcing ? 'STITCHIQ_ENFORCE_PLANS=1' : 'set STITCHIQ_ENFORCE_PLANS=1 to enforce'}
          />
        </section>
      ) : null}

      {err ? <p className="dz-err" role="alert">{err}</p> : null}

      <section className="dz-card" aria-label="User management">
        <h2 className="dz-card-title">Users</h2>
        <div className="dz-table-wrap">
          <table className="dz-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Email</th>
                <th>Created</th>
                <th>Plan</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((u) => (
                <tr key={u.userId}>
                  <td>{u.username}</td>
                  <td>{u.email ?? <span className="dz-muted">—</span>}</td>
                  <td className="dz-muted">{new Date(u.createdAt).toLocaleDateString()}</td>
                  <td>
                    <select
                      value={u.plan}
                      onChange={(e) => change(u, 'plan', e.target.value)}
                      aria-label={`Plan for ${u.username}`}
                    >
                      <option value="free">free</option>
                      <option value="pro">pro</option>
                      <option value="studio">studio</option>
                    </select>
                  </td>
                  <td>
                    <select
                      value={u.role}
                      onChange={(e) => change(u, 'role', e.target.value)}
                      aria-label={`Role for ${u.username}`}
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {stats ? (
        <section className="dz-card" aria-label="Feature matrix">
          <h2 className="dz-card-title">Premium feature matrix</h2>
          <div className="dz-table-wrap">
            <table className="dz-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Minimum plan</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.features).map(([f, p]) => (
                  <tr key={f}>
                    <td>{f.replace(/_/g, ' ')}</td>
                    <td>
                      <span className={`dz-plan dz-plan-${p}`}>{p.toUpperCase()}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </>
  );
}
