# v2 Part 60 — the Part 59 decisions, visible in the UI

**Date:** 2026-08-07 · **Branch:** `claude/code-quality-improvements-hyu6dg`
**Work order:** surface `trim_profile` and the colour-cap warning in the
frontend without changing any default. UI follow-through, not a redesign.

**Both surfaced, no default moved, and the gate-1 claim is pinned at the
request level:** an untouched control produces a request **byte-identical** to
what the app sent before the control existed — the default profile is omitted
from the URL, not sent-and-ignored. Captured from the live app:

```
aggressive selected:  /api/export/package?format=dst&trim_profile=aggressive
control untouched:    /api/export/package?format=dst
```

---

## 1. The trim control

This app has no export dialog — the toolbar's format select **is** the export
UI — so the control is a sibling select, in user language:

| option (what the user reads) | wire value |
|---|---|
| **Trims: safe (any machine)** — default | `conservative` (omitted from the URL) |
| **Trims: fewer (auto-trim machines)** | `aggressive` |

Helper text rides on the control and each option as its tooltip: *"For machines
with an auto-trimmer: short connecting threads (under 10 mm) are carried instead
of trimmed, saving machine time. Stitching is identical — only the trim commands
change."*

One catalogue (`lib/exportOptions.ts`) feeds the control, the API client and the
tests, so the labels users read and the values the backend receives cannot
drift. A test asserts the wire values never appear in the labels. Both
`exportDesign` and `exportPackage` take the profile; the Export path's advisory
validate preflight is untouched.

## 2. The warning display

`App.tsx` has rendered every `Design.warnings` entry verbatim since Part 25 —
the mechanism the brief said not to duplicate, and it is not duplicated. The
block is extracted unchanged into `DesignWarnings.tsx` so the present/absent
contract is testable in this repo's node test environment
(`react-dom/server.renderToStaticMarkup`, no new dependencies): the Part 59
colour-limit message renders verbatim; empty, undefined and null render nothing
at all.

**One honest note on gate 3.** The digitize dialog already clamps its colour
input at `max={8}`, so a UI user cannot *request* more than 8 — the inert range
is simply not offered, which is Part 58's decision expressed as UX. The warning
therefore reaches the screen on designs that arrive carrying it: digitized via
the API, opened from saved masters, or loaded from the cloud. Widening the
dialog to 12 just to make the warning reachable would add a knob that does
nothing — the exact anti-pattern Parts 57–58 closed — and was not done.

## 3. Evidence

`docs/benchmarks/v2-part60-ui/` — screenshots of the real app (Vite dev build,
Chromium), with a design carrying the Part 59 warning loaded through the app's
own Saved mechanism:

- `warning-banner.png` — the colour-limit warning rendered verbatim in the
  existing warnings banner
- `toolbar-default.png` — the toolbar with the control at "Trims: safe (any
  machine)"
- `toolbar-aggressive.png` — "Trims: fewer (auto-trim machines)" selected,
  sitting beside the format select

The request URLs above were captured from the same session by clicking the real
Package button — not from unit tests.

## 4. Gates

| Gate | Result |
|---|---|
| Untouched control behaves exactly as before | ✅ the default is omitted from the URL; captured request is `?format=dst`, byte-identical — plus `exportQuery` tests pin it |
| Aggressive actually sends the parameter, tested | ✅ captured live (`&trim_profile=aggressive`) and pinned by `exportQuery` + option-value tests |
| Warning visible when present, absent when not | ✅ `DesignWarnings` render tests both ways, screenshot of the live banner |
| Frontend tests pass | ✅ **143 passed** (131 + 12 new), `tsc` at its pre-existing baseline (0 new errors) |
| Backend locks/baselines unmoved | ✅ 26 passed (4 locks, 10 visual baselines); **no backend file changed** |

## 5. Files

- `apps/frontend/src/lib/exportOptions.ts` — profile catalogue + `exportQuery`
- `apps/frontend/src/components/toolbar/TrimProfileSelect.tsx` — the control
- `apps/frontend/src/components/feedback/DesignWarnings.tsx` — extracted banner
- `apps/frontend/src/api/client.ts`, `Toolbar.tsx`, `App.tsx` — wiring
- 12 new tests across `exportOptions.test.ts`, `DesignWarnings.test.tsx`,
  `TrimProfileSelect.test.tsx`
- `docs/benchmarks/v2-part60-ui/` — three screenshots

## 6. Residual

The select uses `title` tooltips for helper text, which matches how every other
toolbar control explains itself in this app — but tooltips are invisible on
touch devices. If the export flow ever grows a real dialog, the helper text
should move into it as visible copy.
