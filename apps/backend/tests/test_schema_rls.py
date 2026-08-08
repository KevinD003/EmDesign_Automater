"""CTO A13/S3: every table in the applied schema carries row level security.

Supabase tables without RLS are readable/writable via the public anon key.
The review found users/teams/team_members unprotected — subscription tier,
usage counters and team rosters exposed. This is a text-level lint of
db/schema.sql: a new table added without an RLS enable fails here instead of
shipping open.
"""

from __future__ import annotations

import re
from pathlib import Path


def _schema_text() -> str:
    return (Path(__file__).resolve().parents[3] / "db" / "schema.sql").read_text()


def test_every_table_has_rls_enabled():
    text = _schema_text()
    tables = set(re.findall(r"create table if not exists public\.(\w+)", text))
    rls = set(re.findall(r"alter table public\.(\w+)\s+enable row level security", text))
    assert tables, "no tables found — schema path wrong?"
    missing = tables - rls
    assert not missing, f"tables without RLS: {sorted(missing)}"


def test_identity_tables_have_policies():
    # RLS enabled with no policy = deny-all for the anon key, which is safe but
    # unusable; the three S3 tables must carry their intended policies.
    text = _schema_text()
    for needle in ('"own profile" on public.users',
                   '"see own memberships" on public.team_members',
                   '"owner manages team" on public.teams',
                   '"members see their teams" on public.teams'):
        assert needle in text, f"policy missing: {needle}"


def test_team_members_policies_never_reference_teams():
    # Recursion guard: a teams policy may subquery team_members, so any
    # team_members policy that subqueries teams back makes Postgres RLS
    # evaluation recurse infinitely. Structural, so a future edit can't
    # reintroduce it.
    text = _schema_text()
    policies = re.findall(r"create policy[^;]+on public\.team_members[^;]+;", text)
    assert policies, "no team_members policies found"
    for p in policies:
        assert "public.teams" not in p, f"recursion hazard: {p[:120]}"
