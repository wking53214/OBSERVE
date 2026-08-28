# Changelog

Dated, human-readable summary of notable changes. Git history has the
full detail; this is the skim version.

## 2026-08-28 (follow-up, after PR #1)

- **`PARAMETER_SET_VERSION` scope stated honestly.** It attests the named
  module-level calibration constants. It does **not** attest the
  `score += X` risk weights inside the adapter methods, nor the branch
  logic in `ObserveClinicalEngine.evaluate` / `EscalationPolicy` /
  `regime_distribution` / `validate_vitals` — those are attested by the
  source-control revision that produced the build. (An earlier draft of
  this follow-up folded an `inspect.getsource` digest of three classes
  into the version; reverted — it produced a *different* version for
  byte-identical code in a frozen/`.pyc` deployment vs a source checkout,
  which would report phantom drift on every cross-build fingerprint
  replay. Hoisting the genuine tunable weights into named constants is a
  separate deferred follow-up; ~half the adapter literals are structural,
  not tunable, and would overclaim if put in a *parameter* manifest.)
- **`observe_clinical_risk_source.py.broken` deleted.** The flattened,
  non-parsing nominal source (retired to `.broken` in PR #1) is gone —
  nothing imported it; content is in git history.
- Root suite 117 pass; vendored observe/perceive 152 pass.

## 2026-08-28

- **Resilience-fix review round.** Code review of the 2026-08-27 change
  found the validation gate was too blunt. Reworked:
  - A faulted channel is now **masked** to a non-alerting value and the
    remaining channels are still assessed — a `NaN` SpO2 no longer
    suppresses a real `HR=210`.
  - The fault is overlaid as a **WARNING floor that never downgrades**
    the patient's tracked regime (a sensor dropout on a CRITICAL patient
    stays CRITICAL), routes escalation through the 300 s cooldown (no
    page-storm on a flapping lead), and floors `risk_score` to match the
    forced regime (an unassessable patient can't be sorted to the bottom
    of a risk-ranked ward).
  - `VITALS_PHYSICAL_BOUNDS` widened to sensor-plausibility only —
    clinically extreme but real values (profound hypothermia ~20 °C,
    infant SVT ~300 bpm) are assessed, not rejected.
  - `compute_decision_fingerprint()` is now **called by `evaluate()`** and
    stored on the verdict and in the audit entry (it was defined but
    unwired). New `FusedVerdict` fields: `decision_fingerprint`,
    `unassessable`.
  - `EscalationPolicy` is constructed with the declared
    `ESCALATION_*` constants explicitly; the `PARAMETER_SET` scope note
    now states what the version does and does not attest.
  - A **second review round** found the overlay still fed masked data
    through the stateful `EscalationPolicy` (corrupting/stalling the
    real-signal dwell state), masked delta-channels injected a synthetic
    improving trend, the risk floor was skipped on hold calls, a transient
    fault permanently bumped the tracked regime, and `PARAMETER_SET`
    aliased mutable module dicts. Reworked: on a fault with no
    valid-channel emergency the policy is **frozen** (not evaluated with
    masked data); faulted channels also drop their trend-context keys;
    the risk floor uses an explicit `REGIME_RISK_FLOOR` map applied every
    call; fault-escalation dedup moved to engine-level per-patient state;
    `PARAMETER_SET` is a `deepcopy` snapshot.
  - A **third review round**: the fault path is now fully frozen on the
    bypass branch too (it was still writing `policy.current_regime` from a
    masked-data distribution); `_patient_entropy` is no longer overwritten
    by a fault reading (it drives heavy-engine selection); and the
    repo-root `pytest.ini` was removed — it was silently changing the
    vendored `sentinel_os` CI suite's rootdir/import-mode. The root suite
    is now named explicitly in the CI step instead.
  - `test_observe_invariants.py` grew 23 → 41 tests. Full: 117 root pass,
    152 vendored observe/perceive pass, ruff clean.

## 2026-08-27

- **Resilience-candidate assessment + findings fixed** — the "URE /
  IntegratedResilienceOrchestrator" candidate was investigated and
  **rejected** (another, weaker implementation of capabilities OBSERVE
  already has; see `RESILIENCE_INTEGRATION_ASSESSMENT.md`). Three fixes
  the investigation surfaced were applied:
  - **Canonical source adopted.** `observe_consolidated.py` is now an
    OBSERVE-owned file at the repo root (was only a vendored copy under
    `sentinel_os/`). The flattened, non-parsing
    `observe_clinical_risk_source.py` is retired to `.broken`.
  - **Input validation restored (T-2/T-6).** The consolidated engine did
    NO vital validation — a `NaN`/out-of-range vital fused to a confident
    `STABLE`. `validate_vitals` + `VITALS_PHYSICAL_BOUNDS` ported back
    from the retired source; `evaluate()` now returns a `WARNING` verdict
    carrying `validation_faults` (never `STABLE`) and audits the
    rejection.
  - **Parameter-set provenance (I-3).** Calibration constants are hoisted
    to a named surface and declared in `PARAMETER_SET`;
    `PARAMETER_SET_VERSION` (its SHA-256) is stamped on every
    `FusedVerdict` and folded into every audit entry.
    `compute_decision_fingerprint()` gives a deterministic, wall-clock-free
    decision hash for replay / drift detection.
  - New `test_observe_invariants.py` — 23 property tests (OBSERVE's first
    repo-owned invariant suite) locking out the candidate's failure modes.
    Full: 99 passed (76 existing + 23 new); vendored `sentinel_os` suite
    still 82 passed.

## 2026-07-24

- **C2 dimension 4: statistical outcome-equity** — the fourth C2
  bias-identification dimension, unbuilt until now, is real: a
  COHORT-level four-fifths-rule disparate-impact checker
  (`regulatory_checks.check_statistical_outcome_equity`), a sealed
  channel for protected-characteristic data completely walled off from
  the live judgment path (`sealed_demographic_channel.py` — new table,
  new role, no grant to `ledger_reader`, ever), and a real BISG
  estimator (`bisg_estimator.py`) reproducing CFPB's own published
  methodology over live Census geocoding/ACS data plus the actual 2010
  Census surname list — never a fabricated estimate; any unreachable
  data source makes the whole estimate INDETERMINATE. `RegulationCheckProfile`
  gains `consent_model` (`opt_in_required` default, or
  `opt_out_permitted`). `CFPBRegBLens.c2_rollup()` can now genuinely
  reach `PASS`, not just `FLAG`/`INDETERMINATE`, when a caller supplies
  an already-computed dimension-4 result for a cohort — automatic
  cohort assembly is not built this session.

## 2026-07-23

- **Cassette kernel/capability split** — the cassette contract is no
  longer IVR-shaped. A minimal domain-blind KERNEL (identity, typed
  parameter declarations, `judge(episode)` / `explain(episode)`) plus
  four opt-in CAPABILITY modules (`telephony_ingest`,
  `routing_topology`, `rl`, `self_healing`), each owning its own
  parameters and methods. A cassette declares a `CAPABILITIES`
  manifest; load-time validation checks kernel + the union of enabled
  capabilities, and **rejects any parameter owned by a disabled
  capability** — the anti-placeholder rule. Schema `2.0.0`; snapshots
  now record the manifest.
- **Episode ground-truth record** (`episode.py`) — kernel-level record
  of requested vs. actual outcome with two enforced invariants: a
  reason is owed on ANY outcome mismatch (paid-but-reduced counts,
  not just formal denials), and the actor's self-report is always
  cross-checked against the observed record (twin posture), with
  divergences surfaced ahead of the cassette's own factors in every
  explanation. No judgment path admits an unvalidated episode.
- **Banking cassette is honest now** — declares
  routing + rl + self_healing only; the three flagged placeholder
  `twilio_*` thresholds are gone (validation would now refuse them),
  and its judgment moved to the kernel surface with arithmetic
  unchanged. Consequence: banking is refused by the telephony
  pipelines at the door (legible capability error at construction)
  instead of pretending Twilio-readiness it never had.
- **IVR is the reference implementation** — enables all four
  capabilities; kernel `judge` proven arithmetically identical to the
  legacy `score_outcome_quality` by an equivalence sweep. Version
  `2.0.0` (identity, not behavior: the code hash changed, and binding
  enforcement correctly refuses a changed hash under an old version).
- **Engines guard their doors** — `SentinelCore`, `CassetteHarness`,
  `IcebergProductionHarness` (construction and swap), and Twilio
  ingest each refuse a cassette missing the capabilities they read,
  at construction rather than mid-call.
- **Pre-existing defect fixed** — `serialize_cassette_for_ledger`
  duplicated the snapshot serialization and had silently drifted from
  `GovernanceParameters.snapshot()`; it now delegates to the single
  source of truth.
- Full suite: 307 passed (279 baseline + 28 new proof tests, including
  a kernel-only cassette with zero telephony surface that loads,
  validates, and judges — the shape a hiring cassette starts from).

## 2026-07-22

- **Phase 2 merged** — closed 6 of 7 Known Limitations: cassette
  version binding, code-hash coverage, structural injection defense,
  model identity per decision, decision supersession, authorizing
  identity. See `COMPLIANCE.md` and `PHASE2_MIGRATION_NOTES.md`.
- **ICEBERG_LEDGER_RUNTIME_USER made fail-closed** — the app no longer
  boots with a privileged database credential, even by accident. See
  `governance/README.md`.
- **docker-compose fixed end-to-end** — the runtime-user fix above
  would have broken `docker-compose up` (no fallback credential to
  silently use); fixed via self-provisioning instead of just patching
  the compose file. Also fixed a separate, pre-existing startup race
  (`iceberg-main` could start before Postgres was actually ready to
  accept connections).
- **CI corrected** — `tests.yml` previously only ran the `Tests/`
  subdirectory (27 of 37 test files) and had no Redis service at all.
  Now runs the full suite; `test_twin_live.py` is explicitly excluded
  (needs infrastructure — 3 OS identities, real TLS PKI between them —
  not yet reconstructed in CI) rather than silently skipped.
- **Full stack verified live** — real Postgres ledger, real fail-closed
  credential behavior, a governed call correctly blocked with no
  governor configured, and an independently-verified 25-entry hash
  chain, all confirmed running end-to-end.
