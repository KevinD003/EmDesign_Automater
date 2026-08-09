# Handoff: STITCHIQ — Atelier redesign

## Overview

A full visual and structural redesign of the STITCHIQ frontend (`apps/frontend`),
covering the Studio, the dashboard, auth, and the marketing landing page — plus
several surfaces the current build does not have (command palette, design
library, production queue, thread inventory, templates gallery, onboarding).

The direction is **Atelier**: warm paper, an Instrument Serif display face, an
antique-brass accent, and monospaced numerals for every measured value. It
avoids the violet/indigo-on-near-black palette that reads as generic, and takes
its cue from craft-house and pro-audio tooling instead.

## About the design files

`StitchIQ.dc.html` in this bundle is a **design reference**, not production
code. It is a single self-contained file so it opens in any browser with no
build step. It happens to run on React, but it is not the `.tsx` you should
ship — it is the specification you implement against.

The task is to **recreate this design inside `apps/frontend`** using its
existing environment: React 18 + TypeScript, Vite, zustand stores, hash
routing, and the `.dz-*` / `.app-shell` class conventions already in
`index.css`. Do not port the HTML file wholesale.

Three files in `src/` **are** production code and can be used as-is:

| File | What it is |
| --- | --- |
| `src/styles/atelier.css` | The token layer. Import once after `index.css`. |
| `src/lib/useTheme.ts` | Widened theme hook — replaces the `useState` inside `DashShell`. |
| `src/components/command/CommandPalette.tsx` | New ⌘K palette, wired to `designStore` + `routes`. |
| `src/components/nav/MobileTabBar.tsx` | New sub-64rem navigation. |

## Fidelity

**High-fidelity.** Colours, type, spacing, radii and interaction states are all
final. Match them. Where the design and the current build disagree on
*behaviour*, the current build wins unless this document says otherwise — the
redesign was authored against `main` and deliberately preserves your logic.

## Approach: restyle, don't rewrite

Your components already use semantic class names (`.dz-nav-item`, `.panel-right`,
`.view-toggle`). `atelier.css` redefines the values those classes read. So the
cheapest correct path is:

1. Add the font `<link>` tags to `apps/frontend/index.html` (listed in
   `atelier.css`).
2. `import './styles/atelier.css';` in `main.tsx`, after `index.css`.
3. Replace the hard-coded colour literals in `index.css` with the `--sq-*`
   tokens. Mechanical, one pass, no markup changes.
4. Swap `DashShell`'s local theme state for `useTheme()` and delete its
   `data-theme` prop — see "Theme" below.
5. Mount `<CommandPalette />` and `<MobileTabBar />` in `App.tsx`.

Only then build the genuinely new screens.

## Theme

Today `data-theme` is set on `.dz-root`, so it themes the dashboard only. The
Studio is hard-dark and overlays rendered outside that subtree never receive
the attribute at all.

`useTheme()` stamps `data-theme` on `<html>` instead. One attribute themes every
surface including portalled overlays. `lib/theme.ts` is unchanged — it already
resolves saved-choice → OS preference → dark, which is the right ladder.

The Studio becoming themable is intentional and was an explicit request. The
comment in `theme.ts` arguing the Studio must stay dark is a reasonable
position, but the user has asked for a switch; keep dark as the Studio's
*default* and let the toggle override it.

## Screens

### Studio

Layout unchanged: toolbar / left rail / canvas / right rail / player. What
changes:

- **Toolbar** — tools become a segmented group inside a `--sq-surface-2` well
  rather than loose buttons. Export becomes a split control: format `<select>`
  and Export button share one bordered shell.
- **Left rail** — colour sequence, objects, and a new **version history** list.
  Sequence rows carry a zero-padded mono index, a 1rem swatch, the name, and a
  right-aligned mono stitch count.
- **Canvas** — `--sq-canvas-bg` with a 5%×8% grid at `--sq-canvas-grid`. The
  hoop guide is a 1px dashed `--sq-canvas-guide` rect. 2D/TrueView toggle sits
  top-right, stitch/size/colour badge bottom-left, zoom bottom-right.
- **Right rail** — Quality (score in Instrument Serif at 2.7em, tone-coloured
  grade, progress bar, four metrics), Properties, Thread palette (6-col grid of
  square swatches), and a new Stitch-GPT panel.
- **Player** — round accent play button, full-width scrub, mono
  `current / total` readout, estimated sew time.

### Dashboard

Sidebar grows from four items to eight: Overview, Library, Analytics,
Production, Threads, Templates, Account & plan, Admin. Admin stays gated on
`account?.role === 'admin'` exactly as it is now.

- **Overview** — four stat tiles, "In the Studio now" card, recent activity list.
- **Library** — responsive card grid, `minmax(14rem, 1fr)`, 4:3 thumbnails.
- **Analytics** — six stat tiles, stitch-length histogram, per-thread usage
  bars, needle-down vs travel split, capability matrix.
- **Production** — job queue rows with status, progress bar, ETA.
- **Threads** — inventory table with stock level and per-design usage.
- **Templates** — gallery grid, click loads into the Studio.
- **Account** — profile, recovery email form, plan ladder. Plans are
  admin-assigned; there is no billing flow and the design does not invent one.
- **Admin** — five stat tiles, user table with plan/role selects, feature matrix.

### Auth

Username + PIN, matching `AuthPages.tsx` — *not* email/password. Field notes
("leave empty if none", "4+ characters", "for PIN recovery") are preserved
verbatim. Reset takes an email and returns the one-time/30-minute message.

### Landing

New. Sticky header, serif hero with an italic brass clause, live stitch preview
on canvas, four numbered feature cards, mono credibility strip.

## Interactions

| Interaction | Spec |
| --- | --- |
| ⌘K / Ctrl-K | Toggle command palette. ↑↓ move, Enter runs, Esc closes. |
| `?` | Keyboard shortcut sheet. |
| Space | Play/pause stitch-out (Studio only, not while typing). |
| D / T | Digitize / Lettering dialogs. |
| Esc | Cancel drawing → `setTool('select')` (existing behaviour, keep). |
| ⌘Z / ⇧⌘Z / ⌘Y | Undo / redo (existing, keep). |
| Colour stop click | Toggles isolation — selected stop at full opacity, others at 0.30. |
| Property slider | Debounce, then rebuild. Density > 0.62mm shows an inline pucker warning. |

Transitions: 0.15–0.2s ease-out for overlays, 0.3s for progress bars. All
animation is disabled under `prefers-reduced-motion: reduce`.

## Accessibility

Target is **WCAG AAA**, and it must hold at any zoom on any browser.

- Every interactive control is ≥44px in its smallest dimension.
- One visible focus ring (`:focus-visible`, 0.18rem accent, 0.12rem offset).
  Never remove it.
- Sizing is `rem` / `%` / `clamp()` — no fixed `px` except hairline borders, so
  browser font-size settings scale the whole UI.
- Toggle buttons carry `aria-pressed`; nav items carry `aria-current="page"`;
  overlays are `role="dialog" aria-modal="true"` with a label.
- Progress and toast regions are `role="status"` with `aria-live="polite"`.
- Icon-only buttons always carry `aria-label`.
- A "Skip to content" link is the first focusable element.

## Design tokens

All tokens live in `atelier.css`. Summary of the light surface:

| Token | Value | Use |
| --- | --- | --- |
| `--sq-plane` | `#f7f4ee` | Page background |
| `--sq-plane-2` | `#efeae0` | Canvas surround |
| `--sq-surface` | `#fffdf8` | Cards, rails, headers |
| `--sq-ink` | `#26221c` | Body text |
| `--sq-muted` | `#625b4c` | Secondary text |
| `--sq-faint` | `#8b8271` | Labels, meta |
| `--sq-line` | `#e2dcd0` | Borders |
| `--sq-accent` | `#a8702a` | Accent fills |
| `--sq-accent-text` | `#7d5017` | Accent text (AAA on `--sq-surface`) |
| `--sq-good` / `--sq-warn` / `--sq-bad` | `#2f6b3f` / `#8a6210` / `#8f2f24` | Status |

Dark surface values are in the same file under `[data-theme='dark']`.

**Radii** — 0.3 / 0.45 / 0.9 / 1.2rem. **Type scale** — base
`clamp(0.82rem, 0.95vw, 0.95rem)`; labels 0.8em; display 1.4–2.7em; hero
`clamp(2.6rem, 5.2vw, 4.4rem)`.

## Data & correctness notes

Two things the redesign fixed that are worth carrying over:

1. **Every analytics figure is derived, never hard-coded.** Stitch counts,
   travel percentage, longest jump, histogram bins and per-thread lengths are
   all computed from the stitch stream. Wire these to `lib/analytics.ts`.
2. **No invented commercial data.** The plan ladder carries the feature lists
   from `AccountPage.tsx` and no prices, because no prices exist anywhere in
   the codebase. Do not add them without a real pricing decision.

## Assets

None external. Thumbnails in the reference are generated procedurally on
canvas; in production they should be real design renders. Fonts are Google
Fonts (Instrument Serif, Archivo, Archivo Narrow, JetBrains Mono) — self-host
them if you want the app to work offline.

## Files in this bundle

```
StitchIQ.dc.html                              the design reference (open in a browser)
src/styles/atelier.css                        token layer — ship as-is
src/lib/useTheme.ts                           theme hook — ship as-is
src/components/command/CommandPalette.tsx     new — ship as-is
src/components/nav/MobileTabBar.tsx           new — ship as-is
```

## Suggested order

1. Tokens + fonts + `useTheme` (whole app shifts to Atelier, no new screens).
2. Studio rails and player restyle.
3. Command palette + mobile tab bar.
4. Dashboard sidebar expansion; Library, Production, Threads, Templates.
5. Analytics rebuild against `lib/analytics.ts`.
6. Landing page.
