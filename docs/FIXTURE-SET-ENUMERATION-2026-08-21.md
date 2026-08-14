# Enumerating "the fourteen" before promoting — the standing rule applied to a set

**Required by the ruling of 2026-08-21, and reported BEFORE the promotion lands.** The standing
rule is: *when a field, unit, or space changes, list every calibrated constant evaluated against
it.* The fixture SET is that kind of quantity, and the sentence that triggered this — "promotion
turns fourteen into sixteen everywhere at once" — turns out to be **false**, which is the finding.

Method: grep for the literal count (words and digits) **and** for the set enumeration, then — the
part that mattered — for sites that do **neither**, because a site that never mentions either is
the one that will bite. That is the same warning that turned up nine thresholds where four were
expected on the space change.

---

## 0. THE HEADLINE: there is no single "the fourteen". There are three nested sets.

| set | size | defined in | member paths |
| --- | ---: | --- | --- |
| **the bench TEN** | 10 | `FIXTURE_PARAMS` (`run_quality_bench.py`) | `tests/fixtures/quality_bench/` |
| **the audit FOURTEEN** | 14 | `coverage_audit.fixtures()` = bench ten + `CORPUS_EXTRA` | + `tests/fixtures/corpus100/` @ 4 colours |
| **the lock FOUR** | 4 | `LOCK_FIXTURES` (`test_swarm_perf_lock.py`) — **hand-copied** | subset of the bench ten |

A01/A02 are real photographs in `corpus100/`, and `run_corpus100.py` puts them in its `BIG` set
(hoop `360x350`, not the `180x130` the C-tier four use). **They belong to none of the three sets
and match no existing parameter block.**

**Therefore: adding them to the audit set does NOT turn "fourteen into sixteen everywhere."** It
turns one of three sets from fourteen into sixteen and leaves the other two untouched — including
the one the ruling's most important watch item depends on.

## 1. The site that bites: the visual harness cannot see the promotion

`scripts/visual_regression.py` line 52:

```python
FIXTURES = FIXTURE_PARAMS          # the bench TEN
```

It hard-codes no count and enumerates no audit set — exactly the "does neither" case. So:

> **Watch item 1 requires looking at all sixteen renders. As things stand, promoting into the
> audit set gives A01 and A02 no render, no baseline, and no diff — and the noise-sewing check
> would be silently unsatisfiable on precisely the two inputs most likely to produce noise.**

This is not a small omission. The single-branch boundary is a **proxy, not a detector**; the only
thing standing between a noise sliver and a customer is a human looking at a render. Promoting
photographs into a set the render harness cannot see would remove that last check exactly where
it is needed most.

It is also **guarded against silent change**, which is correct and must be respected:
`tests/test_visual_regression.py::test_the_fixture_table_is_the_bench_table` asserts
`VR.FIXTURES is FIXTURE_PARAMS` — an *identity* assertion, deliberately anti-drift ("pictures and
numbers must describe the same run, so there is one table"). Extending visual regression to
sixteen therefore **requires knowingly changing that test**, which is the right cost: the
promotion must decide, out loud, whether the render table and the bench table are still the same
table. My recommendation is that they must not be forced apart silently — see §5.

## 2. Full enumeration, by class

### Class A — scale automatically (import `coverage_audit.fixtures()`)

| site | today | after | note |
| --- | --- | --- | --- |
| `test_stream_accounting.py` | **98 assertions** (7 identities × 14) | 7 × 16 = **112** | auto-scales — **but every new fixture must satisfy all seven.** Not a free pass: A02's phantom `COLOR_CHANGE` would fail `stops_partition_matches` **here**, which is the honest place for it to surface (watch item 3) |
| `test_corpus_baseline_fixtures.py::test_all_fourteen_fixtures_are_present` | 14 checked | 16 checked | auto-scales; **the function name and docstring become wrong** |
| `coverage_audit.py` `--json` / `--compare` | 14 rows | 16 rows | auto-scales, and now **records `fixture_set`** so the change is visible rather than inferred (landed `5eacdba`) |

### Class B — re-enumerate by hand; will NOT pick up the promotion

| site | mechanism | needs |
| --- | --- | --- |
| `scripts/trace.py::resolve()` | `if name in FIXTURE_PARAMS … elif name in CORPUS_EXTRA` | explicit A-tier branch, or it raises `unknown fixture` |
| `scripts/trace.py --all` | `list(FIXTURE_PARAMS) + list(CORPUS_EXTRA)` | **does not call `fixtures()`** — a second enumeration of the same set, the drift pattern this repo punishes. Should import `fixtures()` |
| `scripts/visual_regression.py` | `FIXTURES = FIXTURE_PARAMS` | §1 — the decision |

### Class C — keyed on the bench ten; unaffected, and correctly so

`run_quality_bench.py`, `measure_classification_width.py`, `measure_fabric_axis.py`,
`measure_stitch_quality.py`, `test_headline_numbers_are_labelled.py`. These measure *bench*
behaviour at *bench* conditions; a real photograph at a 360×350 hoop is not a bench fixture and
should not silently enter a bench table. **Unaffected is the right answer here** — but it must be
stated, not assumed, which is why they are listed.

`test_quality_bench.py::test_every_fixture_has_declared_params` globs `quality_bench/*.png` only,
so it is unaffected **unless** anyone copies the photographs into that directory — at which point
it would demand `FIXTURE_PARAMS` entries. That is a trap worth knowing about: **promotion must be
a table change, never a file copy.**

### Class D — hand-copied subsets (latent drift, found by this enumeration)

`tests/test_swarm_perf_lock.py::LOCK_FIXTURES` carries **params copied verbatim** from
`FIXTURE_PARAMS` for four fixtures, with a comment saying so. The promotion does not break it,
but it is the identical defect `visual_regression.py`'s own header warns about — *"IMPORTED, not
copied. A first draft retyped the fixture table and got four of the ten wrong within the hour."*
Reported, not fixed: no fix in this tranche.

### Class E — per-fixture baselines

| baseline | count | promotion effect |
| --- | ---: | --- |
| `tests/visual/baselines/*.png` | 10 | +2 needed **iff** §1 is decided for extension |
| `docs/benchmarks/v2-swarm/stitch-hashes.json` | 4 | unaffected (fixed subset) |
| `BASELINE_SHA256` (C-tier) | 4 | unaffected — its guard asserts `set(CORPUS_EXTRA) == set(BASELINE_SHA256)`, and A01/A02 would join a *new* list. **But that leaves two tracked real photographs unpinned**, which is precisely the argument that got the C-tier four pinned. They should be hashed. |
| `FIDELITY_BANDS` / `PARITY_BANDS` | 6 / 3 | unaffected — no band is added. **Finding, not a fix:** the rebuild round trip has never been measured on a photograph, so the promotion's first fidelity numbers on A01/A02 will be unbanded observations |

### Class F — prose that becomes false the moment the promotion lands

* `tests/fixtures/quality_bench/README.md` — the standing statement. Its "blind to" list names
  **photographs, dark garments, and `RUNNING_SINGLE`** as gaps; the promotion closes exactly
  those. **It must be rewritten in the promotion commit, not after** — a standing statement that
  is false is worse than none.
* `coverage_audit.py` docstring — "Fourteen fixtures, not ten".
* `generation.py:184` — *"14 refused regions across the fourteen fixtures, every one 0.20–0.23 mm"*
  — a **measured** claim in a shipped docstring; sixteen fixtures will change both numbers.
* `generation.py:222` — "a constant fitted to fourteen images".
* `test_running_entry_penetration.py`, `test_stream_accounting.py`, `test_rs1_hairline_runs.py`
  docstrings — each says "the fourteen".

## 3. What the enumeration found that the obvious list would not

Had I listed only the obvious sites, I would have reported: the accounting identities scale, the
presence test scales, rename some docstrings. All true, all harmless. The three findings that
matter came from asking which sites mention **neither** the count nor the set:

1. **`visual_regression.py` is blind to the promotion** — and it is the harness that caught the
   noise-sewing the numeric gates missed. Watch item 1 depends on a decision nobody had noticed
   needed making.
2. **`trace.py` enumerates the audit set a second time by hand**, so the repository's own
   provenance instrument would disagree with the audit about what "all fixtures" means.
3. **`LOCK_FIXTURES` is a verbatim copy** of a table whose own module warns against copying it.

## 4. Assertion arithmetic, stated so the after-count is checkable

| quantity | before | after (audit set only) |
| --- | ---: | ---: |
| accounting identities | 98 (7 × 14) | 112 (7 × 16) |
| presence checks | 14 | 16 |
| coverage-audit rows | 14 | 16 |
| visual baselines | 10 | 10, or 12 if §1 extends |
| stream locks | 4 | 4 |
| fidelity/parity bands | 9 | 9 |

## 5. The one decision the promotion cannot make silently

**Does the render table follow the audit table?** Three options, with what each costs:

| option | effect | cost |
| --- | --- | --- |
| **A. extend visual regression to the audit sixteen** | every promoted photo gets a render, a baseline and a diff; watch item 1 becomes satisfiable | must knowingly change the `VR.FIXTURES is FIXTURE_PARAMS` identity test; two large photo baselines committed |
| **B. leave it at the bench ten** | no change | **watch item 1 is unsatisfiable** — the promotion's most important check has no instrument |
| **C. a separate render pass for A-tier** | keeps bench identity intact, adds photo renders | two harnesses to keep honest; the drift risk this repo keeps paying for |

**Recommendation: A**, with the identity test rewritten to assert the render table *is* the audit
table rather than the bench table — one table, still, just the larger one. The reason is the
ruling's own: the boundary is a proxy, a human looking at a render is the only real check, and
promoting photographs into a set that produces no renders would remove that check exactly where
noise is most likely.

**I have not implemented any of this.** Enumeration reported before the promotion, as ruled; the
promotion follows once §5 is decided.

---

## 6. Closed — what the ruling of 2026-08-22 decided and what landed

Kept as an addendum rather than an edit, so the pre-promotion document still reads as it did
when it was written.

* **§5: Option A**, with the identity test rewritten to assert the render table *is* the audit
  table. Landed `9c55766`. Four C-tier baselines appeared for the first time, and C24's render
  made SH2's wholesale-deleted rectangle visible.
* **§2 Class B**: both `trace.py` sites now resolve through `fixtures()`; `LOCK_FIXTURES`
  imports its params. Landed `5f2cb3c`. The import immediately exposed a concealed contract
  mismatch (`KeyError: 'text'`) — the hand copy was not wrong in its values, it was *more
  explicit than its source*, which is why the defect had stayed invisible.
* **§2 Class E**: the `BASELINE_SHA256` prediction was correct. The guard asserted against
  `CORPUS_EXTRA` alone, so A01/A02 would have entered the standing set **unpinned**. Both are
  now hashed and the guard reads both corpus tiers.
* **§4 assertion arithmetic**: 112 accounting assertions (7 x 16), 16 presence checks, 16
  audit rows, 16 visual baselines. The "10, or 12 if §1 extends" line was superseded by
  Option A — it is 16, because the C-tier four gained baselines too.
* **§2 Class F**: every prose site named there was rewritten, and one of them — the census
  claim in `generation.py:184` — was **re-measured** rather than reworded, which is what found
  that its count was right and its verb was wrong.

The promotion itself, its parameters, and what it surfaced are in
`docs/CORPUS-PROMOTION-2026-08-22.md`.
