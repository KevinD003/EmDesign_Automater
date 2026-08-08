-- STITCHIQ — PostgreSQL / Supabase schema (spec §8).
-- CAPTURED, NOT APPLIED. Run against your own Supabase project when wiring persistence.
-- Mirrors the Pydantic/TS data model (see docs/DATA-MODEL.md).

-- Enable extensions (Supabase has these available)
create extension if not exists "uuid-ossp";

-- 1. users — extends Supabase auth.users
create table if not exists public.users (
  id                uuid primary key references auth.users (id) on delete cascade,
  subscription_tier text not null default 'free',
  designs_this_month int  not null default 0,
  machine_brand     text,
  created_at        timestamptz not null default now()
);

-- 2. designs
create table if not exists public.designs (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid not null references public.users (id) on delete cascade,
  name          text not null,
  stitch_count  int  not null default 0,
  colors        int  not null default 0,
  width_mm      numeric(8,2) not null default 0,
  height_mm     numeric(8,2) not null default 0,
  fabric_type   text,
  version       int  not null default 1,
  master_file_url text,
  trueview_url  text,
  status        text not null default 'draft',
  created_at    timestamptz not null default now()
);
create index if not exists idx_designs_user on public.designs (user_id);

-- 3. design_objects (stitching sequence)
create table if not exists public.design_objects (
  id               uuid primary key default uuid_generate_v4(),
  design_id        uuid not null references public.designs (id) on delete cascade,
  sequence_order   int  not null,
  object_name      text,
  stitch_type      text not null,
  color_stop       int  not null,
  density          numeric(6,2),
  stitch_angle     numeric(6,2),
  underlay_type    text,
  pull_compensation numeric(5,2),
  entry_point      jsonb,
  exit_point       jsonb,
  connect_method   text,
  stitch_count     int not null default 0
);
create index if not exists idx_objects_design on public.design_objects (design_id, sequence_order);

-- 4. color_stops
create table if not exists public.color_stops (
  id            uuid primary key default uuid_generate_v4(),
  design_id     uuid not null references public.designs (id) on delete cascade,
  stop_number   int  not null,
  thread_brand  text,
  catalog_number text,
  thread_name   text,
  hex_color     text,
  stitch_count  int not null default 0
);
create index if not exists idx_colorstops_design on public.color_stops (design_id, stop_number);

-- 5. thread_database
create table if not exists public.thread_database (
  id            uuid primary key default uuid_generate_v4(),
  brand         text not null,
  product_line  text,
  catalog_number text not null,
  color_name    text,
  hex_color     text not null,
  lab_l         numeric(6,2),
  lab_a         numeric(6,2),
  lab_b         numeric(6,2),
  weight        int,
  fiber_type    text,
  discontinued  boolean not null default false
);
create index if not exists idx_thread_hex   on public.thread_database (hex_color);
create index if not exists idx_thread_brand on public.thread_database (brand);

-- 6. exports
create table if not exists public.exports (
  id            uuid primary key default uuid_generate_v4(),
  design_id     uuid not null references public.designs (id) on delete cascade,
  format        text not null,
  file_url      text,
  generated_at  timestamptz not null default now(),
  machine_brand text
);

-- 7. worksheets
create table if not exists public.worksheets (
  id           uuid primary key default uuid_generate_v4(),
  design_id    uuid not null references public.designs (id) on delete cascade,
  pdf_url      text,
  generated_at timestamptz not null default now(),
  approved_by  uuid references public.users (id),
  approved_at  timestamptz
);

-- 8. design_versions
create table if not exists public.design_versions (
  id             uuid primary key default uuid_generate_v4(),
  design_id      uuid not null references public.designs (id) on delete cascade,
  version_number int  not null,
  snapshot_json  jsonb not null,
  created_at     timestamptz not null default now(),
  change_summary text
);

-- 9. teams
create table if not exists public.teams (
  id                uuid primary key default uuid_generate_v4(),
  name              text not null,
  owner_user_id     uuid not null references public.users (id) on delete cascade,
  subscription_tier text not null default 'free'
);

-- 10. team_members
create table if not exists public.team_members (
  team_id uuid not null references public.teams (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  role    text not null default 'member',
  primary key (team_id, user_id)
);

-- ─── Row Level Security (stubs — review before enabling) ───────────────────
-- TODO: tighten policies (team sharing, public templates) before production.
alter table public.designs        enable row level security;
alter table public.design_objects enable row level security;
alter table public.color_stops    enable row level security;
alter table public.exports        enable row level security;
alter table public.worksheets     enable row level security;
alter table public.design_versions enable row level security;

-- Owner-only access to own designs (example policy).
create policy "own designs" on public.designs
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- thread_database is shared read-only reference data.
alter table public.thread_database enable row level security;
create policy "threads readable" on public.thread_database for select using (true);

-- ─── Identity & membership RLS (CTO A13/S3) ─────────────────────────────────
-- Without RLS these three tables were readable AND writable via the public
-- anon key: subscription_tier, usage counters, team rosters — all exposed.
-- Policies are written recursion-safe: team_members policies never reference
-- teams (a teams policy may subquery team_members, and if team_members
-- subqueried teams back, Postgres RLS evaluation recurses infinitely — the
-- classic Supabase membership-table pitfall). Membership WRITES are
-- server-side only (the service key bypasses RLS by design), so no
-- insert/update policy is granted to clients at all.

alter table public.users enable row level security;
create policy "own profile" on public.users
  for all using (auth.uid() = id) with check (auth.uid() = id);

alter table public.team_members enable row level security;
create policy "see own memberships" on public.team_members
  for select using (user_id = auth.uid());

alter table public.teams enable row level security;
create policy "owner manages team" on public.teams
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
create policy "members see their teams" on public.teams
  for select using (
    exists (
      select 1 from public.team_members tm
      where tm.team_id = id and tm.user_id = auth.uid()
    )
  );
