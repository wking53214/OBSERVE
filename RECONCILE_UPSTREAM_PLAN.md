# Plan: reconcile OBSERVE's engine with observe-perceive (option C, upstream first)

Status: **PLAN ONLY.** Nothing here has been executed. The only change made so far is the stopgap on this branch
(`test_observe_invariants.py::VendoredCopyStaysInSync` and the pin in `VENDORED.md`). observe-perceive was read, never edited.
Date: 2026-10-29.

## 0. Owner decisions this plan rests on

1. **Fingerprint design: upstream wins.** observe-perceive's `decision_fingerprint` and `verdict_state` are the design to keep.
   OBSERVE's `compute_decision_fingerprint` is retired in favour of them.
2. **Do option C (reconcile upstream first), scoped as a proper piece of work, with option D (the pinned-snapshot test) as a temporary measure.**
   The owner approved editing the sync test for the stopgap. That approval covers that one test, for the stopgap only.
3. **Production use: the owner answered "No" to knowing of anything in production that imports either copy.**
   This plan treats that as **none known**. That is an **assumption**, not confirmed absence.

## 1. Known, assumed, unknown

### Known (each was run or read on 2026-10-29)

- The two copies were byte-identical at commit `4fc3df6`. Commit `c0dbef8` (2026-09-08) overwrote `sentinel_os/observe_consolidated.py`
  with observe-perceive `717c2e2`, so they have differed since then. The old identical-assertion has been red since that date.
- `sentinel_os/observe_consolidated.py` is byte-identical to observe-perceive `717c2e2` (sha256 `66feebf5...b53c`, pinned in `VENDORED.md`).
- The root `observe_consolidated.py` is OBSERVE's own evolved engine. Since the common base it gained 26 lines and lost 4 (PR #19's LRU
  eviction fix with the `STATE_EVICTED` ledger entry). The vendored snapshot changed by +244 and -346 lines (upstream's engine).
- observe-perceive's engine has changed in 4 commits since `717c2e2`: #11 (TIE and GEMS), #26 (the cassette seam), #29 (parameter-set version
  and per-subject state commitments, ported from OBSERVE) and #53 (physician approval for emergency override, and an LRU eviction fix equal in
  intent to OBSERVE's #19).
- Dry runs in throwaway copies: copying root over the vendored copy breaks 3 tests in the `sentinel_os/` suite and drops `sanitize_context`.
  Copying the vendored copy over root makes the root suite fail at import (`ModuleNotFoundError: kalman_trajectory`).
- The stack already converged on upstream's fingerprint algorithm: `interconnected_beta/beta/fingerprint.py` says it was "extracted verbatim"
  from observe_consolidated and is identical (`sha256(json.dumps(data, sort_keys=True, default=str))`). OBSERVE's own
  `observe_clinical_risk_adapter.py` uses the same expression. **OBSERVE's `compute_decision_fingerprint` is the odd one out.**
- There are **no hard-coded digests** in OBSERVE's root tests, docs or JSON (a search for 64-character hex strings outside `sentinel_os/` found none).
  Every fingerprint and commitment value is computed at run time and compared relatively.

### Assumed

- No production system imports either copy or reads their audit entries (owner: "No", read as "none known").
- No persisted ledger or audit store contains OBSERVE-style fingerprints that must stay verifiable. If one exists, section 6.4 applies.
- observe-perceive's cassette binding (cassette name and version are in the fingerprinted payload) gives the same protection against
  silent threshold changes that OBSERVE got from putting two thresholds in `PARAMETER_SET`.
- The 600-reading corpus in section 7 is representative enough to find a gross behaviour difference. It is not a clinical validation.

### Unknown

- Whether anything outside the repositories under `/home/user` reads these audit entries.
- Whether clinicians or the owner accept upstream's scoring changes (section 5.5). That is a clinical decision, not a code one.
- Whether the sentinel_os suite stays green after the re-sync in PR-3. It needs Redis and Postgres and could not be run locally.
- Whether an equivalent of OBSERVE's `test_decision_fingerprint_is_persisted_on_verdict_and_in_audit` exists upstream under another name
  (upstream has 51 invariant tests against OBSERVE's 44, and only that one test name is absent; its intent looks covered, not verified line by line).

A missing record is a lead, not proof of absence.

## 2. What the two engines are

| | OBSERVE root `observe_consolidated.py` | observe-perceive `observe_consolidated.py` |
|---|---|---|
| Lines | 1,531 | 1,670 |
| Parameter set | `PARAMETER_SET` with 12 keys, version `906c4a26...` | `PARAMETER_SET` with 11 keys, version `5808ba2f...` |
| Fingerprint | `compute_decision_fingerprint(vitals, verdict)` | `decision_fingerprint(decision_data)` |
| State commitment | its own `compute_state_commitment(payload, predecessor_state_commitment, scope)` | `governance_contracts.compute_state_commitment(parent_commitment, state)` over `verdict_state(subject, fingerprint)` |
| Context handling | none: a non-numeric context value raises `TypeError` | `sanitize_context` drops bad values and records notes |
| Domain knowledge | in the engine (constants and thresholds inline) | in a cassette (`cassette.py`, `pediatric_cassette.py`) |
| Local modules needed | none | `cassette`, `pediatric_cassette`, `kalman_trajectory`, `governance_contracts` (about 900 lines in four files) |

## 3. Inventory of consumers (searched across every repository under `/home/user`)

Searched names: `compute_decision_fingerprint`, `compute_state_commitment`, `_normalize_commitment_value`, `_canonical_json`,
`REGIME_DISTRIBUTION_BANDS`, `HEAVY_PATH_ENTROPY_TRIGGER`, `HEURISTIC_HARD_RULE_THRESHOLD`, `_CHANNEL_CONTEXT_KEYS`, `_VITALS_NEUTRAL`,
`PARAMETER_SET`, `PARAMETER_SET_VERSION`, `predecessor_state_commitment`, `decision_fingerprint`, `verdict_state`, and imports of `observe_consolidated`.
Archive repositories (`*_History`, `Graveyard`, `WhitePapers`, `Ecology/corpus`) contain text mentions only and are not consumers.

### 3.1 In OBSERVE (the repository that changes)

| File | Uses | Affected by the switch |
|---|---|---|
| `observe_consolidated.py` | defines all of the retired names | replaced |
| `test_observe_invariants.py` | imports 23 names from the engine; 44 mentions | **yes: 8 tests fail** (section 5.4) |
| `test_observe_consolidated.py`, `test_observe_clinical_risk_adapter.py` | engine API only | no: 78 tests pass unchanged against the upstream engine |
| `cns_connector.py` | `FusedVerdict`, `VitalsSnapshot`, `validate_vitals`; `decision_fingerprint` as an opaque string in `observe:omega:<fingerprint>` | no code change; its 10 tests pass against the upstream engine |
| `clinical_capacity_orchestration_source.py` | `ObserveClinicalEngine`, `VitalsSnapshot`, `FusedVerdict`, `OperationalRegime` | no |
| `observe_clinical_risk_adapter.py` | its **own** third hash, `decision_hash` over regime, escalation and entropy | not affected; see open question 6 |
| `docs/CLINICAL_SCORING.md` | names the retired constants and cites engine line numbers (lines 183, 205, 206, 465, 524, 561) | **yes: text and line references** |
| `docs/CHANGELOG.md`, `RESILIENCE_INTEGRATION_ASSESSMENT.md` | history that names `compute_decision_fingerprint` | add a note; do not rewrite history |
| `README.md` line 69 | describes the verdict fields | check wording |
| `.ghost_baseline.json` | a generated findings baseline that lists `_normalize_commitment_value` and others | **regenerate** with the ghost tool |
| `sentinel_os/` | its own copy of the upstream engine, `governance_contracts.py` and PERCEIVE | PR-3 |

### 3.2 In other repositories

| Repository | Finding | Affected |
|---|---|---|
| `observe-perceive` | the upstream; defines the design that stays | not edited by this plan |
| `interconnected_alpha`, `interconnected_zeta` | docstrings and comments cite `observe_consolidated.py` **line ranges** as the provenance of what they extracted (for example "observe_consolidated.py:113-119"); no code imports it | no code change; those line citations point at the older revision they were extracted from and will not match the new engine. They are history, not links |
| `interconnected_beta` | `beta/fingerprint.py` is the upstream algorithm, verbatim; `beta/verdict.py` cites `observe_consolidated.py:90-94` in a comment | no (already aligned) |
| `interconnected_delta`, `Reporting` | `decision_fingerprint` is an opaque string field on delta's own `Decision` and `Obligation` types (Reporting's COMPAS tests read it from those types); delta's tests use placeholders such as `"fp-1"` and `"0"*64` | no |
| `GSA-815` | imports `observe_perceive_core`, a different module; 0 matches for any of the searched names in `.py` files | no |
| `fortress-kernel` | its own `_canonical_json` in `fortress_unified.py`; unrelated implementation | no |
| `DGK`, `ASSAY`, `DIT`, `CNS`, `URE`, `ATS` | 0 matches in `.py` files (a few text mentions in Markdown or JSON only) | no |

**Result:** the only real code consumers of the retired functions are OBSERVE's engine, its invariants test, and its documentation.

## 4. Field-by-field mapping

### 4.1 Decision fingerprint

| | OBSERVE `compute_decision_fingerprint` | Upstream `decision_fingerprint(decision_data)` | Change |
|---|---|---|---|
| Serialization | `json.dumps(sort_keys=True, separators=(",", ":"), default=str)` (compact) | `json.dumps(sort_keys=True, default=str)` (default separators) | **different bytes for the same data** |
| Hash | SHA-256 | SHA-256 | same |
| `vitals` | `asdict(vitals)` | `asdict(recorded vitals)`; when a channel is faulted, `assessed_vitals` is also recorded | upstream records more when faulted |
| `risk_score`, `entropy` | **rounded to 9 decimals** | exact (not rounded) | **lost: rounding**; open question 2 |
| `regime`, `escalation_required` | top level | inside `verdict` | moved |
| `triggered_rules` | sorted list of all rules, including the fault and bypass notes | not included directly; each engine's own rules are inside `outputs` | **bypass note no longer in the fingerprint** |
| `validation_faults`, `unassessable` | always present | present only when faulted (a clean entry keeps its shape) | shape change |
| `parameter_set_version` | present | present | value differs (section 2) |
| `selected_engines`, per-engine `outputs` (engine, risk, confidence, rules) | not included | **included** | **gained** |
| Cassette identity (name, version) | none | **included** | **gained** |

### 4.2 State commitment

| | OBSERVE | Upstream | Change |
|---|---|---|---|
| Function | `compute_state_commitment(payload, predecessor_state_commitment="", scope="clinical_state")` | `compute_state_commitment(parent_commitment, state)` | different name for the chain argument, no `scope`; **positional order differs** |
| What is committed | patient id, timestamp, fingerprint, risk, regime, confidence, entropy, version, faults, unassessable, selected engines | `{"subject", "decision_fingerprint"}` only | upstream commits less directly and relies on the fingerprint covering the rest |
| Scope string | `"clinical_verdict"` | none | lost |
| Canonical form | `_normalize_commitment_value` maps NaN to `"__nan__"`, infinity to `"__inf__"`, datetimes to UTC ISO text | `_canonicalize_commitment_value` passes floats through (NaN and infinity become JSON tokens) and turns datetimes into `str(value)` | differs; **moot today**, because the upstream state holds only two strings |
| Chain | per patient, head kept in the engine | per subject, head kept in the engine under a lock | same idea; upstream is thread-safe |
| Eviction | head popped when a patient is evicted | head popped when a subject is evicted | same |

### 4.3 Parameter set

| Key | OBSERVE | Upstream |
|---|---|---|
| `heavy_path_entropy_trigger` (0.6) | in `PARAMETER_SET` | **not in it**; the literal 0.6 lives in `pediatric_cassette.select_engines` |
| `heuristic_hard_rule_threshold` (0.5) | in `PARAMETER_SET` | **not in it**; it is `HARD_RULE_RISK = 0.5` in the cassette |
| `unassessable_confidence_penalty` | not in it | in it |
| `_VITALS_NEUTRAL`, `_CHANNEL_CONTEXT_KEYS` | in the engine | moved to `pediatric_cassette.py` |
| `schema` label | `observe.parameters/v1` | `observe.parameters/v1` (**same label, different content**) |

The values are equal where both define them. What changes is where they live and whether they are inside the version hash.

## 5. What changes when the design switches

### 5.1 Values that change (all computed at run time, none pinned)

For the same input reading, **every one of these differs** between the engines (measured on the corpus in section 7, 588 comparable readings, 0 equal):

- `decision_fingerprint` (verdict field and audit entry field)
- `parameter_set_version`
- `state_commitment` and `predecessor_state_commitment`
- the audit-ledger `audit_hash`, because the audit entry's content and shape change (upstream adds `cassette`, and omits `validation_faults` and `verdict.unassessable` when clean)
- the state payload OBSERVE commits to, because the commitment is rebuilt from `{subject, fingerprint}`

### 5.2 Pinned values and golden files

**None in OBSERVE's root tests, docs or JSON.** No other repository pins an OBSERVE-derived digest: `interconnected_delta` and `interconnected_beta` use placeholder strings.

### 5.3 Persisted evidence

Unknown (section 1). If any ledger holds old-style entries, they can still be read but their fingerprints cannot be recomputed by the new engine. See 6.4.

### 5.4 Tests that change (measured by running OBSERVE's root tests against the upstream engine)

| Test file | Result against the upstream engine |
|---|---|
| `test_observe_consolidated.py` + `test_observe_clinical_risk_adapter.py` | **78 passed, 0 changed** |
| `test_cns_connector.py` | **10 passed, 0 changed** |
| `test_observe_invariants.py` | **fails at import**: it imports `compute_decision_fingerprint`, `HEAVY_PATH_ENTROPY_TRIGGER` and `HEURISTIC_HARD_RULE_THRESHOLD`, which upstream does not export |

With those three names stubbed to see run-time failures, **8 tests fail** (the ninth failure was only because the throwaway directory had no `sentinel_os/`):

| # | Test | Why it fails |
|---|---|---|
| 1 | `StateContinuityBoundary::test_state_commitment_is_deterministic` | call signature: upstream's function takes `(parent_commitment, state)` |
| 2 | `StateContinuityBoundary::test_state_commitment_binds_to_predecessor` | same: no `predecessor_state_commitment` keyword |
| 3 | `T2_MissingOrGarbageTelemetryNeverReadsAsHealthy::test_out_of_range_vital_rejected` | fault text changed: `heart_rate=out_of_range(999.0)` became `heart_rate=999.0 outside physical range [0.0, 350.0]` |
| 4 | `T2b_ValidationFaultOverlayIsSafe::test_fault_in_one_channel_preserves_signals_in_the_others` | same fault-text change |
| 5 | `I3_...::test_decision_fingerprint_is_deterministic_and_timestamp_free` | calls `compute_decision_fingerprint` |
| 6 | `I3_...::test_decision_fingerprint_is_persisted_on_verdict_and_in_audit` | same |
| 7 | `I3_...::test_fingerprint_moves_with_the_parameter_version` | same |
| 8 | `I3_...::test_manifest_entries_track_their_live_module_constants` | `KeyError: 'heavy_path_entropy_trigger'` |

Each is a rule-5 edit in PR-2: the test changes only to assert the new behaviour. The edits are listed in that PR. Tests 3 and 4 are not about the fingerprint
at all; they come from upstream's reworded fault text (`VALIDATION_FAULT:` became `DATA_INTEGRITY_FAULT:` in the rule notes), which is also part of what the fingerprint covers.

### 5.5 Behaviour changes that come with the upstream engine (the surprise)

The re-sync is **not only plumbing**. It adopts upstream's clinical-engine changes. Measured on the corpus:

| Finding | Detail |
|---|---|
| The root engine crashes on bad context | `TypeError` on `previous_o2="x"` and on `age_months="x"`. 12 of 600 corpus readings, on 7 of 12 patients. Upstream raised 0 (it sanitizes context). |
| Regime and escalation agree where the root engine did not crash | 5 patients, 255 readings: **0** disagreements |
| Risk scores differ slightly | 13 of those 255 readings |
| The set of engines differs | 27 of 255: upstream selects the `behavioral` engine more often ("behavioral gating widened") |
| Disagreements on the other 7 patients | 12 regime or escalation differences in 333 readings, all on patients whose root engine had already crashed. Whether the crash caused the divergence (a partly updated state) is **not established** |

Consequence: PR-2 changes which engines run and some risk scores in OBSERVE. `docs/CLINICAL_SCORING.md` documents the old gating and must be updated, and the owner (or a clinician) should accept those scoring changes on purpose.

## 6. OBSERVE-only work that must move into observe-perceive first

### 6.1 Inventory and disposition

| OBSERVE-only item | Already upstream? | Conflicts with upstream's design? | Disposition |
|---|---|---|---|
| Parameter-set version | yes (#29) | different manifest content | nothing to port |
| State commitment chain | yes (#29), different structure | yes, by design (section 4.2) | owner chose upstream's; nothing to port |
| `STATE_EVICTED` ledger entry and the non-stable-or-locked eviction rule (#19) | yes (#53, same intent) | no | nothing to port |
| `HEAVY_PATH_ENTROPY_TRIGGER`, `HEURISTIC_HARD_RULE_THRESHOLD` | values equal; live in the cassette | they are not in the version hash upstream | do not port (see 6.2) |
| `_VITALS_NEUTRAL`, `_CHANNEL_CONTEXT_KEYS`, `_REGIME_SEVERITY`, `_max_severity`, `REGIME_RISK_FLOOR`, `UNASSESSABLE_CONFIDENCE_PENALTY` | yes (cassette or engine) | no | nothing to port |
| 9-decimal rounding inside the fingerprint | **no** | upstream does not round | open question 2 |
| NaN, infinity and UTC-datetime handling in commitments | **no** | upstream passes floats through | do not port; moot today (4.2) |
| The 44 invariant tests | 43 of 44 by name; 51 upstream | no | verify the one missing name (section 1) |
| Empty-distribution fix (#19 step 2) | n/a: it is in `observe_clinical_risk_adapter.py`, an OBSERVE-only pipeline | n/a | stays in OBSERVE |

### 6.2 Conclusion

**Almost nothing needs to move into observe-perceive.** The reason the "port first" step shrinks is that PR #29 already ported OBSERVE's parameter-set and
state-commitment work upstream, in a different design, and the owner chose that design. What remains is decisions (open questions 2 and 3), not code.
Adding the two thresholds to upstream's `PARAMETER_SET` would change `PARAMETER_SET_VERSION` for every upstream user and so is not recommended; the cassette
identity already binds them.

### 6.3 Conflicts with upstream's design

- Rounding (6.1) is the only item where OBSERVE's choice would change upstream's bytes.
- OBSERVE's `scope` string has no upstream counterpart. If separate commitment namespaces matter, upstream would need to add it; the owner decided otherwise.

### 6.4 If persisted old-style evidence exists

Verifiers would need to branch on the audit entry's `parameter_set_version` (the two engines produce different versions) to pick the algorithm.
Because `schema` is `observe.parameters/v1` on both sides, the label cannot tell the eras apart. See open question 3.

## 7. Differential-test strategy

### 7.1 What was run for this plan (read-only; scripts and outputs were in `/tmp`, nothing was added to any repository)

- One deterministic corpus: 600 readings, 12 patients, seed `20261029`, with ordinary, deteriorating, faulted-channel and bad-context readings, run through each engine
  in its own process. The script is reproduced in Appendix A.
- Comparisons: regime, escalation, risk, entropy, engine set, fingerprint, parameter version, commitment, and chain integrity.
- Results: section 5.1 (digests all differ), section 5.5 (behaviour), chain integrity intact in both (588 of 588 root, 600 of 600 upstream).

### 7.2 What the real differential test should do (a proposed addition to PR-2)

1. **Behaviour parity with an allow-list.** Replay a larger fixed corpus through the old and new engines. Fail on any regime or escalation difference for a patient
   whose old run did not crash. List the expected differences (wider behavioural gating, context sanitizing, fault wording) so each one is accepted on purpose.
2. **Property tests for the new fingerprint** (because old and new values cannot be equal): the same input gives the same fingerprint across processes and across
   `PYTHONHASHSEED` values; changing any decision field changes it; it contains no wall-clock value; it changes when the parameter version or the cassette changes;
   recomputing it from the stored audit entry matches.
3. **Equivalence-class check.** Include repeated identical readings on fresh engines. Group by old fingerprint and by new fingerprint: the new partition must be equal
   or finer, never coarser (the corpus in 7.1 gave a trivial 588 groups each because every reading was unique, so it did not test this).
4. **Chain check.** Recompute every state commitment from the stored entries and confirm each predecessor link.
5. **Round-trip of faulted input.** Faulted and junk-context readings must produce a verdict and a fingerprint, never an exception.

## 8. Sequence of small pull requests

Every PR is built on a branch, has one commit per step, and is listed with its rule-5 test edits.

| PR | Repository | What | Size | Risk | Rollback |
|---|---|---|---|---|---|
| **0 (done on this branch)** | OBSERVE | Pin the vendored snapshot; declare the root `diverged`; this plan | about 60 lines | low: red CI becomes green and still fails loudly on drift | revert the merge commit |
| **1** | observe-perceive | **No code required.** A short confirmation PR or note only if the owner decides open questions 2 or 3 in a way that needs an upstream change | 0 to about 40 lines | low | revert |
| **2** | OBSERVE | Re-sync the root engine from observe-perceive at one recorded commit `X`: replace `observe_consolidated.py`; add `cassette.py`, `pediatric_cassette.py`, `kalman_trajectory.py`, `governance_contracts.py` at the repository root; update `test_observe_invariants.py` for the 8 tests in 5.4 (rule-5 edits, listed); add the section 7.2 differential tests; update `docs/CLINICAL_SCORING.md`, README, `UPSTREAM.md` and `VENDORED.md`; regenerate `.ghost_baseline.json`; update the stopgap test's "root is diverged" clause, because the root becomes identical to upstream `X` | about +2,350 lines of engine and modules; about 120 lines of test edits; about 100 lines of docs | **medium**: changes engine selection and some risk scores (5.5), and the evidence hashes | revert the merge commit; the stopgap pin is untouched because the vendored copy does not change in this PR |
| **3** | OBSERVE | Re-sync the 10 observe-perceive-derived files inside `sentinel_os/` that differ from upstream HEAD, to the same commit `X`: `observe_consolidated` (435 changed lines), `test_clinical_governance_system` (192), `perceive_consolidated` (135), `clinical_governance_system` (118), `kalman_trajectory` (80), `test_observe_consolidated` (49), `governance_contracts` (43), `test_perceive_consolidated` (14), `compliance_exporters` and its test (2 each); add the two modules `sentinel_os/` lacks (`cassette.py`, `pediatric_cassette.py`); move the stopgap pin to the new hash | about 1,070 changed lines + 440 new lines | **highest**: the `sentinel_os/` suite needs Redis and Postgres and can only be validated in CI; `UPSTREAM.md` records an earlier large sync that dropped passing tests from 570 to 337 (that was the diverged files; this subset collected cleanly then) | revert the merge commit |
| **4** | OBSERVE | Restore the original byte-identity assertion between root and `sentinel_os/` `observe_consolidated.py`; delete the stopgap section and pin; set the `VENDORED.md` rows to `identical` | about 40 lines | low | revert |

Order matters: PR-2 before PR-3 keeps the quick, fully local root suite as the first gate and leaves the heavy `sentinel_os/` suite for the second. Between PR-2 and PR-3 root and
`sentinel_os/` differ again (root at `X`, vendored still at `717c2e2`); the updated stopgap test covers that interval. An alternative to PR-3 is the direction `UPSTREAM.md` already names:
adopt sentinel_os wholesale as a submodule, as GSA-815 does, and delete the copy (a deletion, so propose only; open question 7).

## 9. Open questions for the owner

1. **Scoring changes.** Do you accept that PR-2 adopts upstream's wider behavioural-engine gating and context sanitizing (section 5.5), with a clinical review of `docs/CLINICAL_SCORING.md`?
2. **Rounding.** OBSERVE rounds risk and entropy to 9 decimals inside its fingerprint; upstream does not. Keep upstream as is, or add rounding upstream (which would change every upstream fingerprint)?
3. **Evidence eras.** Both engines label their parameters `observe.parameters/v1` with different content. Should upstream bump the label to `v2`, and does any persisted evidence need a verifier that can tell the eras apart? (Assumed: none exists.)
4. **Bypass note.** OBSERVE's fingerprint included the safety-bypass note in `triggered_rules`; upstream's does not. Is that acceptable, or should the note be added to upstream's decision data?
5. **Test edits.** Do you pre-approve the edits to the stopgap test in PR-2, PR-3 and PR-4, and the 8 invariant-test edits in PR-2? (Your approval so far covers the stopgap edit only.)
6. **Third hash.** `observe_clinical_risk_adapter.py` computes its own `decision_hash`. The goal of "one fingerprint" would need that retired or redirected. In scope?
7. **`sentinel_os/` direction.** Re-sync file by file (PR-3), or adopt sentinel_os as a submodule and remove the copy?
8. **Reference commit `X`.** Which observe-perceive commit should PR-2 and PR-3 pin, and should upstream freeze changes to `observe_consolidated.py` while the re-sync is in flight?
9. **Ghost baseline.** Who regenerates `.ghost_baseline.json`, and with which tool version?

## Appendix A: the corpus script used for section 7.1

Run once in each repository root (`python3 run_corpus.py out.json`), with that repository's `observe_consolidated.py` importable.

```python
import json, random, sys, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.getcwd())
import observe_consolidated as oc
random.seed(20261029)
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
rows = []
eng = oc.ObserveClinicalEngine()
patients = [f"P{i}" for i in range(12)]
clock = {p: T0 for p in patients}
for n in range(600):
    p = random.choice(patients)
    clock[p] += timedelta(seconds=random.choice([30, 60, 120, 400]))
    kind = random.random()
    if kind < 0.55:
        hr, o2, rr, temp = random.uniform(70, 150), random.uniform(90, 100), random.uniform(15, 40), random.uniform(36, 39.5)
    elif kind < 0.85:
        hr, o2, rr, temp = random.uniform(130, 190), random.uniform(78, 92), random.uniform(35, 60), random.uniform(38.5, 41)
    elif kind < 0.93:
        hr, o2, rr, temp = random.uniform(70, 150), float("nan") if random.random() < .5 else 250.0, random.uniform(15, 40), random.uniform(36, 39)
    else:
        hr, o2, rr, temp = random.uniform(70, 150), random.uniform(90, 100), random.uniform(15, 40), random.uniform(36, 39)
    ctx = {"age_months": random.choice([1, 6, 18, 48, None])}
    if kind >= 0.93:
        ctx["previous_o2"] = random.choice([200, "x", 91])
    if random.random() < .2:
        ctx["force_heavy"] = True
    v = oc.VitalsSnapshot(p, clock[p], hr, o2, rr, temp, context=ctx)
    try:
        r = eng.evaluate(v)
        rows.append({"i": n, "patient": p, "risk": round(r.risk_score, 9), "regime": r.regime.value,
                     "esc": r.escalation_required, "entropy": round(r.entropy, 9), "engines": list(r.active_engines),
                     "unassess": r.unassessable, "fp": r.decision_fingerprint, "psv": r.parameter_set_version,
                     "sc": r.state_commitment, "pred": r.predecessor_state_commitment})
    except Exception as e:
        rows.append({"i": n, "patient": p, "error": type(e).__name__})
json.dump(rows, open(sys.argv[1], "w"))
```
