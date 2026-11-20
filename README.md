# OBSERVE

Observation and state-assessment code for ≡TACK, with pediatric physiological monitoring as the worked example. **Not for clinical use.** It has not been clinically validated or reviewed by a clinician, and it is not a medical device.

Status: downstream copy plus a large vendored tree. Last checked 2026-11-19 at commit `32d5620`. This repo's history was rewritten after the 2026-11-15 review; every root file is unchanged by that rewrite. License: Apache-2.0 (`LICENSE`).

## Role Within ≡TACK

- **What it is.** The observation stage: it turns vitals into a regime, risk score and an escalation flag. It is a downstream copy of the engine in `observe-perceive`, plus OBSERVE-only wiring (`observe_engine_gate.py`, `observe_clinical_risk_adapter.py`, `cns_connector.py`).
- **What it owns.** The choice of when the behavioral engine runs (`observe_engine_gate.py`, currently the `conservative_legacy` rule), and its own clinical adapter wiring. It does not own the engine: `observe_consolidated.py` is a byte-for-byte copy of observe-perceive `d596262`.
- **What it contributes.** The observation concept and a reference for the extracted detectors in `interconnected_alpha` and `interconnected_zeta`.
- **What it does not own.** Authorization, execution, custody, admission, or the orchestrator (observe-perceive). It does not own policy, but PERCEIVE policy files sit in this tree.
- **Depends on.** observe-perceive (engine source), sentinel_os and GSA-815 (the nested `sentinel_os/` tree). Optional CNS v4.0.0 for the connector (`requirements-cns.txt`).
- **Depended on by.** UNKNOWN. No consumer was found or inspected.
- **Verified versus declared.** Verified: root copy matches its pins (`VENDORED.md`, checked by `test_observe_invariants.py`). Declared only: the planned order below and the "paired with PERCEIVE" relationship. Nothing in this repo is on the orchestrator path (observe-perceive's `GovernanceOrchestrator`).
- **Governance and control design.** OBSERVE's output is evidence, not authority. A regime or escalation flag is a signal for a downstream stage. It is not a decision.

## Known upstream fixes this copy lacks

**Root engine (updated 2026-11-19).** The root engine is observe-perceive `d596262`. Between `d596262` and observe-perceive's head `34894bb` the engine files are unchanged (INSPECTED with `git diff`, 2026-11-19), so the root engine is current. The four escalation fixes that earlier versions of this section listed (cooldown hiding a severity increase, dwell on an already-escalated patient who worsens, escalation state for an unrecorded reading, a hard rule averaged away by history) were part of this re-sync. Re-checking each one against the new engine has not been done.

**This re-sync changes scoring and has NOT been clinically reviewed.** On the recorded 600-reading corpus it differs from the old engine on 79 fields; 50 readings change regime or escalation, 43 more cautious and 7 less cautious. See `docs/ENGINE_RESYNC_DIFFERENCES.md` and `docs/ENGINE_RESYNC_DISPOSITIONS.md`. Do not treat the new engine as clinically approved.

**Nested copy.** `sentinel_os/observe_consolidated.py` is observe-perceive `bca7a70` (the twin of `e818659`, whose history was rewritten) and still lacks the fixes above. Do not use its escalation output where those cases matter.

## Pipeline position

**OBSERVATION.** Evidence-bearing state assessment. Does not authorize.

What runs today is observe-perceive's `GovernanceOrchestrator` (INSPECTED in its `governance_orchestrator.py` at `b4f4c62`, 2026-11-19). It uses observe-perceive's own copy of the engine. It does not import this repo.

```text
(caller)  optional Governance_Gateway admission, passed in
   │
   ▼
OBSERVE assessment            observe-perceive's observe_consolidated (dwell and cooldown locks are inside it)
   ▼
admission and source-time checks
   ▼
PERCEIVE
   ▼
fortress-kernel containment   opt-in
   ▼
Conservation_Kernel
   ▼
execution approval and scope check
   ▼
executor (execution_guard), then the audit-chain link
```

### Planned order (design, not what runs)

```text
Admission → OBSERVE (this repo / observe_consolidated) → Locks → PERCEIVE → Decision → Conservation → Execution → Custody
```

This is the order the architecture text describes. It differs from what runs: OBSERVE runs before the admission check, the locks are part of OBSERVE, and the engine that runs is observe-perceive's, not this repo's.

Paired with PERCEIVE inside [`observe-perceive`](https://github.com/wking53214/observe-perceive). Named-Keys extraction: [`interconnected_alpha`](https://github.com/wking53214/interconnected_alpha). This repository is **not** on the orchestrator path; it is the observation concept plus a large amount of vendored history.

## 2. Full System Scope & Architectural Depth

Intended pipeline:

```text
SIGNAL → VALIDATE → OBSERVATION → ASSESSMENT → FUSION → REGIME → EVIDENCE
```

Missing evidence is not evidence of normality (abstention is first-class). Observation before governance. No silent normalization.

What actually lives in this checkout:

| Path | What it is |
|---|---|
| `observe_consolidated.py` | The OBSERVE engine: RiskAdapters, EscalationPolicy, fusion. **Copied byte-for-byte from observe-perceive `d596262`** (never edited here), with its seven sibling modules `cassette.py`, `pediatric_cassette.py`, `kalman_trajectory.py`, `governance_contracts.py`, `clinical_settings.py`, `log_redaction.py` and `logic_stamp.py`. |
| `observe_engine_gate.py` | OBSERVE's own: the one place that chooses when the behavioral engine runs (`conservative_legacy`, OBSERVE's rule, until a pediatrician signs off upstream's widened rule). |
| `observe_clinical_risk_adapter.py` and `clinical_*` | Clinical wiring. Three files in this tree do not import (EXECUTED 2026-11-16): `clinical_capacity_orchestration_source.py` needs a `perceive_consolidated` module that is not here, and `clinical_governance_ledger_source.py` and `perceive_policy_enforcement_source.py` are reconstructed files that raise a SyntaxError. No root test covers the capacity, ledger or policy adapters. |
| `perceive_policy_enforcement_*` | PERCEIVE copies / flattened sources — **policy code in an observation repo**. |
| `sentinel_os/` | A **vendored historical tree** of sentinel_os: patches (`APPLY-*.md`, `0001-*.patch`), Docker, tests, governance, cassettes. Not a clean observation library. |
| `docs/CLINICAL_SCORING.md` | Scoring notes. |

`RiskAdapters.heuristic` (age-adjusted single-vital thresholds) and `behavioral_vaccine` (fixed-threshold syndromes + score modulation) are the extraction source for α. `EscalationPolicy` (dwell, cooldown, one shared regime per patient) is the extraction source for ζ.

## 3. What It Does NOT Do / Non-Goals

- Does **not** authorize, execute, or conserve transformations.
- Does **not** substitute for Gateway admission.
- Does **not** ship as a medical device. No clinical validation study.
- Does **not** provide the orchestrator (observe-perceive does).
- Does **not** own custody (sentinel_os does — and a stale copy of that kernel is nested *inside this repo*, which is a comprehension hazard).

## 4. Brutally Honest Current Status & Gaps

| Gap | Detail |
|---|---|
| Nested `sentinel_os/` | Hundreds of files: patches, APPLY playbooks, IVR kernel. OBSERVE-the-idea is a handful of modules; OBSERVE-the-repo is a dump. Drift vs live `wking53214/sentinel_os` is expected. |
| Engine copies | The root engine is a byte-identical copy of observe-perceive `d596262` (pinned in `VENDORED.md`, checked by `test_observe_invariants.py`). `sentinel_os/observe_consolidated.py` is the older snapshot `bca7a70` (re-synced in PR-3) and has NOT been brought up to `d596262`; the two copies differ on purpose until the owner decides (`RECONCILE_UPSTREAM_PLAN.md`). |
| Clinical skips | Commercial red team: missed/late pediatric detections and sensor-fault gaps recorded as **skipped tests** in the spine. This repo does not close them. |
| Uncalibrated constants | `PEDIATRIC_NORMS`, dwell, lock_seconds, syndrome weights (`0.40`/`0.35`) — copied into α without independent validation. |
| Age-adjustment asymmetry | Syndromes not age-adjusted. Preserved, not a bug, but unsafe to treat as a finished clinical model. |
| PERCEIVE files in-tree | Observation/policy seam is blurred in the file tree even if the architecture text separates them. |
| Not commercially relevant as a sepsis product | Explicit audit finding. Use as the hard-domain reference for the spine. |

No `pyproject.toml` at repo root. Not an installable observation package.

## 5. Core Invariants & Guarantees

- Observation ≠ policy ≠ authorization (claimed; tree mixing undermines the claim).
- Abstention is representable.
- Named conditions in RiskAdapters are deterministic given finite vitals.

No guarantee of sensitivity/specificity, calibration, or that this tree is the engine the orchestrator runs.

## 6. Inputs, Outputs & Type Contracts

Live types live in `observe_consolidated.py` (also in observe-perceive): `VitalsSnapshot`-like records, fused verdict (`risk_score`, `regime`, `confidence`, `entropy`, `active_engines`, `triggered_rules`, `timestamp`, `audit_hash`, `escalation_required`, `decision_fingerprint`). α's `VitalsObservation` is a strict subset.

## 7. Stack Integration Topology

```text
observe-perceive:observe_consolidated.py  (LIVE)  ──copied──►  this repo:observe_consolidated.py
        │                                         │
        ├── extracted detectors ──► interconnected_alpha
        └── EscalationPolicy   ──► interconnected_zeta
sentinel_os/ (nested, stale)   ──✗ not──►  wking53214/sentinel_os (LIVE custody)
```

See `VENDORED.md` / `UPSTREAM.md` if present for the intended relationship.

## Install and quick start

No installable package: there is no `pyproject.toml`. Run the root suite from a checkout:

```
pip install pytest
python -m pytest -q test_*.py
```

The nested `sentinel_os/` suite runs as a CI step that needs Redis and Postgres (`.github/workflows/tests.yml`). That step is marked non-blocking, and the workflow's own comment says the suite fails until the reconcile plan is done, so a green CI run says nothing about it. It was not run for this README. The blocking root step names four test files; `test_observe_gate_sync.py` and `test_domain_signal_validator.py` are in no CI step (INSPECTED).

## Testing and verification

EXECUTED 2026-11-15 (Python 3.13), root suite `test_*.py`: 155 passed, 1 skipped. Same result on 2026-11-19 at `32d5620`, and 186 passed with `requirements-cns.txt` installed. That covers the root engine copy, the invariants and pin test, the clinical adapter, the engine gate and the CNS connector. It does not show the engine is clinically correct. The nested `sentinel_os/` suite was not run (UNKNOWN). Clinical skips recorded upstream are not closed here.

## Failure behavior and trust

Missing evidence is meant to abstain, not read as normal. EXECUTED 2026-11-16 through `make_engine`: a missing or non-numeric vital sign gave WARNING with escalation and a `DATA_INTEGRITY_FAULT` finding. A missing or invalid age is the exception and fails open: a critical oxygen reading was rated STABLE (see "Known upstream fixes this copy lacks"). Context trust-boundary handling (`sanitize_context`) is in this copy: `observe_consolidated.py` defines it and `evaluate` calls it (INSPECTED 2026-11-16). `UPSTREAM.md` still says this copy lacks it; that text describes the 2026-09-07 state.

## Documentation

`UPSTREAM.md` and `VENDORED.md` (what is copied and from where), `RECONCILE_UPSTREAM_PLAN.md`, `RECONCILE_HARNESS_PLAN.md`, `RESILIENCE_INTEGRATION_ASSESSMENT.md`, `TROUBLESHOOTING.md`, `CONTRIBUTING.md`, `docs/CLINICAL_SCORING.md` (for clinical review; not yet reviewed), `docs/CHANGELOG.md`.

Maintainer: William N. King.
