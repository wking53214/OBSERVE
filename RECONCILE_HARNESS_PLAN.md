# Plan: adopt the newer harness generation in OBSERVE's sentinel_os/ (option D)

Status: **PLAN ONLY.** Nothing in this plan has been executed. This file is the only change on this branch.
Date: 2026-10-30.
Reads with: `RECONCILE_UPSTREAM_PLAN.md` (the engine reconcile; separate work) and `VENDORED.md` / `UPSTREAM.md`.

## 0. Owner decisions this plan rests on

1. **Option D: adopt the newer harness generation as planned work.** OBSERVE's `sentinel_os/` harness, decider and the ledger stack
   they sit on are brought up to the upstream generation (GSA-815 plus the `sentinel_os` kernel).
2. **Option F (adopt `sentinel_os` as a submodule, as GSA-815 does) stays propose-only.** It deletes OBSERVE's copy. Nothing here does that.
3. **Option E is done** (PR #22: the harness hands the IVR cassette to the Twilio parser). Option D replaces `production_harness.py`
   wholesale, so E is superseded by D, not in conflict with it.
4. **Production use: none known** (the owner's earlier answer to the engine question, read as "none known", an assumption). See section 8
   for the one place this plan found that makes that assumption matter more: the worker and the API ingress run this harness.

## 1. Known, assumed, unknown

### Known (each was run or read on 2026-10-29 or 2026-10-30)

- **Baseline.** The `sentinel_os/` suite on main after PR #21: 1,027 tests collected; 922 pass, 6 skip, 79 fail, 20 error (99 bad). A local
  run on a real Redis and Postgres matched CI exactly.
- **The ancestor is on disk and settles "unique work" (section 2.1).** OBSERVE's `claude_governance_api.py` is **byte-identical** to
  `sentinel_os`'s `interpretation/claude_governance_api.py` at commits `587faf237` and `8f6d5f4d3` (2026-08-06). OBSERVE's `production_harness.py`
  at its initial commit is **byte-identical** to `interpretation/production_harness.py` at `8f6d5f4d3`. Since then OBSERVE changed the harness
  only by lint (unused imports, `f` prefixes, PR #18) and the decider not at all. The ancestor is in the object store of the submodule
  inside GSA-815 (`vendor/sentinel_os`). The standalone `sentinel_os` clone has no exact match, which is why an earlier look missed it.
- **No OBSERVE-authored lines in the closure.** Of the 20 files in the closure that differ from upstream, **every non-blank line of OBSERVE's
  copy exists in some historical upstream version** (0 lines found in no upstream version, over 5 to 73 historical versions per file).
  OBSERVE's copies are older upstream snapshots, not forks with their own work.
- **The closure** is 47 modules; 9 are already identical; 38 differ or are missing (+6,979 / -775 lines). Appendix A.
- **The upstream generation was built in GSA-815 over 2026-10-03 to 2026-10-29** (for example #14 credentials, #18 loop guard, #22 agent staffing
  removed and IVR sized with Erlang B, #26 IVR split behind a domain pack, #33 judged episode passed to the ledger, #36 ledger attestation key).
- **Why the mixed tree fails today.** `twilio_log_ingestion.py` (newer) requires a cassette; the old harness built the parser without one.
  PR #22 fixed that one call; 97 failures remain because the tests describe the new generation.
- **A scratch overlay of the whole closure** (in `/tmp`, deleted) was run against the full suite. Results are in section 3.
- **The runtime services use this harness.** `sentinel_worker.py` builds `IcebergProductionHarness(_harness_config_from_env())`;
  `resilient_harness.py` wraps it; `api_server_v2.py` is the ingress next to it.

### Assumed

- No production system depends on OBSERVE's `sentinel_os/` runtime (owner: "none known").
- The upstream generation's behaviour is what the owner wants. The tests that describe it (`Tests/test_governor_failclosed.py`,
  `Tests/test_live_path_kernel_wiring.py`, `Tests/test_phase2_limitations.py`, and others) are already in OBSERVE and are currently red.
- A line that exists somewhere in upstream history is not OBSERVE's work. This test would miss an OBSERVE edit that only reorders or reuses
  existing lines. It would not miss a new line, and none exist.

### Unknown

- **Why about 12 of the 38 remaining failures expect ledger rows that are not there** (section 3.6). Not established.
- Whether the worker and ingress are deployed anywhere, and with which environment (the new harness and ledger fail closed at start without
  a ledger, a non-owner runtime role and an attestation key).
- Whether the upstream generation passes OBSERVE's remaining suite once the test alignment in section 3 is done. Measured as far as the
  overlay went (section 3.5); not run as one landed change.

A missing record is a lead, not proof of absence.

## 2. The module closure

### 2.1 The "unique OBSERVE work" finding, in plain words

The same bytes as OBSERVE's decider (and, at OBSERVE's initial commit, its harness) appear upstream in the kernel's history in commits dated
**2026-08-06** (`587faf237` and `8f6d5f4d3`, "Interpretation framework: F1+F3 reframe for regulatory drift", under `interpretation/`). OBSERVE's
own history starts 2026-07-31, five days earlier, and `GSA-815` starts 2026-08-17 and the standalone `sentinel_os` repository 2026-09-03. So the
two copies share an earlier origin that is not recorded on disk, and which side copied from which is **not established**. What is established is
that the bytes are the same and that upstream has since moved and rebuilt both files while OBSERVE kept the originals. The "Gate 1 / Gate 2
fail-closed" design in them is the early form of the fail-closed design upstream still has.
(An earlier note counted 62 harness lines and 174 decider lines that "match no upstream version". That count used only part of the upstream
history; with the full history it is zero.)

What this does **not** prove: that the old and new generations behave the same. They do not (section 3). It proves OBSERVE has no work of its own
in these files to lose.

### 2.2 The closure, file by file

Appendix A lists all 38. Summary by slice (the PRs are defined in section 4):

| PR | What | Files | Change |
|---|---|---|---|
| H1 | Libraries and cassettes (schema, capabilities, forensics, interface, regulatory, outcome, event, canonical fields, twin custody, banking and mortgage cassettes) | 13 | +994 / -100 |
| H1 | Ledger, conservation boundary and the leaf governance modules the libraries import (`governance/ledger_postgres.py` +1,531, `governance/authorized_by_attestation.py`, `governance/human_selection_v1.py`, `conservation/**`, `epistemic/dit_gate.py`) | 14 | +4,111 / -45 |
| H2 | Harness stack (`production_harness`, `governed_pipeline`, `ivr_pack`, `domain_pack`, `claude_governance_api`, `governance_decider`, `governance_loop_guard`, `twilio_log_ingestion`, `queue_staffing_bayes_integration`, `sentinel_core`, `observe_perceive_core`) | 11 | +1,874 / -630 |

H1 is 27 files, +5,105 / -145, because the libraries and the ledger must land together (section 4).

Also needed for the test alignment: the kernel's `interpretation/` package (8 files, 2,111 lines), which the updated mortgage test imports.
It is a test dependency, not a runtime one for the harness.

**Dynamic loading hid part of the closure.** `CassetteLoader` loads cassettes by name, so a static import search missed
`cassettes/mortgage_cassette.py` (403 lines in OBSERVE, 502 upstream, 0 OBSERVE-only lines) and `cassettes/banking_cassette.py`. They are in the table.

## 3. What breaks when the closure is adopted (the 63, then what is left)

The overlay (the whole closure from GSA-815 `4239ae1` and the kernel commit GSA-815 itself records, `51f0e09`, with the ledger attestation
key set) gave: 103 failed, 914 passed, 0 errors, against the baseline 99 bad. Compared test by test: **59 fixed, 40 still failing,
63 new failures.** `Tests/test_queue_staffing_bayes.py` (4 tests) could not be collected and was set aside (section 3.4).

Every one of the 63 new failures has a cause. Re-run in isolation (they reproduce in about ten seconds), they group into three causes. A fourth row below is a side effect that is not among the 63:

| Cause | Tests | What it is | Fix | Who decides |
|---|---|---|---|---|
| 3.1 The ledger now refuses a decision with no judged episode | 48 | `ValueError: Governance decision rejected: no episode was supplied ... the boundary is mandatory at the ledger`. Setting the waiver below, on the 63 alone, cleared exactly 48 of them. | Tests copied from the kernel call `ledger.append` directly. The kernel's own `conftest.py` waives the boundary for its test suite with `os.environ.setdefault("ICEBERG_LEDGER_CONSERVATION_DEV_OVERRIDE", "1")` (a documented development-only setting). Do the same in OBSERVE's `sentinel_os/conftest.py`, **and carry the kernel's `Tests/test_ledger_conservation_boundary.py`** (OBSERVE does not have it) so the boundary itself stays tested. | Owner (section 7, Q2) |
| 3.2 The newer cassette schema rejects OBSERVE's mortgage cassette | 11 | `cassette declares outcome_obligation but does not enable 'interpretation_testable'` | Not new domain work: upstream's `mortgage_cassette.py` already enables it and implements `resolve_scenario` (version 1.0.1). Re-sync the cassette (OBSERVE-only lines: 0). The 3 OBSERVE tests that pin the old version and capability list must follow upstream's updated test file (rule-5 edit, section 4). | Owner confirms (Q3) |
| 3.3 The harness requires a ledger to bind its cassette by default | 4 | `RuntimeError: require_cassette_binding=True but no postgres_host configured` | All 4 are in `test_governor_failclosed_root.py`, an OBSERVE-only older copy of the fail-closed tests. Its upstream equivalent, `Tests/test_governor_failclosed.py`, is already in OBSERVE and passes on the overlay (4 fixed). Passing `require_cassette_binding=False` in the old copy's `_harness()` clears these 4 but then 3 of its assertions fail, because they assert the old result keys (`governance_approved is True`). **Propose retiring (archiving, not deleting) the old copy** in favour of the upstream one. | Owner (Q4) |
| 3.4 (side, not among the 63) The removed agent-staffing classes | 4 (not collected) | `ImportError: cannot import name 'QueueState'` | Removed upstream in GSA-815 #22 (2026-10-11, "Size IVR lines with Erlang B; remove agent staffing"). Users in OBSERVE: `Tests/test_queue_staffing_bayes.py` (4 tests), `Tests/conftest.py` (a loader entry), `Domain/QueueState.py`, `Domain/README.md`. **These 4 tests pass today and would be lost.** Options: port them to the Erlang B sizing upstream now has, or retire with an archive. Propose only. | Owner (Q5) |

The 63 are 48 + 11 + 4: what the waiver cleared (48) and what was left after it (the 11 mortgage tests and the 4 in the old fail-closed copy).
Grouping by each test's first error message alone paired 61 of the 63 (44 the episode rule, 2 a reworded form of it, 11 mortgage, 4 binding);
the other 2 of the 48 first reported the cassette-binding error and also clear once the waiver is set. Why the waiver clears those 2 was not
traced.

**The key.** The ledger refuses to start without `ICEBERG_LEDGER_ATTESTATION_KEY` (or `_KEY_FILE`) and has no default
(`governance/authorized_by_attestation.py`). Without it the overlay gave 114 failed and 61 errors (measured by the earlier read-only analysis, not re-run here). GSA-815's conftest generates a fresh random key
per test session (`secrets.token_hex(32)`) unless one is configured; the kernel's conftest uses a fixed string that says it is not a secret.
**Recommendation: GSA-815's way**, so nothing is hard-coded.

**The runtime role.** The ledger also refuses to start unless `ICEBERG_LEDGER_RUNTIME_USER` names a non-owner, non-superuser role. OBSERVE's
conftest already sets `ledger_reader` as a default, as GSA-815's does, so no change is needed there.

### 3.5 After every fix identified above (full suite on the overlay)

With the key, the conservation waiver, upstream's mortgage cassette and (in the scratch copy only) `require_cassette_binding=False` in the old
fail-closed copy: **44 failed, 973 passed, 6 skipped** (the 4 staffing tests set aside), against the baseline's 99 bad and 922 passed.
Compared test by test: **61 of the 99 fixed, 38 still failing, 6 new.** The 6 new are the 3 mortgage tests that pin the old cassette (cleared by
upstream's updated test file, which passed 59 of 59 with the cassette and the `interpretation/` package) and the 3 old-fail-closed assertions
above (3.3). Not run together as one landed change, so the exact final count is **expected, not measured**: about 38 failing.

### 3.6 The 38 that are still failing (they were failing before; the overlay does not fix them)

Re-run in isolation, 7 of the 38 pass (the `test_api_server_v2.py::test_L*` trajectories: they depend on suite state or order), and 31 fail:

| Group | Tests | What the failure says | Established? |
|---|---|---|---|
| Ledger rows that the test expects are not there | about 12 | `IndexError: list index out of range`, `assert 0 == 1`, `governed call must produce a decision row`, `primary ledger unexpectedly empty`, `assert 0 == 25` | **No.** Mostly in OBSERVE-only test files (`Tests/test_cassette_governs_every_decision.py`, `Tests/test_ai_cost_end_to_end.py`) written for the old recording behaviour, plus the twin and worker tests that read the ledger. This is the largest unexplained group. |
| Worker and queue | 8 | `Outcome.SCHEDULED is Outcome.OK`, `pending == done`, `dead == done` | No. `queue_schema.py` was re-synced in PR #21; the worker and the harness around it may disagree. |
| Twin live | 2 to 3 | `401 Unauthorized` | No. Probably CI identity setup. |
| Ingress import test (`test_T10`) | 2 | the ingress imports modules it must not (`sentinel_core`, `governance...`) | No. Order-dependent in the full run. |
| Harness circuit breakers | 3 | breaker independence assertions | No. Upstream has the breaker design; the test is `test_production_harness_breakers.py`, which has an upstream counterpart in GSA-815. |
| Rate limiter | 3 | `got 15` successes where 5 were expected | No. Independent of the harness; present in the baseline. |

## 4. The sequence of small pull requests

Every PR is built on a branch, has one commit per step, and lists its rule-5 test edits. **Measured, not guessed, where marked.**

**What the slice experiments showed (each on a fresh copy of OBSERVE):**

| Experiment | Result | Meaning |
|---|---|---|
| Libraries and leaf governance modules, without the ledger | 108 failed, 903 passed; **29 new failures** (hash, twin and chain verification) | The library slice and the ledger slice must land **together**. The libraries change the hash and twin format and the old ledger cannot match it. |
| Libraries, leaf modules and ledger stack, without the harness (key and waiver set) | 80 failed, 931 passed, 20 errors against 79 / 922 / 20; **0 fixed, 1 new** | Safe to land alone. The one new failure is a test pinning the banking cassette version (`2.0.3` against upstream `2.0.4`): a one-line rule-5 edit. The 9 extra passes fit the larger updated mortgage test file; they were not itemized. |
| The whole closure plus the identified fixes | 44 failed, 973 passed (section 3.5) | The harness slice is where the 61 get fixed. |

| PR | What | Size | Risk | CI state expected after | Rollback |
|---|---|---|---|---|---|
| **H1** | Libraries, leaf modules, ledger and conservation stack (27 modules); `sentinel_os/conftest.py` (random per-session attestation key, conservation waiver for tests, as the kernel does); the kernel's `Tests/test_ledger_conservation_boundary.py`; upstream's updated `Tests/test_mortgage_cassette.py` and the `interpretation/` package it imports; the banking version pin (rule-5 edit, one line) | +5,105 / -145, plus 2,111 for `interpretation/` | **Medium.** It changes the ledger. It looks safe in CI terms (measured) but the worker and ingress run on this ledger. | Same red as today. The overlay measured **100 bad** (80 failed, 20 errors) against the baseline 99, the one extra being the banking version pin; **99 expected** after the one-line pin edit (inferred, not run). | revert the merge commit |
| **H2** | Harness stack (11 modules) | about +1,900 / -630 | **Highest.** Changes the runtime construction (section 8). The suite needs Redis, Postgres and the twin identities; validated locally on this machine's real services and then in CI. | About **38 failing** (expected, not measured as one landed change); the 4 staffing tests need a decision first (Q5); the old fail-closed copy retired (Q4) | revert the merge commit |
| **H3a** | Test alignment: the OBSERVE-only test files that describe the old generation (`Tests/test_cassette_governs_every_decision.py`, `Tests/test_ai_cost_end_to_end.py`, `test_production_harness_breakers.py`, `test_governor_failclosed_root.py` retire-or-port) | depends on Q4 and the unexplained group | Medium | fewer failures; unknown until the unexplained group is understood | revert |
| **H3b** | Worker, queue and API end to end (8 + 2 + 7 order-dependent) | unknown | Medium | unknown | revert |
| **H3c** | Independent items: rate limiter (3), twin 401 (2 to 3) | small each | Low | -5 to -6 | revert |

**Order.** H1, then H2, then H3a to H3c in any order. H1 first because it is measured safe and moves nothing visible.

## 5. Differential and regression strategy

1. **Before H1:** run the suite on main and save the failing set (this plan's baseline is the CI log of run 40943161425, 99 bad).
2. **After each PR:** compare test by test with the previous failing set (not just totals). Required result: no test that passed before fails now,
   unless it is listed as a rule-5 edit. This is the comparison used in this plan (it caught the 1 and the 6 above).
3. **For H2 specifically:** the old and the new harness should be compared on the same recorded calls. OBSERVE's fixtures already contain call
   records; run each through both harnesses (the old one from git history, the new one on the overlay) and compare the decision, the blocked flag
   and the ledger row. Expected differences are the documented ones: the new harness records every judged decision, requires a ledger by default,
   and makes the kernel judgment mandatory. Anything else is a finding.
4. **Keep the boundary tested** while the conftest waives it for kernel-copied tests: the kernel's boundary test clears the waiver for itself.

## 6. How this interacts with the open engine reconcile plan

- **No file overlap.** `RECONCILE_UPSTREAM_PLAN.md` PR-3 re-syncs observe-perceive-derived files (`observe_consolidated`, `perceive_consolidated`,
  `clinical_governance_system`, `kalman_trajectory`, `governance_contracts`, `compliance_exporters`, `cassette.py`, `pediatric_cassette.py`).
  None is in this closure. `observe_perceive_core.py` (in this closure) is a different file from `observe_consolidated.py`.
- **Shared files:** `VENDORED.md`, `UPSTREAM.md`, `CHANGELOG` (if any). Merge conflicts there are trivial; update rows after each PR.
- **Order.** Independent. Recommendation: do H1 and H2 first. H2 takes the `sentinel_os/` suite from 99 bad to about 38, so PR-3's CI result is
  readable. If PR-3 lands first, its CI result will include these 99 unrelated failures and be harder to judge.
- **PR #22** (E) changes the same lines as H2 replaces; if it merges first, H2 simply overwrites the file.

## 7. Open questions for the owner (each with options and a recommendation)

1. **Q1. Do H1 and H2 first, then the engine PR-3? (order)** A. Yes (recommended: it makes PR-3's CI readable). B. Engine first. C. Interleave.
2. **Q2. The conservation boundary in the test suite.** The ledger now requires a judged episode and the kernel waives it for its own tests.
   A. Waive it in `conftest.py` as the kernel does, and carry the kernel's boundary test so it stays proven (recommended: keeps kernel-copied
   tests identical to upstream). B. Rewrite the 44 tests to supply episodes (diverges them from upstream). C. Waive only in kernel-copied tests.
3. **Q3. The mortgage cassette.** It is a re-sync (0 OBSERVE-only lines). A. Re-sync and take upstream's updated test file (recommended).
   B. Keep the old cassette and drop the capability (loses the outcome obligation, and the schema will not allow it).
4. **Q4. `test_governor_failclosed_root.py`.** It asserts the old result shape and is superseded by `Tests/test_governor_failclosed.py`.
   A. Retire it by archiving, not deleting (recommended). B. Port its assertions to the new result keys. C. Keep, fix per test.
5. **Q5. The agent-staffing tests (4, plus `Domain/QueueState.py`).** Upstream removed agent staffing in #22 and sizes IVR lines with Erlang B.
   A. Archive the 4 tests and the domain file (propose only; recommended if OBSERVE has no use for staffing). B. Port the 4 tests to the
   Erlang B sizing. C. Keep the old module alongside the new harness (fights the new `queue_staffing_bayes_integration.py`).
6. **Q6. The attestation key in CI.** A. A random per-session key set in `conftest.py`, as GSA-815 does (recommended; nothing hard-coded).
   B. A fixed test string, as the kernel does. C. A CI secret.
7. **Q7. Deployment.** Does anything deploy the worker or the ingress from this tree? If yes the new harness needs a ledger, a non-owner role
   and an attestation key at start, and the deployment files (`Deploy/`, `k8s/`, compose) need them. Unknown. A. Confirm none are deployed
   (recommended to ask first). B. Update the manifests in H2.
8. **Q8. The unexplained 12 (ledger rows expected but absent).** A. A read-only investigation before H3a (recommended). B. Defer.

## 8. What this plan could not determine

- **The 38 failures that remain**: the largest group (about 12 tests expecting ledger rows) has no established cause. The worker and queue group (8)
  may be a mismatch between OBSERVE's `sentinel_worker.py` and the re-synced `queue_schema.py`, or the harness; not established.
- **Whether the landed change behaves like the overlay.** The overlay copied files into a scratch tree. A real PR also edits conftest, tests and
  documents. The expected numbers in section 4 for H2 and after are expectations.
- **Behavioural equivalence** of the old and new harness on real calls (section 5, item 3, is proposed, not done).
- **Deployment impact.** `sentinel_worker.py` builds the harness from environment variables (`POSTGRES_HOST` defaults to `localhost`). The new
  constructor fails closed at start when the cassette cannot be bound to a ledger, and the ledger fails closed without an attestation key and a
  non-owner role. For a deployed worker that is a change from "starts and runs without a ledger" to "refuses to start". The direction is the
  fail-loud one the stack wants; it is still a change someone running this must be told about.
- **Line-level versus meaning.** "No OBSERVE-only lines" is a line check across history (section 1, Assumed).
- Whether the older Graveyard copy of the harness is related: it is not (a 78-line unrelated fragment).

## Appendix A: the closure, file by file

OBSERVE's copy against upstream (GSA-815 `4239ae1` for files that live in GSA-815; the kernel at the commit GSA-815 records, `51f0e09`, for the
rest). "OBSERVE-only lines" counts the non-blank lines of OBSERVE's copy that appear in no historical upstream version of the same file.
Nine more files in the closure are identical and omitted: `ai_cost_tracking.py`, `cassette_loader.py`, `cassettes/ivr_cassette.py`,
`circuit_breaker.py`, `episode.py`, `governance/friction_core.py`, `metrics_prometheus.py`, `operational_resilience.py`, `tracing.py`.

| File | Upstream | Status | Upstream lines | Change (+/-) | PR | OBSERVE-only lines |
|---|---|---|---|---|---|---|
| `canonical_fields.py` | sentinel_os | stale | 285 | +184 / -2 | H1 | 0 |
| `cassette_capabilities.py` | sentinel_os | stale | 322 | +58 / -2 | H1 | 0 |
| `cassette_forensics.py` | sentinel_os | stale | 273 | +19 / -0 | H1 | 0 |
| `cassette_interface.py` | sentinel_os | stale | 180 | +14 / -0 | H1 | 0 |
| `cassette_schema.py` | sentinel_os | stale | 469 | +50 / -1 | H1 | 0 |
| `cassettes/banking_cassette.py` | sentinel_os | stale | 458 | +1 / -1 | H1 | 0 |
| `cassettes/mortgage_cassette.py` | sentinel_os | stale | 502 | +154 / -55 | H1 | 0 |
| `conservation/boundary.py` | sentinel_os | missing in OBSERVE | 59 | +59 / -0 | H1 | n/a (absent) |
| `conservation/episode_source.py` | sentinel_os | missing in OBSERVE | 178 | +178 / -0 | H1 | n/a (absent) |
| `conservation/judgment.py` | sentinel_os | missing in OBSERVE | 98 | +98 / -0 | H1 | n/a (absent) |
| `conservation/transport/__init__.py` | sentinel_os | missing in OBSERVE | 52 | +52 / -0 | H1 | n/a (absent) |
| `conservation/transport/artifact.py` | sentinel_os | missing in OBSERVE | 125 | +125 / -0 | H1 | n/a (absent) |
| `conservation/transport/builder.py` | sentinel_os | missing in OBSERVE | 200 | +200 / -0 | H1 | n/a (absent) |
| `conservation/transport/contracts.py` | sentinel_os | missing in OBSERVE | 352 | +352 / -0 | H1 | n/a (absent) |
| `conservation/transport/errors.py` | sentinel_os | missing in OBSERVE | 31 | +31 / -0 | H1 | n/a (absent) |
| `conservation/transport/registry.py` | sentinel_os | missing in OBSERVE | 167 | +167 / -0 | H1 | n/a (absent) |
| `conservation/transport/transport.py` | sentinel_os | missing in OBSERVE | 329 | +329 / -0 | H1 | n/a (absent) |
| `epistemic/dit_gate.py` | sentinel_os | missing in OBSERVE | 265 | +265 / -0 | H1 | n/a (absent) |
| `event_v1.py` | sentinel_os | stale | 404 | +56 / -2 | H1 | 0 |
| `governance/authorized_by_attestation.py` | sentinel_os | missing in OBSERVE | 662 | +662 / -0 | H1 | n/a (absent) |
| `governance/human_selection_v1.py` | sentinel_os | missing in OBSERVE | 62 | +62 / -0 | H1 | n/a (absent) |
| `governance/ledger_postgres.py` | sentinel_os | stale | 3649 | +1531 / -45 | H1 | 0 |
| `governor_injection_defense.py` | sentinel_os | stale | 118 | +4 / -1 | H1 | 0 |
| `outcome_v1.py` | sentinel_os | stale | 548 | +34 / -16 | H1 | 0 |
| `regulatory_cassette_interface.py` | sentinel_os | stale | 538 | +23 / -4 | H1 | 0 |
| `regulatory_checks.py` | sentinel_os | stale | 1588 | +12 / -5 | H1 | 0 |
| `twin_custody.py` | sentinel_os | stale | 782 | +385 / -11 | H1 | 0 |
| `claude_governance_api.py` | GSA-815 | stale | 307 | +268 / -254 | H2 | 0 |
| `domain_pack.py` | GSA-815 | missing in OBSERVE | 154 | +154 / -0 | H2 | n/a (absent) |
| `governance_decider.py` | sentinel_os | missing in OBSERVE | 240 | +240 / -0 | H2 | n/a (absent) |
| `governance_loop_guard.py` | sentinel_os | missing in OBSERVE | 138 | +138 / -0 | H2 | n/a (absent) |
| `governed_pipeline.py` | GSA-815 | missing in OBSERVE | 575 | +575 / -0 | H2 | n/a (absent) |
| `ivr_pack.py` | GSA-815 | missing in OBSERVE | 374 | +374 / -0 | H2 | n/a (absent) |
| `observe_perceive_core.py` | GSA-815 | stale | 196 | +6 / -33 | H2 | 0 |
| `production_harness.py` | GSA-815 | stale | 197 | +67 / -204 | H2 | 0 |
| `queue_staffing_bayes_integration.py` | GSA-815 | stale | 256 | +40 / -133 | H2 | 0 |
| `sentinel_core.py` | GSA-815 | stale | 306 | +1 / -1 | H2 | 0 |
| `twilio_log_ingestion.py` | GSA-815 | stale | 502 | +11 / -5 | H2 | 0 |
