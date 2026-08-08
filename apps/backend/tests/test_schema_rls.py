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


# ── The applied-migration half (ops item 1) ───────────────────────────────────
# schema.sql is a create-from-scratch script; a LIVE project is updated with
# db/migrations/001_identity_rls.sql. The two must not drift, or the database
# and the repo's stated schema stop agreeing.


def _migration_text() -> str:
    return (Path(__file__).resolve().parents[3] / "db" / "migrations"
            / "001_identity_rls.sql").read_text()


def test_migration_covers_exactly_the_three_identity_tables():
    text = _migration_text()
    enabled = set(re.findall(r"alter table public\.(\w+)\s+enable row level security", text))
    assert enabled == {"users", "teams", "team_members"}, enabled


def test_migration_policies_match_schema_policies():
    # Same policy names, same tables, in both files — so applying the migration
    # yields the database schema.sql describes.
    def policies(text: str) -> set[tuple[str, str]]:
        return set(re.findall(r'create policy\s+"([^"]+)"\s+on public\.(\w+)', text))

    schema = {p for p in policies(_schema_text())
              if p[1] in {"users", "teams", "team_members"}}
    assert policies(_migration_text()) == schema


def test_migration_is_rerunnable():
    # `create policy` has no IF NOT EXISTS in Postgres, so every policy must be
    # preceded by a drop or a re-run fails halfway and leaves RLS half-applied.
    text = _migration_text()
    created = re.findall(r'create policy\s+"([^"]+)"\s+on public\.(\w+)', text)
    dropped = set(re.findall(r'drop policy if exists\s+"([^"]+)"\s+on public\.(\w+)', text))
    assert set(created) == dropped, f"missing drops for {set(created) - dropped}"
    assert "begin;" in text and "commit;" in text  # all-or-nothing


def test_migration_keeps_the_recursion_guard():
    # Same structural rule as the schema: a team_members policy that subqueries
    # teams makes Postgres RLS evaluation recurse infinitely.
    for p in re.findall(r"create policy[^;]+on public\.team_members[^;]+;", _migration_text()):
        assert "public.teams" not in p, f"recursion hazard: {p[:120]}"
