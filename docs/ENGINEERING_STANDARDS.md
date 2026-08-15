# STITCHIQ Engineering Standards

> **Status: binding.** Applied informally since v2 Part 3 and reconstructed from
> chat each time; written down in v2 Part 5 so a future part reads it from the
> repository instead of from memory. If a rule here is wrong, change it here —
> not silently in a review.

Every rule below is stated so it can be **measured**, and the command that
measures it is given. A part's report must paste the actual numbers, not the
verdict: "90 passed" is not a coverage report, and "looks clean" is not a
security review.

---

## 1. Verification: measure, don't assert

The gate this project runs on is that claims get checked. A v2 Part 1 report
claimed "88 passed" when the documented install produced `1 failed, 87 passed`,
and the reviewer caught it. That is the failure this section exists to prevent.

**Every part must paste exact command output for:**

| Check | Command |
|---|---|
| Backend tests, optional deps present | `pytest -q` |
| Backend tests, optional deps absent | `STITCHIQ_DISABLE_REMBG=1 pytest -q` |
| Frontend tests | `cd apps/frontend && npx vitest run` |
| Coverage on every file touched | `pytest -q --cov=<module> --cov-report=term-missing` |
| Lint | `ruff check <changed files>` |

**Both** rembg paths are mandatory. `rembg` is optional (`requirements-features.txt`,
176MB model) so the pipeline behaves differently with and without it, and a suite
that only ever runs one way hides environment-dependent failures — exactly what
happened in Part 1.

**Report coverage as a percentage, not a pass count.** Pass counts say nothing
about whether new code is exercised: Part 4 added a fallback path that no test
reached, and only `--cov` showed it.

**Coverage floor: 80% on any file you touch**, and new code should not lower a
file's existing figure. Below the floor, either add tests or state in the report
which paths are uncovered and why.

**Regressions get a test.** Every defect found during a part gets a test that
fails before the fix. Part 4's along-edge micro-stitch bug survived three parts
because nothing pinned it.

## 2. Measurement infrastructure

Anything used to grade the pipeline lives in the repository, not in a report.

- `apps/backend/scripts/run_quality_bench.py` — the 10-fixture regression corpus.
  Run with `--tag <part>` and diff against the previous tag. **Never** change the
  corpus to make a number move; add a separate probe instead.
- `apps/backend/scripts/measure_stitch_quality.py` — coverage (interior /
  edge band / spill) and penetration density. The single definition of those
  measurements; audits call it rather than restating the method in prose.
- `apps/backend/tests/fixtures/curvature_probe/` — targeted instruments, kept out
  of the bench corpus so "the corpus" keeps meaning the same ten fixtures.

**Report interior and edge-band coverage separately.** Averaging them hides a
ragged outline behind a full interior, which is the specific failure Parts 2–4
were chasing. Report spill alongside, because coverage alone rewards overshoot.

## 3. Code size

Measured on the definition including its docstring.

| Unit | Limit |
|---|---|
| Function | **~50 lines** |
| File | **~800 lines** |

These are guidelines with a hard reporting duty, not hard failures: **anything
over the limit must be named in the report with its actual line count.**

- Code you **add** is expected to comply. Part 4 added 15 functions, all ≤50.
- Code you **rewrite** should move toward the limit — Part 4 took `_skeleton_satin`
  from 133 to 53 lines.
- Pre-existing long code you do not touch is **out of scope**. `digitize_image`
  (822) and `rebuild_design` (183) are known and are not a given part's problem.

`app/services/digitizer.py` was the standing exception. **Part 42 split it** into
`app/services/digitizer/` — ten modules under a strict bottom-up layering, pinned by
`tests/test_digitizer_package_layering.py`, which fails if any import points upward.

Two exceptions remain, and both are deliberate. `constants.py` (760) is a flat list of
tunables with their measured rationale in comments — no control flow, so the length is
documentation. `pipeline.py` (1,131) is one function's fault: `digitize_image` is still
822 lines around a 412-line cluster loop carrying 18 mutable locals in and 7 out.
Extracting that loop needs a state carrier — a design change, not a move — so it is its
own piece of work.

## 4. Security and secrets

Before every commit:

- **No credentials in the diff** — no API keys, tokens, passwords, bearer values,
  private keys, or credentials embedded in URLs. Scan, don't eyeball:
  ```
  git diff -U0 | grep -E "^\+" | grep -viE "^\+\+\+" \
    | grep -inE "(api[_-]?key|secret|token|passwd|password|bearer|BEGIN [A-Z ]*PRIVATE KEY|https?://[^ ]*:[^ ]*@)"
  ```
- **Real secrets live only in gitignored `apps/backend/.env`.** Supabase keys are
  already there; nothing else joins them in tracked files.
- **No magic numbers.** A numeric constant that encodes a decision gets a module-level
  name and a comment saying what it is and, where one exists, what measurement set
  it. Thresholds tuned without a recorded measurement are the thing this rule
  exists to stop.
- **Uploads and untrusted input** stay bounded — size limits, format validation,
  and no path derived from user input reaching the filesystem unsanitised.
- **Errors must not leak internals.** 502 bodies do not carry the Supabase URL,
  query, or row ids (fixed in Update #32; do not regress it).

## 5. Commits and branches

- **Conventional prefixes**, required: `feat:` `fix:` `docs:` `test:` `chore:`
  `refactor:` `perf:`.
- Subject in the imperative, ~72 chars. Body explains **why**, and carries the
  measurements that justify the change.
- Develop and push on the branch named in the task. Never push elsewhere without
  being asked.
- **BOTH TEST LANES FINISH BEFORE THE PUSH.** Not "the default lane plus a
  judgement about the risk" — both, green, then push. The lanes are `pytest -q`
  and `STITCHIQ_NO_REBUILD_PASSTHROUGH=1 pytest -q`, about 25 minutes each on a
  4-CPU box.

  Made binding 2026-08-23. Three pushes had gone out with the second lane still
  running. Each was disclosed in its report and each came back green, so no
  damage was done and the disclosure worked — but three is a pattern rather than
  an incident, and the cost of waiting is minutes against a red `main` that
  every later measurement has to be re-attributed around. Disclosure was the
  right stopgap and is not a substitute for the rule.
- Do not chain (`&&`) or pipe (`| tail`) a test lane: the exit code becomes the
  chain's or the pipe's, and a red lane has been read as green that way.
- **No build artifacts committed** — `.coverage`, `__pycache__`, `node_modules`,
  local databases. (A `.coverage` file slipped into a Part 4 commit and had to be
  removed; `.gitignore` now covers it.)
- Open a pull request only when explicitly asked.

## 6. Honesty rules

These are not style preferences; they are what makes the phased process work.

- **A claim in a report must be reproducible from the repository.** If a number
  cannot be regenerated by a committed script, it does not belong in an audit.
- **Report what regressed.** Every audit since Part 2.5 carries a section for
  numbers that got worse. A report with no downside stated is not finished.
- **Corrections go in visibly.** When an earlier audit is found wrong, correct it
  in place with the correction marked — Part 1's false test claim, Part 4's
  finding that a bug had been masking three parts' edge-coverage numbers.
- **Record rejected options with their measurements.** An outward-bias knob was
  measured and declined twice (Parts 2.5 and 4); both are in the audits so the
  choice stays auditable instead of being re-litigated from scratch.
- **Say when something is unmeasured.** Part 4 shipped boundary-paced pitch and
  stated plainly that no metric detected its fabric-damage risk. Part 5 built the
  metric. That only works if the gap is written down.
