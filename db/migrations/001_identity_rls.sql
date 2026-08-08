-- 001 — Row Level Security for the identity & membership tables (CTO A13/S3).
--
-- WHY A MIGRATION AND NOT schema.sql: schema.sql is a create-from-scratch
-- script. Running it against a live project is not the right instrument — this
-- file carries ONLY the RLS delta, is idempotent, and is safe to paste into the
-- Supabase SQL editor on a database that already holds data.
--
-- WHAT IT CLOSES: without RLS these three tables are readable AND writable via
-- the public anon key — subscription_tier, usage counters and team rosters all
-- exposed. RLS on the other tables was already enabled in schema.sql.
--
-- RECURSION SAFETY: the `teams` policies subquery `team_members`, so no
-- `team_members` policy may subquery `teams` back — Postgres RLS evaluation
-- would recurse infinitely (the classic Supabase membership-table pitfall).
-- tests/test_schema_rls.py enforces that structurally.
--
-- WRITES: membership rows are written server-side with the service key, which
-- bypasses RLS by design. Clients therefore get NO insert/update policy at all.
--
-- APPLY:  psql "$SUPABASE_DB_URL" -f db/migrations/001_identity_rls.sql
--     or  paste into Supabase Studio → SQL Editor → Run
-- VERIFY: python apps/backend/scripts/verify_rls.py   (anon-key probe)

begin;

-- ── public.users — a profile is visible only to its owner ───────────────────
alter table public.users enable row level security;
drop policy if exists "own profile" on public.users;
create policy "own profile" on public.users
  for all using (auth.uid() = id) with check (auth.uid() = id);

-- ── public.team_members — you may see the memberships that are yours ────────
-- NOTE: must not reference public.teams (see RECURSION SAFETY above).
alter table public.team_members enable row level security;
drop policy if exists "see own memberships" on public.team_members;
create policy "see own memberships" on public.team_members
  for select using (user_id = auth.uid());

-- ── public.teams — owner manages; members may read ──────────────────────────
alter table public.teams enable row level security;
drop policy if exists "owner manages team" on public.teams;
create policy "owner manages team" on public.teams
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
drop policy if exists "members see their teams" on public.teams;
create policy "members see their teams" on public.teams
  for select using (
    exists (
      select 1 from public.team_members tm
      where tm.team_id = id and tm.user_id = auth.uid()
    )
  );

commit;

-- Post-apply sanity, in the SQL editor (expect rowsecurity = true for all three):
--   select relname, relrowsecurity from pg_class
--    where relname in ('users','teams','team_members');
--   select tablename, policyname from pg_policies
--    where tablename in ('users','teams','team_members') order by 1,2;
