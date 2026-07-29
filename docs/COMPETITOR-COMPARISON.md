# Competitor comparison — STITCHIQ vs the market (July 2026)

**Method:** live web research, 2026-07-29 (four parallel investigations, ~12 targeted queries each).
Facts carry source URLs. **Caveat, stated rather than hidden:** the sandbox's egress proxy blocked
direct page loads of several publisher domains, so some facts come from search-result excerpts of
the cited official pages rather than full page fetches; those are flagged in the research notes.
STITCHIQ's own column reflects the codebase as of v2 Part 13, verified by reading the code
(references in [`LAUNCH-READINESS-GAPS.md`](./LAUNCH-READINESS-GAPS.md)).

## Where STITCHIQ actually sits

STITCHIQ is an **AI auto-digitizer with a browser editor** — its market is EmbroidAI / SewFlow /
StitchPilot / StitchFast, not Wilcom. Against that cohort it is feature-competitive on the core
pipeline and ahead on measurement transparency; the pro desktop suites (Wilcom, Hatch) remain far
ahead on lettering, manual digitizing depth, and fabric-assist maturity.

## Feature matrix

| Capability | **STITCHIQ (Part 13)** | Wilcom ES 2026 | Hatch Digitizer 3/4 | Embird+Studio | Ink/Stitch | EmbroidAI | SewFlow | StitchFast |
|---|---|---|---|---|---|---|---|---|
| Auto-digitize image | ✅ classical CV + optional U2-Net background removal | ✅ Smart Design, Color PhotoStitch | ✅ + PhotoFlash/Reef | ⚠ Trace tool; photos need Sfumato ($90) | ⚠ manual-first | ✅ core product | ✅ core product | ✅ core product |
| Fabric-aware settings | ✅ **12-fabric profile table**: pull comp + fill/satin density + underlay step + edge inset (Part 13; provisional values) | ✅ Auto Fabric Assistant: pull/underlay/density by fabric **and object size** | ✅ Auto Fabric with per-object-group values (tatami / wide satin / narrow satin / lettering) + custom presets + stabilizer recommendation | ❌ none found | ❌ manual params | ✅ knits/twill/caps/towels profiles (density + pull) | ⚠ light/medium/heavy density presets only | ⚠ AI-suggested pull comp |
| Pull compensation | ✅ per fabric 0.15–0.5mm/side, per-object editable | ✅ auto + per-object | ✅ auto per fabric + per-object | ✅ manual | ✅ manual | ✅ claimed | ⚠ unclear | ✅ suggested |
| Underlay | ✅ center-walk (satin) / edge-walk (fills), fabric-stepped | ✅ full menu incl. tatami/double-zigzag | ✅ auto, dual underlays (edge run + tatami/zigzag) | ✅ | ✅ several types | ✅ claimed | ✅ claimed | ✅ |
| Quality scoring | ✅ **0–100 score + findings, auto-run after every digitize, in the package ZIP** (Part 13); plus a dev bench no competitor publishes an equivalent of (coverage %, penetration floor, density cells) | ⚠ TrueView preview; no published score | ⚠ no published score | ❌ | ❌ | ✅ 0–10 DST analyzer (stitch stats, density, hoop fit, fix suggestions) | ❌ | ⚠ "AI analysis" |
| Machine-safety guarantees | ✅ **measured & enforced**: 0.30mm same-side floor (0 violations corpus-wide), 12.7mm cap, 0.5mm min stitch, density-cell watch | not published | not published | not published | not published | not published | not published | not published |
| Lettering | ⚠ TTF rasterize→digitize + letter-spacing control (Part 13); no kerning/baselines | ✅ 228+ digitized fonts, auto+savable manual kerning, 9 baselines, Team Names | ✅ 62–124 digitized fonts, baselines, on-baseline kerning handles | ✅ Font Engine plugin ($145) | ✅ satin fonts | ⚠ text via editor | ✅ text-to-embroidery, multiple fonts | ⚠ |
| Export formats | ✅ DST/PES/PEC/JEF/EXP/VP3/XXX/U01/CSV via pyembroidery (DST+PES round-trip tested; rest tested Part 13) | ✅ widest (EMB native + all majors) | ✅ EMB native + majors | ✅ ~70 formats | ✅ majors | ✅ DST/PES/EXP/JEF/VP3/XXX/HUS | ⚠ JEF/DST/PES auto (more via Pro service) | ✅ 7 formats |
| Jump/pathing optimization | ✅ Part 13: branch chaining + per-fragment fill (**−17% corpus jumps**); color grouping since Phase 4; opt-in NN object reorder | ✅ Branching (one trim per group), Closest Join | ✅ Closest Join, Optimize Color Changes | ⚠ manual | ⚠ manual | ✅ "pathing" claimed | ✅ "travel-path + corner optimization" claimed | ⚠ |
| Post-auto editing | ✅ full object editor (density/pull/underlay per object, rebuild) | ✅ deepest | ✅ deep | ✅ deep | ✅ | ✅ browser editor | ⚠ layer-level only | ✅ adjust step |
| Price model | TBD (self-hosted) | $999–$3,999 perpetual / $1,490/yr | $199–$1,199 perpetual (Digitizer 4 promo $899) | $149 + plugins | free | credits | free tier + subs; Pro human service $19.99/design | £4.99/design; £29.99/mo unlimited |

## What the research corrects or settles

1. **The "jumps per 1,000" target the Part 12 brief cited does not exist in published guidance.**
   The dedicated search found no such benchmark anywhere; production-efficiency guidance is
   expressed as **trim counts and time**: ~3–7s per trim, machine stops 6–20s, and a documented
   case where cutting 28 trims to 8 saved >15% run time
   ([erichcampbell.com](https://www.erichcampbell.com/digitize-embroidery-designs-productivity/)).
   STITCHIQ's quality report therefore reports the jump rate as an internal metric without claiming
   an industry threshold. Part 13's −17% corpus jumps (fixture 08 −41%) is the aligned improvement.
2. **STITCHIQ's density values sit inside published ranges** — wovens 0.4–0.5mm spacing, denim/canvas
   0.3–0.4, knits +10–15% spacing vs standard, fleece 0.5–0.6
   ([ezstitchdigitizing](https://ezstitchdigitizing.com/embroidery-stitch-density-guide/),
   [sewflow guide](https://sewflow.com/blog/embroidery-density-guide),
   [californiadigitizing](https://californiadigitizing.com/how-to-avoid-puckering/)). **Terry is the
   conflict case:** loft-generic guides group it with fleece (sparser), while terry-specific guidance
   says 10–20% *denser* so loops can't separate the stitching
   ([maggieframes](https://www.maggieframes.com/blogs/embroidery-blogs/how-to-embroider-towels-by-machine-expert-techniques-for-flawless-results));
   STITCHIQ follows the terry-specific source (0.4mm satin) and the fabric protocol's terry sew-out
   is the tiebreaker.
3. **The next real fabric-profile gap is underlay TYPE, not values.** High-loft fabrics want
   double-zigzag/knockdown underlay (10–20% density cross-hatch) to hold stitches above the pile
   ([Coldesi Underlay 101](https://support.coldesi.com/Portals/8/Documents/Liberty%20Docs/Underlay%20101.pdf),
   [machineembroiderygeek](https://www.machineembroiderygeek.com/what-is-a-knockdown-stitch/));
   width-dependent underlay selection (center-run <2mm, edge-run 2.5–3.5mm, zigzag >4mm —
   [embroiderylegacy](https://embroiderylegacy.com/embroidery-digitizing-underlay-digitizing/)) is
   how the pro suites pick. STITCHIQ picks by geometry only (center vs edge walk). Deferred with a
   named design in the gaps doc.
4. **Wilcom/Hatch's fabric assist varies by object size/group, not just fabric** — Hatch keeps
   separate fabric values for tatami, wide satin, narrow satin, and lettering. STITCHIQ's profile is
   flat per fabric. A second-order refinement, noted for a future part.
5. **EmbroidAI's 0–10 analyzer is the closest analogue to STITCHIQ's report** — transparent penalty
   model over stitch stats/density/hoop fit. STITCHIQ's 0–100 report now matches it feature-for-
   feature in the product (auto-run + packaged), and the dev bench (coverage %, penetration floor,
   per-cell density, per-object classification log) measures things no competitor publishes at all.
6. **Nobody in the AI cohort publishes machine-safety guarantees or a stitch-out warranty** —
   SewFlow explicitly routes "needs to be perfect" work to a $19.99 human service. STITCHIQ's
   enforced, measured floor (0 violations corpus-wide, machine-checked in CI) is a genuine,
   defensible differentiator worth marketing.

## Priorities this comparison implies (beyond Part 13)

1. Lettering depth (digitized-font quality, kerning, baselines) is the widest visible gap to every
   paid competitor — currently rasterize-then-digitize with a spacing control.
2. Underlay type selection (double-zigzag/knockdown for loft; width-dependent choice) — the
   highest-value remaining fabric-profile item.
3. Physical validation (fabric protocol + machine sew-outs) — the AI cohort's weakness too; doing it
   and publishing results would leapfrog, not follow.
4. Per-object-size fabric values (Hatch's four object groups) — refinement after underlay type.
