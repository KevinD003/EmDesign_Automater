# 🧵 STITCHIQ — CTO Review & Competitive Battle Plan

**Date:** 2026-08-07 · **Reviewed at:** commit `6d29918` (branch `claude/code-review-competitive-o2qw0o`)
**Method:** first-hand code review of the full engine/security/frontend core + a multi-agent fleet
(master-digitizer domain assessment with *empirical reproductions*, web-researched competitive analysis
with cited 2025-26 pricing, VP-Eng ship-readiness audit) + ground-truth test runs on a fresh clone.
**Audience:** the founder and every build session (human or Claude) working on this repo. **Read this
before writing code.** Work top-down through §8; do not cherry-pick fun items below blockers.

---

## 1. Executive summary — the verdict

**What you have** is genuinely rare: a working, tested, browser-based embroidery studio whose
auto-digitized designs remain **editable objects** (contours + parameters + server rebuild) — the
Wilcom "objects, not stitches" paradigm, in a browser, at hobby-tier cost. None of the AI
digitizing web services (StitchFast, Stitch AI, EmbroidAI) offer editability; none of the browser
editors (Embrowser, Ember) ship your production pipeline (package ZIP, worksheets, color cards,
validation, path optimizer). The architecture (mirrored TS⇄Pydantic model, contour-backed rebuild)
is the right chassis to compete from. That is the good news, and it is real.

**What you don't have yet** is output a professional would run. The stitch *generation* engine
fails production standards in ways every commercial embroiderer checks first — **no lock stitches
(designs unravel), untrimmed jumps across letter counters (whisker-covered garments), no-spine
satin (bridges concave shapes), tatami-blob lettering that is illegible at standard left-chest
sizes** — and the platform cannot yet take money or survive contact with the public internet
(no deploy, fail-open auth, unauthenticated CPU-heavy endpoints, no billing, no rate limits).

**The verdict:** the distance to competitive is measured in *focused weeks, not years* — because the
gaps are mostly classical geometry, data, and ops work that the existing architecture was explicitly
designed to absorb. No GPU, no neural nets, no schema change needed for any blocker fix. The plan in
§8 sequences it: **make it true → make it sellable → make it win.**

---

## 2. Ground truth — what actually runs (verified in this session, fresh clone)

| Check | Claimed (STATUS/README) | Actual |
|---|---|---|
| Frontend tests | vitest 57/57 | ✅ **57/57 pass** |
| Typecheck | clean | ✅ clean |
| Backend tests | pytest 81/81 | ❌ **collection fails on a fresh clone** — `pyembroidery` was missing from `requirements.txt`/`-dev.txt` (only in `-features.txt`). After installing it: **80/81** |
| The 1 failing test | — | `test_unsupported_glyphs_rejected`: on Linux the fallback font renders emoji as "tofu" boxes that digitize into **garbage stitches** instead of raising. Lettering output is **font-environment-dependent** (dev Mac ≠ prod Linux) |
| CI | "written, unverified" | ❌ **would fail on first push** — installs only core+dev requirements (same missing dep). Fixed in this branch: `pyembroidery` added to `requirements-dev.txt` |
| Docs | single source of truth | Drift: README says 63/47 tests & references "no remote"; STATUS says branch `main`, local Mac path; actual is 81/57 on a GitHub remote |

Lesson for all future sessions: **"tests pass on my machine" ≠ reproducible.** CI must be green on
GitHub before any further "verified" claims go into STATUS.md.

---

## 3. What is genuinely strong — protect these

1. **Editable-objects architecture.** `DesignObject.contour` + holes + params + `rebuild_design`
   is the moat. Every fix below lands inside it without a schema change. The enums already
   anticipate the pro feature set (`DOUBLE_ZIGZAG`/`PARALLEL`/`CONTOUR` underlay, `TRAVEL_RUN`).
2. **Machine-file mechanics are valid.** pyembroidery's encoder splits moves to ≤12.1mm (measured
   11.9mm max after DST round-trip), emits standard Tajima trim sequences, correct color-change/END
   records. Exported files load and run.
3. **Production pipeline breadth**: package ZIP (machine file + master + worksheet PDF with
   per-color thread length + color card + preview), 45+ formats, convert, blocking hoop-fit
   validation. Ahead of every web-tier competitor.
4. **TrueView-style 3D preview + stitch player** — visual parity with a feature Wilcom brands and
   Ricoma charges $2,499 + subscription for.
5. **Engineering hygiene**: 138 tests, honest STATUS discipline, regression tests per fix,
   adversarial-review hardening already applied once (commit `24c9aef`).
6. **Web-native + cloud auth + per-user isolation** vs. an incumbent field that is Windows-only
   desktop (Wilcom, Hatch, PE-Design, Embird) or Mac-only (Embrilliance).

---

## 4. Critical defects (correctness) — worst first

Confirmed by direct code reading and/or empirical reproduction this session. File refs at review commit.

| # | Severity | Defect | Evidence |
|---|---|---|---|
| C1 | **Blocker** | **No tie-in/tie-off lock stitches anywhere.** Every object starts/ends unsecured; machines trim at every color change and the digitizer emits TRIM before every object → every element unravels at first wash / pulls out mid-run. | Zero lock logic in `apps/backend/app`; first moves after entry jump go straight into 2mm underlay. pyembroidery supports `tie_on`/`tie_off` contingencies but `embroidery_io.write_embroidery` passes no settings |
| C2 | **Blocker** | **Jumps/stitches cross holes and counters.** Row gaps <3mm are sewn straight across (counters stitched shut); wider gaps become raw JUMPs that are never trimmed → whiskers across every 'o','e','a'. | Empirical: digitized letter-'o' ring → **30 untrimmed jump segments crossing the open counter, 0 trims** (`digitizer.py:268-298`, `CONNECT_MM`) |
| C3 | **Blocker** | **Appliqué never emits a STOP.** Placement outline → tackdown → satin border run as one continuous sequence; the machine never pauses for the operator to place appliqué fabric. Appliqué is unusable in production. | `rebuild_design` APPLIQUE branch (`digitizer.py:618-627`) emits no `STOP` record; nothing in the codebase ever emits `STOP` |
| C4 | **High** | **Editing satin `stitch_angle` is a silent no-op.** Rebuild recomputes `minAreaRect` and ignores the edited value; UI offers the edit. | Verified: identical output at 0° vs 77° (`digitizer.py:629`) |
| C5 | **High** | **Underlay menu is mostly fake.** `DOUBLE_ZIGZAG`/`PARALLEL`/`CONTOUR` are selectable in PropertiesPanel but any non-NONE silently collapses to edge-walk (fills) / center-walk (satin). | `digitizer.py:631,639` |
| C6 | **High** | **Optimize silently re-rasterizes the whole design at ≤4px/mm (0.25mm grid)** — vs DST's 0.1mm resolution. Clicking Optimize (or any rebuild) roughens every edge; repeated edits accumulate damage. NN tour also runs on centroids, not exit→entry points, and can reorder a same-color detail beneath its base fill. | `rebuild_design` `px_per_mm = min(4.0, 800/max)` (`digitizer.py:580`); `optimizer.py:65-78` |
| C7 | **High** | **Manual/run stitches are ~6mm long** (max-stitch cap reused as run pitch; pro default ~2.5mm; snag-prone), and `density` on run objects is ignored. | `digitizer.py:636` (`_manual_run(poly, max_step_px, …)`) |
| C8 | **High** | **Fill subdivision uses `round()` not `ceil()`** → single stitches up to ~9mm ship despite the stated 6mm cap (measured 7.9mm). | `digitizer.py:294` |
| C9 | **High** | **Rebuild silently drops objects** whose `color_stop` doesn't match any stop number (object simply vanishes from output). | `digitizer.py:605` filter with no else/validation |
| C10 | **High** | **Unsupported glyphs digitize as tofu boxes on Linux** (the failing test); output depends on server-installed fonts; Arial/Helvetica paths are hardcoded and can't be legally bundled. | `lettering.py:22-35`; test run this session |
| C11 | **Medium** | **Quality scorer certifies broken output**: 8mm lettering with jump-crossed counters and no ties scored **98/A**. A trusted-but-wrong grade is worse than none. | `optimizer.py:139-186` checks only long/tiny stitches, jump count, color count |
| C12 | **Medium** | `selectedObject` can go stale after Optimize renumbers `sequence_order`; `path_metrics.stitch_count` counts command records while `Design.stitch_count` counts STITCH only (inconsistent reporting). | `designStore.ts` + `optimizer.py:56` |

**Security / integrity defects:**

| # | Severity | Defect | Evidence |
|---|---|---|---|
| S1 | **Blocker (at deploy)** | **Fail-open auth**: if any `SUPABASE_*` env var is missing/typo'd, `current_user` returns the `local-dev` sentinel — production would run **fully unauthenticated**, mix all users into one account, and store designs in a per-process dict that vanishes on restart. No startup validation. | `deps.py:20-21` |
| S2 | **High** | **All compute endpoints are unauthenticated**: `/digitize`, `/lettering`, `/convert`, `/export`, `/designs/rebuild`, `/optimize/*` have no `current_user` dep → free CPU for anyone + DoS surface. No upload byte caps (`await file.read()` unbounded), no rate limits, signup admin-creates **confirmed** users with no throttle. | routers; `deps.py` only used by designs CRUD |
| S3 | **High** | **RLS missing on `public.users`, `teams`, `team_members`** in the applied schema — Supabase tables without RLS are readable/writable via the public anon key (subscription_tier, usage counters exposed). RLS on the other tables is decorative anyway (service key bypasses it), so tenant isolation is only hand-rolled WHERE clauses. | `db/schema.sql:131-146` enables RLS on 7 tables, not those 3 |
| S4 | **Medium** | **No design update endpoint** — every ☁ Save creates a new row; the design list fills with duplicates; `design_versions` never accrues history. | `routers/designs.py` (POST/GET/DELETE only) |
| S5 | **Medium** | Bearer tokens in localStorage (XSS blast radius); CORS `allow_credentials` + wildcard methods/headers; no prod origin story documented. | `main.py:32-38`, `lib/auth.ts` |

**Scalability defect (will bite in week one of beta):**

- **X1 (Blocker at beta):** CPU-heavy digitize/rebuild/lettering/convert/package run **synchronously
  inside `async def` handlers** → they block the FastAPI event loop; one digitize freezes every
  request including `/health`. No job queue, no progress channel. First fix is a one-word change
  (`async def` → `def` moves them to the threadpool); real fix is a queue (arq/Celery) before >10
  concurrent users. Also: every edit round-trips the **entire design as JSON** (a 50k-stitch jacket
  back = tens of MB per Apply); fine for 87-stitch fixtures, unusable at commercial sizes.

---

## 5. Domain quality — the professional bar (master-digitizer assessment)

The stitch engine's current output would be rejected by a paying embroiderer on first stitch-out.
The full gap list, empirically probed:

1. **Locks (C1)** and **hole-crossing (C2)** — see above. These two alone disqualify commercial use.
2. **Satin has no spine** — one global `minAreaRect` angle per region; stitch direction never turns
   along a curve; concave shapes get bridged (ring → SATIN produced 135 stitches sewn straight
   across the hole). Curved narrow strokes fail the aspect test and silently fall back to 0° tatami
   (a 2.25mm S-curve stroke became TATAMI with 7.9mm stitches). No corner mitre/cap, no
   short-stitching on curves, no max-width auto-split.
3. **Lettering is tatami-filled raster blobs** — 'Peak' at 8mm (standard left-chest size) = **166
   stitches total** (~40/letter, p95 length 5.8mm); professional satin lettering runs 150-250
   st/letter at that size. PIL basic kerning, straight baseline only, i-dots vanish below ~8mm,
   each letter costs an untied trim. **Lettering is the #1 commercial workload — this is the first
   head-to-head loss vs every competitor including free ones.**
4. **All fills stitch at 0°** (`stitch_angle=0.0` hardcoded at digitize) — visually flat, push/pull
   accumulates in one direction, and it's the single most visible amateur tell.
5. **Density/coverage**: 0.6mm rows vs the ~0.35-0.42mm industry default at 40wt (fabric grins
   through); no tatami offset patterns (moiré/unstructured texture); not fabric- or
   thread-weight-aware.
6. **Pull comp is omnidirectional dilation** — satin columns get *longer* as well as wider (tip
   registration collisions), and holes shrink: at knit defaults (0.4-0.5mm/side), counters under
   ~1mm close entirely. Real pull comp extends endpoints along the stitch axis only.
7. **Path planning**: entry/exit points fall wherever the scan starts; every transition is
   TRIM+JUMP even between touching same-color regions; `TRAVEL_RUN` exists in the model but is
   never generated. Trim count = cycle time + 2 untied tails each.
8. **Fabric handling is cosmetic**: `fabric_type` maps to one pull-comp scalar and nothing else —
   no density multiplier, underlay recipe, stitch-length floors, cap sequencing (bottom-up/
   center-out), or stabilizer/needle recommendations (Worksheet has the fields; PDF never fills them).
9. **Rebuild raster tax (C6)**: 0.25mm grid on every rebuild vs 0.1mm DST resolution; DST header
   `LA:` name field never set (shops identify files on the machine panel by it).

**Strengths to keep:** boustrophedon fill skeleton with per-row run splitting and RETR_CCOMP hole
carving is a correct baseline; appliqué procedure (placement→tackdown→cover) is right *except* C3;
darkest-first sequencing is a sane default; validation blocking on hoop-fit is correct.

---

## 6. Competitive landscape & strategy (web-researched, 2025-26 pricing)

### The field

| Tier | Product | Price | What they have that we lack |
|---|---|---|---|
| Pro | Wilcom ES 2026 | $3,999 perpetual / ~$1,490yr | 200+ satin fonts, spine satin, stitch-level editing, cap/3D-puff/sequin, CorelDRAW bundled, 395k users |
| Pro | Tajima Pulse DG17 | dealer-tiered | Illustrator integration, machine networking, 170+ fonts |
| Pro | Chroma Luxe (Ricoma) | $2,499 + ~$41/mo | 250 fonts, machine integration |
| Hobby | Hatch 4 (Wilcom) | $1,199 (or $99/mo FlexPay) | ~100 fonts, PhotoStitch, hoop libraries (Mighty Hoop etc.), vector import |
| Hobby | Brother PE-Design 11 | $1,958 | 130 fonts, PhotoStitch, wireless transfer, 1,000 bundled designs |
| Hobby | Embrilliance (Mac+Win) | $199-$369+ | resize-with-recalc of purchased designs, BX font ecosystem, merge/lettering |
| Hobby | Embird | $149 + modules | stitch-level editing (Studio $150), Sfumato photo ($90), fonts ($145) |
| Free | Ink/Stitch (OSS) | $0 | 100+ hand-digitized fonts, vector-native SVG, batch lettering |
| Web | **Embrowser** ⚠ closest threat | $0 / $9.99mo | motif/gradient/cross-stitch fills, auto-route, 100 fonts, 3D preview, community, cloud |
| Web | Ember | free / Pro | 24 fill patterns, 7 run types, 25 fonts, free commercial use |
| AI service | StitchFast / Stitch AI / EmbroidAI | £3.50/design, £29.99/mo, free | instant logo→file conversion — but **flat, non-editable output** |

### The strategy (adopt this)

- **Attack segment:** small embroidery businesses + prosumers (Etsy sellers, 1-2 machine shops,
  spiritwear/promo side businesses) **+ Mac/Chromebook users** — the wide-open **$10-50/mo band**
  between thin web tools ($0-9.99) and $1,199+ Windows-only desktop. **Do NOT attack pro bureaus
  first** (stitch-level editing, puff/sequin/cap distortion, machine networking = years of moat).
- **Wedge positioning:** *"The browser embroidery studio where auto-digitizing stays editable — and
  production-ready."* Two provable claims nobody else combines: (1) vs AI services — their output
  is a flat DST; ours stays editable objects; (2) vs Embrowser/Ember — neither ships worksheets,
  color cards, package ZIPs, quality scoring, or path optimization.
- **Pricing:** freemium SaaS. Free = ~10 cloud designs, full editing, watermark-free export;
  Studio **$12-15/mo** = unlimited + production packages + full thread catalogs; later Shop
  $29-39/mo = team seats. **Avoid per-design credits** (the stated pain of the AI-service tier).
- **Marketing ammunition:** Windows-only lock-out; $1,199-$3,999 price shock; dongles; Embird's
  modular nickel-and-diming; Ink/Stitch's Inkscape dependency; AI services' non-editable output.
- **Neural AI (Phases 8-9) is NOT the priority.** The 2025-26 AI-digitizing wave proves customers
  accept approximate digitizing when it's instant, cheap, and *fixable* — we already beat them on
  fixable. Revisit neural once revenue funds data collection; meanwhile the rebuild loop can
  capture **user corrections** — a training-data asset no incumbent collects.
- **Watch list:** Embrowser cadence (match its fill/font breadth within two quarters); Wilcom's
  cloud push; Hatch FlexPay normalizing subscriptions (validates our model).

### Table-stakes features we're missing (market blockers, in order)

1. **Satin-stroke lettering + real font library** (25-50 pre-digitized/OFL fonts + monogram frames)
   — every competitor down to free tools clears this bar; we don't.
2. **Move/scale/rotate/mirror transforms** — confirmed absent; the only "scale" in the app is
   viewport zoom. *A studio that cannot resize a design to fit a hoop is unusable for a single
   paying customer.* Our contour architecture makes true re-stitch resize nearly free — a feature
   Embrilliance built a $199 business on.
3. **Thread catalog**: currently **5 sample colors**. The CIE-Lab matcher is built but has nothing
   to match. Ingest Madeira/Isacord/Robison-Anton (200-400 colors each; data entry, not
   engineering; pursue brand licensing — brands give color cards to software vendors because it
   sells thread).
4. **Public deployment + billing + free tier** — the product currently exists only on localhost;
   every comparison is moot until a URL converts visitors.
5. **SVG/vector import** straight into the contour pipeline (logos arrive as vectors; rasterizing
   them through k-means needlessly degrades our best-case quality).
6. **Import handling**: resize-with-density-recalc (±20% safe band) + design merge + add-lettering
   — the core hobbyist "personalize a purchased .PES" workflow.
7. **Fill/effect variety**: motif, contour/spiral, gradient fills, bean run — Embrowser ships some
   of these on its *free* plan.
8. **Hoop library by machine brand/model** (users think "Brother 4x4", not millimeters).
9. Deferred consciously: stitch-level editing, PhotoStitch mode, machine connectivity, puff/sequin —
   pro-tier features, post-wedge.

---

## 7. Ship-readiness (ops) — from repo to paid service

**Blockers:** no deployment story at all (no Dockerfiles/hosting/CDN; frontend only ever served by
Vite dev server); fail-open auth (S1); event-loop blocking (X1); zero monetization plumbing (schema
columns exist, nothing reads them); no upload caps / rate limits / signup throttle (S2); no data
lifecycle (no update endpoint, hard cascade deletes, **no password reset** — users are locked out
in week one, no account deletion/export → cannot lawfully serve EU/UK, no backup config, no
ToS/privacy).

**Major:** observability is one log line (no Sentry, no request IDs, `/health` checks nothing);
service-key-only data path (one leaked key = entire DB; no rotation story); font licensing +
determinism (C10); missing commercial surfaces (library is a text popover — no thumbnails, search,
share links; teams exist only in schema; free-text hoop entry); thread-catalog data rights
unanswered; CI never run and omits lint/e2e/audit/coverage; multi-MB JSON round-trips per edit;
**legal**: spec publicly targets .EMB/.ART (closed formats — DMCA/EULA risk; de-scope from claims),
no LICENSE file, no trademark screen on "STITCHIQ".

**Environment drift:** local venv py3.11, CI pins 3.12, STATUS claims 3.14 — pick one (3.12
recommended for wheel coverage) and enforce in CI.

---

## 8. The battle plan — priority-ordered

> Rule for build sessions: **finish a phase before starting the next.** Within a phase, items are
> ordered. Every engine change ships with a regression test + re-run of the acceptance probes below.

### Phase A — Make it TRUE (correctness + trust; ~1-2 weeks of focused work)

| # | Task | Ref |
|---|---|---|
| A1 | ✅ *(done this branch)* `pyembroidery` into requirements-dev; CI installable | §2 |
| A2 | **Lock stitches**: tie-in at every object start, tie-off before every TRIM/COLOR_CHANGE/END in `digitize_image` + `rebuild_design`. Same-day stopgap: pass `tie_on`/`tie_off` THREE_SMALL contingencies to `pe.write` | C1 |
| A3 | **Never cross open fabric**: connection segments must stay inside the region mask; route travel inside the fill around holes; TRIM any unavoidable crossing. Acceptance: ring probe = 0 counter crossings | C2 |
| A4 | **Appliqué STOP sequence**: STOP after placement outline and after tackdown (operator places/trims fabric) | C3 |
| A5 | Honor satin `stitch_angle` on rebuild; make the underlay enum honest (implement zigzag/double-zigzag/parallel/contour *or* hide unimplemented options) | C4, C5 |
| A6 | Fill quality quick wins: 0.4mm default spacing; `ceil()` subdivision with ~4mm max fill stitch; per-region auto angles (region long axis, alternated); tatami offset pattern (25/33% phase) | C8, §5.4-5.5 |
| A7 | Run pitch 2.5mm default + density-aware; fix manual-run 6mm bug | C7 |
| A8 | Rebuild validation: raise on orphan `color_stop` refs instead of dropping objects; raise rebuild raster to ≥10px/mm | C9, C6 |
| A9 | **Quality scorer rewrite** around real rejection criteria (coverage vs fabric, jumps over open fabric, unlocked ends, satin width violations, uniform angles, trims/1000st) — or drop the letter grade until then | C11 |
| A10 | **Fail-fast config**: `APP_ENV=production` refuses to boot without Supabase keys; sentinel/in-memory only in dev | S1 |
| A11 | Auth on all compute endpoints; upload byte caps (10-20MB); slowapi rate limits on digitize/convert/signup/login; email confirmation on signup | S2 |
| A12 | Bundle 3-5 OFL fonts in-repo (deterministic output, kills Arial licensing risk); reject unsupported glyphs properly (fixes the failing test) | C10 |
| A13 | `PUT /designs/{id}` (update + version snapshot); RLS on `users`/`teams`/`team_members` | S4, S3 |
| A14 | Doc-sync pass: README/STATUS counts, remote, branch, python version; commit this review | §2 |

### Phase B — Make it SELLABLE (the wedge; ~4-8 weeks)

| # | Task |
|---|---|
| B1 | **Deploy**: 2 Dockerfiles + compose; backend → Fly/Railway (gunicorn, 2-4 workers, `def` handlers → threadpool), frontend → Vercel/CF Pages; CI green on GitHub + eslint + pip/npm audit; Sentry both apps; real `/health`; uptime monitor |
| B2 | **Transforms**: move/scale/rotate/mirror on canvas — contour-space for digitized designs (rebuild does the rest), stitch-space with density recalc (±20%) for imports |
| B3 | **Spine-based satin engine**: medial-axis spine + rails, perpendicular sampling with interpolated angles, corner mitre/cap, short-stitch on curves, min/max width guards with auto-split. *Largest single quality jump; unblocks lettering* |
| B4 | **Vector lettering**: fontTools glyph outlines → stroke decomposition → satin engine; real kerning/shaping; baseline modes (incl. arc); size minimums with warnings; 25-50 OFL fonts + monogram frames |
| B5 | **Thread catalogs**: Madeira/Isacord/Robison-Anton full charts into `thread_database` (+ licensing outreach); wire the already-built CIE-Lab matcher, color cards, worksheets |
| B6 | **SVG import** → paths/fills parsed directly into contours (skip k-means); biggest cheap quality multiplier for logo work |
| B7 | **Billing**: Stripe Checkout + webhook → `subscription_tier`; quota dependency (free: ~10 designs, N digitizes/day) on the existing schema columns; pricing page; password reset; ToS + privacy; account delete/export |
| B8 | **Library & sharing**: thumbnail grid (store the package preview PNG in Supabase Storage), tokenized read-only share links (viral loop), hoop/machine profile catalog (static JSON), stabilizer/needle lines on the worksheet from a fabric profile table |

### Phase C — Make it WIN (quarter 2+)

- Fabric profile table driving density/underlay/pull-comp/stitch-floors/cap-sequencing + worksheet.
- Directional pull comp (endpoint extension along stitch axis, holes preserved).
- Path planner: closest exit→entry chaining, travel runs under later coverage, trims only when exposed; optimizer on entry/exit points; no re-raster tax.
- Fill/effect library: motif, contour/spiral, gradient fills, bean run; zigzag/double-zigzag underlay.
- Job queue (arq/Celery + Redis) + SSE progress; payload diet (send params+ids, not full design JSON; stitches to Storage as binary).
- Import merge + add-lettering ("personalize a purchased design"); stylized photo mode (edge-directed runs) — not photoreal.
- Community: public gallery, starter pack; then teams (schema ready).
- JWT pass-through to PostgREST so RLS enforces tenancy in depth.
- Only then: neural digitizing, trained on the user-correction data the rebuild loop captures.

### Acceptance probes (run after every engine change)

1. **Ring test**: digitize a letter-'o' ring → 0 jumps/stitches crossing the counter; counter present down to 1.5mm.
2. **Lock test**: exported DST contains tie-in/tie-off around every trim (parse and assert).
3. **Lettering test**: "Peak" at 8mm → ≥150 st/letter satin, i-dot present at 6mm, deterministic across OS.
4. **Angle test**: satin object edited 0°→77° produces different, correct output; fill regions get non-uniform default angles.
5. **Appliqué test**: exported file contains STOP after placement and after tackdown.
6. **Fidelity test**: rebuild of an unedited design changes no coordinate by >0.1mm.
7. **Suite**: pytest + vitest green *in CI on GitHub*, not just locally.

---

## 9. Scorecard

| Dimension | Grade | One-liner |
|---|---|---|
| Architecture & data model | **A-** | The right chassis; contour-rebuild is the moat |
| Code hygiene & tests | **B+** | Real suites and honest docs; CI never exercised, e2e not committed |
| Stitch-engine correctness | **D** | Locks, hole-crossings, appliqué STOP, angle no-op — production-disqualifying today, all fixable in-place |
| Digitizing quality vs pros | **C-** | Correct skeleton; no spine satin, flat angles, thin density, cosmetic fabric handling |
| Lettering | **F** | Below the free-tool bar; the #1 commercial workload |
| Security & tenancy | **C** | Good scoping instincts; fail-open auth, open compute, RLS gaps |
| Scalability | **D** | Event-loop blocking + full-JSON round-trips; fine at demo scale only |
| Ship-readiness (deploy/billing/legal) | **F** | Localhost-only, no billing, no policies, no LICENSE |
| Competitive positioning potential | **A-** | Real wedge, vacant price band, provable differentiators |

**Bottom line:** a genuinely promising product one focused quarter away from a sellable wedge —
provided the order of operations above is respected: correctness first, then deploy+sell, then breadth.

---

## 10. How to use this document (for the user & other build sessions)

- **The user (founder):** treat §8 as the backlog of record. When another Claude session proposes
  work, check it against the phase order; anything below the current phase is a distraction. The
  two questions to ask of any "done" claim: *which acceptance probe proves it* and *is CI green on
  GitHub*.
- **Build sessions (Claude or human):** read §4-§5 before touching `digitizer.py`. Keep the STATUS.md
  discipline (changelog row per change). Never mark a feature 🟢 without an acceptance probe. Do not
  re-litigate the market strategy per-session; it's decided in §6 until the user changes it.
- **Review cadence:** re-run the multi-agent review after Phase A and after first deploy; the
  remaining planned deep-dive (5 code-level bug-finder agents: engine math, API contracts, security,
  frontend state, frontend libs) is pending and will be appended as **Appendix A** when it completes.

*Prepared by the CTO-review session on branch `claude/code-review-competitive-o2qw0o`. Sources for
all pricing/feature claims in §6: vendor pricing pages and product documentation retrieved
2026-08-07 (Wilcom, Hatch, Embrilliance, Embird, Brother, Tajima, Ricoma, Ink/Stitch, Embrowser,
Ember, StitchFast, Stitch AI, EmbroidAI).*
