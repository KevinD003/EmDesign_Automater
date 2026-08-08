"""Anon-key RLS probe for the identity tables (CTO A13/S3 production verification).

Applying `db/migrations/001_identity_rls.sql` is not proof — the proof is that
the PUBLIC anon key can no longer read or write `users`, `teams` or
`team_members` on the LIVE project. This script is that proof, run against a
real deployment.

    SUPABASE_URL=https://xxx.supabase.co \\
    SUPABASE_ANON_KEY=eyJ... \\
    python apps/backend/scripts/verify_rls.py

Exit 0 = every table denied. Exit 1 = something is still exposed (the message
names it). Exit 2 = could not run (missing credentials / network).

WHAT COUNTS AS DENIED, and why the read and write checks differ:

* READS — Supabase grants the `anon` role table-level SELECT by default, so an
  RLS-protected table answers 200 with an EMPTY array rather than an error: no
  policy matches an anonymous caller because `auth.uid()` is NULL. An empty
  result is therefore a PASS; any row at all is a FAIL, and a 401/403/42501 is
  also a pass (belt and braces).
* WRITES — an insert with no permissive policy is refused outright, so anything
  other than an error is a FAIL. If a write unexpectedly SUCCEEDS the script
  says so loudly and tells you to delete the row: it just wrote to production.

The probe deliberately uses raw PostgREST over httpx rather than the supabase
client, so it exercises the same public surface an attacker would.
"""

from __future__ import annotations

import os
import sys
import uuid

TABLES = ("users", "teams", "team_members")

# A row shaped well enough that a REJECTION proves policy, not a schema error.
# (A 400 "column does not exist" would be a false pass, so each payload uses
# only columns the table really has.)
INSERT_PAYLOADS = {
    "users": {"id": str(uuid.uuid4())},
    "teams": {"name": "rls-probe", "owner_user_id": str(uuid.uuid4())},
    "team_members": {"team_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())},
}


def main() -> int:
    import httpx

    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY") or ""
    if not url or not anon:
        print("SUPABASE_URL and SUPABASE_ANON_KEY must be set (anon key, NOT the "
              "service key — the service key bypasses RLS by design and would "
              "make this probe meaningless).", file=sys.stderr)
        return 2

    rest = f"{url}/rest/v1"
    headers = {"apikey": anon, "Authorization": f"Bearer {anon}",
               "Content-Type": "application/json"}
    failures: list[str] = []

    with httpx.Client(timeout=20) as client:
        for table in TABLES:
            # ── read ────────────────────────────────────────────────────────
            try:
                r = client.get(f"{rest}/{table}?select=*&limit=5", headers=headers)
            except httpx.HTTPError as exc:
                print(f"network error probing {table}: {exc}", file=sys.stderr)
                return 2
            if r.status_code in (401, 403):
                print(f"  ok   {table}: read refused ({r.status_code})")
            elif r.status_code == 200:
                rows = r.json()
                if rows:
                    failures.append(
                        f"{table}: anon key READ {len(rows)} row(s) — RLS is NOT closed"
                    )
                    print(f"  FAIL {table}: read returned {len(rows)} row(s)")
                else:
                    print(f"  ok   {table}: read returned no rows")
            else:
                # An unexpected status is not proof of denial — say so.
                failures.append(f"{table}: unexpected read status {r.status_code} "
                                f"({r.text[:120]}) — cannot certify")
                print(f"  ??   {table}: unexpected read status {r.status_code}")

            # ── write ───────────────────────────────────────────────────────
            w = client.post(f"{rest}/{table}", headers=headers,
                            json=INSERT_PAYLOADS[table])
            if w.status_code in (200, 201):
                failures.append(
                    f"{table}: anon key WROTE a row (status {w.status_code}) — RLS is "
                    f"NOT closed. DELETE THAT ROW: {INSERT_PAYLOADS[table]}"
                )
                print(f"  FAIL {table}: write succeeded")
            else:
                print(f"  ok   {table}: write refused ({w.status_code})")

    print()
    if failures:
        print("RLS VERIFICATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"RLS verified on {url}: anon key can neither read nor write "
          f"{', '.join(TABLES)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
