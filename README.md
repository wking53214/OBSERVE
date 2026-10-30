# OBSERVE

Industry-agnostic **observation and state-assessment** architecture. The principal demonstration is physiological/clinical monitoring — a representative application, not the definition.

## 1. Pipeline Position & Role

**OBSERVATION.** Evidence-bearing state assessment. Does not authorize.

```text
Admission → OBSERVE (this repo / observe_consolidated) → Locks → PERCEIVE → Decision → Conservation → Execution → Custody
```

Paired with PERCEIVE inside [`observe-perceive`](https://github.com/wking53214/observe-perceive). Named-Keys extraction: [`interconnected_alpha`](https://github.com/wking53214/interconnected_alpha). This repository is **not** the live orchestrator; it is the observation concept plus a large amount of vendored history.

## 2. Full System Scope & Architectural Depth

Intended pipeline:

```text
SIGNAL → VALIDATE → OBSERVATION → ASSESSMENT → FUSION → REGIME → EVIDENCE
```

Missing evidence is not evidence of normality (abstention is first-class). Observation before governance. No silent normalization.

What actually lives in this checkout:

| Path | What it is |
|---|---|
| `observe_consolidated.py` | The OBSERVE engine: RiskAdapters, EscalationPolicy, fusion. **Copied byte-for-byte from observe-perceive `e818659`** (never edited here), with its four sibling modules `cassette.py`, `pediatric_cassette.py`, `kalman_trajectory.py` and `governance_contracts.py`. |
| `observe_engine_gate.py` | OBSERVE's own: the one place that chooses when the behavioral engine runs (`conservative_legacy`, OBSERVE's rule, until a pediatrician signs off upstream's widened rule). |
| `observe_clinical_risk_adapter.py` and `clinical_*` | Clinical wiring. |
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
| Engine copies | The root engine is a byte-identical copy of observe-perceive `e818659` (pinned in `VENDORED.md`, checked by `test_observe_invariants.py`). `sentinel_os/observe_consolidated.py` is still the older upstream snapshot `717c2e2` until PR-3 of `RECONCILE_UPSTREAM_PLAN.md`. |
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

Apache-2.0.
