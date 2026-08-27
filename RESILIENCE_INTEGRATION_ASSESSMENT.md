# RESILIENCE_INTEGRATION_ASSESSMENT

Adversarial architectural investigation — "URE / SystemResilienceConfig /
StabilityMonitor / SystemRegimeClassifier / IntegratedResilienceOrchestrator"
candidate vs. `wking53214/OBSERVE`.

Investigation phase: no source modified. **Implementation phase (authorized
2026-08-27): see "Implementation status" at the end of this document.**

---

## 0. Candidate identification & provenance chain

The investigation prompt's candidate-code block was delivered as an unfilled
placeholder (`[PASTE COMPLETE ... CODE HERE]`). The candidate was identified by
evidence, not supplied directly:

1. Prompt names five classes: `SystemResilienceConfig`, `SystemMetricsTelemetry`,
   `StabilityMonitor`, `SystemRegimeClassifier`, `IntegratedResilienceOrchestrator`.
2. Exact five-class match found in `~/Downloads/URE.txt` (also a byte-identical
   flattened duplicate at
   `~/GSA-GATEWAY/governance-stack/ure-universal-resilience-engine-flattened.py`).
3. `URE.txt`'s own header is an LLM code-generation prompt
   ("*User prompt: URE (Universal Resilience Engine) module Domain: Nonlinear
   Dynamical Systems and Risk Modeling …*") followed by generated output. This is
   **prototype generation output, not repository code**. No tests, no repo
   history, no author, no production status.
4. A *different* candidate — an event-sourcing / hash-chain / governance-auditor
   implementation with a "Conservation_Kernel / OBSERVE-PERCEIVE" header — was
   found in `~/.claude/paste-cache/52b69e01b9f6fc68.txt` (mtime 12:15, *after*
   this prompt's 12:13). It shares none of the five class names and is
   **set aside as belonging to a separate investigation**.

Confidence in this identification: **HIGH** (exact five-symbol match, no
competing artifact). If it is wrong, the rest of this document is void.

A faithful re-expansion of the candidate was reconstructed to
`scratchpad/ure_candidate.py` and executed; all empirical results below are
captured from that run.

Per the candidate's own provenance vacuum: **architectural conclusions are HIGH
confidence; implementation-level conclusions are MEDIUM** (no supplied tests or
repo provenance to check against).

---

## 1. Executive Verdict

**The candidate reveals no missing capability in OBSERVE.** Every mechanism it
contains, OBSERVE already implements — and implements more soundly. The candidate
is a generated prototype whose regime classifier is an admitted mock, whose
"Lyapunov energy" is dimensionally incoherent, whose composite risk saturates to
1.0 under ordinary load, and whose domain (service backlog / dropout / reentry)
is call-centre operations, not clinical vitals — a domain already covered by
`sentinel_os/telemetry_pipeline.py` in the vendored stack.

**VERDICT: REJECT the implementation. HARVEST four tests / invariants.**

The one architecturally useful thing the candidate surfaces, it surfaces by
*failing*: OBSERVE binds no configuration/calculation version into its decision
provenance, so a `FusedVerdict` is not independently replayable. That is a **new
invariant revealed by failure analysis**, not a capability the candidate
contributes.

Secondary finding, outside the candidate's scope but directly on the governing
question: OBSERVE's *canonical* top-level source file
`observe_clinical_risk_source.py` does not parse (flattened / unreconstructed).
The mature engine actually runs only as a **vendored copy of another repo's
file**, `sentinel_os/observe_consolidated.py`. "BETTER OBSERVE" starts there, not
with resilience math.

---

## 2. Current OBSERVE Architecture (verified, not from README)

OBSERVE is a **pediatric clinical vitals risk-assessment engine**. Two source
lineages exist in the repo:

| Artifact | State | Role |
|---|---|---|
| `observe_clinical_risk_source.py` | **Does not parse** — entire file flattened to one physical line (`SyntaxError`) | Nominal canonical source |
| `observe_clinical_risk_adapter.py` | Parses; GSA "module registry" wrapper; runs its `__main__` | Adapter over a reduced 3-adapter pipeline |
| `clinical_signal_validator_adapter.py` | Parses, runs | Salvaged standalone adapter (concreteness check on signal text) |
| `sentinel_os/observe_consolidated.py` (1174 lines) | **Parses, runs, 82 vendored tests pass** | The actual mature engine — a vendored copy, not OBSERVE-owned |
| `imports/living-memory/corpus/Observe_Clinical_AI_System_Consolidated_V2.py` | duplicate of the above | import residue |

Pipeline (from the consolidated engine, `sentinel_os/observe_consolidated.py`):

```
VitalsSnapshot (frozen dataclass, physical-bounds validated)
      -> validate_vitals / VITALS_PHYSICAL_BOUNDS   (nonfinite / out-of-range faults)
      -> RiskAdapters ensemble  (heuristic, bayesian, trajectory, drift,
                                 behavioral, adversarial, physiological)
             each -> RiskOutput{risk_score, confidence, regime_classification(dist),
                                triggered_rules, abstained}
      -> BayesianFusion.fuse            (observe_consolidated.py:659)
             confidence-weighted risk; abstained engines excluded from fusion;
             true Shannon entropy in BITS over fused regime dist  (:685)
      -> OperationalRegime argmax  {STABLE, CAUTION, WARNING, CRITICAL}   (:40)
      -> EscalationPolicy         (:719) escalation_locked cooldown / hysteresis (:728)
      -> FusedVerdict{risk, regime, confidence, entropy, active_engines,
                      audit_hash, decision_fingerprint, escalation_required}
      -> ImmutableAuditLedger  (:769)     hash-chained audit entries
      -> ProvisionalStore      (:941) + reconcile(patient, job, final)  (:966)
```

Capabilities already present, with locations:

| Capability | Location |
|---|---|
| Telemetry / signal ingestion + typed contract | `VitalsSnapshot`, `observe_consolidated.py:57` |
| Physical-plausibility validation | `validate_vitals` / `VITALS_PHYSICAL_BOUNDS`, `observe_clinical_risk_source.py` §"SAFETY"; adapter `VitalValidationModule` |
| Baseline-relative drift (per signal) | `RiskAdapters.drift`, `observe_consolidated.py:327` — z-score of baseline vs. rolling-history mean/σ, None-guards, `critical_floor=0.02`, named `DRIFT_SIGMA_THRESHOLD` |
| Adversarial / stuck-sensor detection | `RiskAdapters.adversarial` (streak detection) |
| Regime classification as **distribution**, not label | `regime_distribution()`, `FusionEngineModule`, `observe_consolidated.py` |
| Shannon entropy over regime distribution (bits) | `BayesianFusion.fuse`, `observe_consolidated.py:685` |
| Composite risk via principled fusion | `BayesianFusion.fuse` — confidence-weighted, abstention-aware, `:659` |
| Entropy-driven adaptive computation | engine selection gated on `recent_entropy > 0.6`, `observe_consolidated.py:1047-1052` |
| Escalation as a **derived indicator** (not an action) | `FusedVerdict.escalation_required`; `EscalationPolicy` hysteresis `:719` |
| Oscillation suppression | `escalation_locked` 5-min cooldown, per-patient, LRU-evicted `:728, :1030` |
| Epistemic humility / abstention | `RiskOutput.abstained`; abstained engines excluded from fusion `:666` |
| Provenance / audit | `fingerprint()` SHA-256 canonical-JSON; `decision_fingerprint`; `ImmutableAuditLedger` hash chain `:769` |
| Provisional-vs-final reconciliation | `ProvisionalStore.reconcile`, `:966` |

**Baseline test result (Phase 1):** OBSERVE ships **no OBSERVE-owned test
suite**. The vendored suite
`pytest sentinel_os/test_observe_consolidated.py sentinel_os/test_integration_consolidated.py`
reports **82 passed in 0.40s**. The consolidated engine's `__main__` demo runs
and self-reports `Audit chain valid: True`. Local checkout is detached at
`d44e15e`; `origin/main` is at `2b660b9` (a README added by a concurrent
process) — this artifact therefore sits on a slightly stale tree.

---

## 3. Candidate Architecture Decomposition

Domain terminology stripped, the candidate is:

| Component | Mechanism (what it actually is) | Class |
|---|---|---|
| `SystemResilienceConfig` | A flat bag of ~26 float constants + one weight dict. 15 of the scalars (`novelty_uncertainty_weight`, `complexity_uncertainty_weight`, `demand_shock_dampening_factor`, `regime_backlog_*_weight`, `stability_*_threshold`, `dropout_threshold_floor`, …) are **never read anywhere in the candidate**. | dataclass |
| `SystemMetricsTelemetry` | 11 service-operations metrics (backlog_depth, dropout_rate, reentry_rate, escalation_rate, containment_efficiency, processing_latency, determinism_index, …). Not clinical. | dataclass |
| `TelemetryIngestionPipeline.parse_vector` | `dict -> dataclass` with `.get(k, 0.0/1.0)` defaults. No validation. | class |
| `StabilityMonitor.calculate_system_energy` | `0.5 · Σ wᵢ (currentᵢ − baselineᵢ)²` over the weight dict. Labelled "Lyapunov-style". | class |
| `SystemRegimeClassifier.classify_current_regime` | Returns a **hardcoded** 6-key dict with a single `if backlog_depth < 10` branch. Comment: *"Simulated distribution mapping function."* | class |
| `calculate_shannon_entropy` | `−Σ p ln p` (nats), computed on whatever dict is passed — normalized or not. | function |
| `IntegratedResilienceOrchestrator.evaluate_composite_risk` | `min(1, (dropout·2 + escalation·1.5 + reentry·1.5 + backlog·0.01) · max(0.5, 1 + H·0.15))`. Takes a `baseline` arg and **ignores it**. | class |
| `IntegratedResilienceOrchestrator.run_diagnostic_sweep` | Pipeline: classify → energy → risk → 3-way status label (`RISK_INCREASING` / `REGRESSIVE` / `NEUTRAL`). | class |

Per-component classification:

| Component | Classification |
|---|---|
| `SystemResilienceConfig` | NOT APPROPRIATE (semantic dumping ground; 15 dead constants) |
| `SystemMetricsTelemetry` | NOT APPROPRIATE FOR OBSERVE (wrong domain); ALREADY PRESENT elsewhere (`sentinel_os/telemetry_pipeline.py`) |
| `TelemetryIngestionPipeline` | UNSOUND (silent 0.0 defaulting → missing data reads as healthy) |
| `StabilityMonitor` (energy) | UNSOUND (dimensionally incoherent, scale-dominated, dead weight key) |
| `SystemRegimeClassifier` | REJECT (admitted mock; 4 of 6 regimes unreachable) |
| `calculate_shannon_entropy` | ALREADY PRESENT / candidate variant UNSOUND (nats vs bits; unnormalized input) |
| `evaluate_composite_risk` | NO MATERIAL IMPROVEMENT (saturates; ignores baseline; uncalibrated) — OBSERVE's fusion is superior |
| `run_diagnostic_sweep` orchestrator | ALREADY PRESENT (`ObserveClinicalEngine.evaluate`, more mature) |

---

## 4. Capability Comparison (Phase 10)

| Candidate capability | Actual OBSERVE location | Existing behavior | Gap? | Candidate improvement | Evidence |
|---|---|---|---|---|---|
| Typed telemetry contract | `VitalsSnapshot` `observe_consolidated.py:57` | frozen dataclass + physical-bounds validation | No | none — candidate skips validation | candidate `parse_vector` has no bounds check |
| Ingest raw dict → typed | `VitalValidationModule.process` (adapter) | validates, records fault count | No | negative — silent `.get(k,0.0)` | harness run **(D)**: missing telemetry → `NEUTRAL` |
| Baseline-relative drift | `RiskAdapters.drift` `:327` | per-signal z-score vs rolling mean/σ, None-guards, critical floor, human-readable rationale strings | No | negative — collapses multi-signal drift into one scale-dominated scalar | harness run **(B)**: 10-unit backlog move alone → `REGRESSIVE` |
| Regime classification | `regime_distribution()` + `FusionEngineModule` | score→distribution, argmax→`OperationalRegime` | No | none — candidate's is a hardcoded mock | candidate comment "Simulated distribution mapping function"; harness **(E)**: only 2 of 6 regimes reachable |
| Shannon entropy of regime dist | `BayesianFusion.fuse` `:685` | true Shannon in **bits**, feeds adaptive engine selection `:1047` | No | negative — nats, on an unnormalized dict, folded into risk | harness **(A)**: surge distribution sums to **0.80**, entropy taken anyway |
| Composite risk score | `BayesianFusion.fuse` `:659` | confidence-weighted, abstention-aware, non-saturating | No | negative — saturates, ignores `baseline` | harness **(C)**: backlog=100 alone → risk `1.0`; **(G)**: baseline arg unused |
| "Energy" / instability scalar | (no direct equivalent — by design) | OBSERVE keeps per-signal drift triggers instead | No (deliberate) | negative — `Σ wᵢΔᵢ²` over unlike units | harness **(A)**: energy `4622.7` vs threshold `0.10` |
| Escalation indicator | `FusedVerdict.escalation_required`, `EscalationPolicy` `:719` | derived boolean + hysteresis/cooldown | No | negative — candidate has no hysteresis; would oscillate | `EscalationPolicy.escalation_locked` `:728` |
| Orchestration pipeline | `ObserveClinicalEngine.evaluate` `:1074` | full pipeline incl. audit chain + provisional store | No | none | — |
| Centralized config object | *absent* — constants inline (`PEDIATRIC_NORMS`, `DRIFT_SIGMA_THRESHOLD`, fusion weights, `regime_distribution` cutpoints) | hardcoded, unversioned, not bound to provenance | **Partial** (see §10) | candidate has a config object but **does not version it either** | candidate `SystemResilienceConfig` has no `version` / hash field |

---

## 5. Information-Preservation Assessment (Phase 3)

The candidate is a textbook case of the anti-pattern the brief warns against.

- `run_diagnostic_sweep` emits **one enum label + one scalar risk + one scalar
  energy**. The underlying per-metric deviations, the (mock) distribution, and
  the entropy are computed and then discarded into `DiagnosticEvaluationSummary`
  fields that no consumer path uses.
- OBSERVE **preserves the structure**: `FusedVerdict` carries the full
  `regime` distribution history via per-engine `RiskOutput.regime_classification`,
  `entropy` as an *independent* dimension, `triggered_rules` as
  human-readable evidence strings (`"O2_DRIFT: baseline 91% is 2.34SD from mean
  94.1%"`), `active_engines`, and `abstained` flags. A downstream reader can see
  *why*, not just *how much*.
- Candidate's `composite_risk` **multiplies** entropy into the risk scalar
  (`entropy_adjustment`). This destroys the ability to distinguish "high risk,
  confident" from "moderate risk, model disagreement". OBSERVE keeps them
  orthogonal.

**Conclusion:** the scalar representation is *not* superior here. OBSERVE already
does the right thing (preserve dimensions, derive summaries only in fusion, keep
entropy separate). Adopting any candidate output would be a regression in
information preservation.

---

## 6. Epistemic / Semantic Assessment (Phase 4)

| Candidate output | Claims to be | Actually is | OBSERVE handles this how |
|---|---|---|---|
| `SystemMetricsTelemetry.*` | MEASURED | MEASURED *if supplied*; silently ESTIMATED-as-zero if absent | `validate_vitals` raises faults; adapters `abstain` when data absent |
| `calculate_system_energy` | DERIVED | DERIVED but uninterpretable (mixed units) | OBSERVE emits per-signal `z-score` DERIVED values with units in the rationale string |
| `RegimeClassificationProfile.probability_distribution` | CLASSIFIED (probabilistic) | **FABRICATED** — hardcoded constants, not inferred from input | `regime_distribution(score)` is an explicit deterministic mapping, documented as such, not dressed as a probability model |
| `confidence_score` | ESTIMATED confidence | just `max(distribution.values())` — a tautology of the mock | `RiskOutput.confidence` is per-engine and data-completeness-aware (`0.9 if age_months is not None else 0.7`) |
| `composite_risk_score` | DERIVED risk | DERIVED but saturated / baseline-blind | `BayesianFusion` fused risk, confidence-weighted |
| `ClassificationResult.RISK_INCREASING` | CLASSIFIED state | threshold trip on a saturated scalar | `OperationalRegime` argmax over a real fused distribution |

The candidate's central epistemic sin: **a hardcoded dict is presented through
the type system as a "probability distribution" with "confidence" and
"entropy".** An inferred-looking artifact that was never inferred. OBSERVE's
`regime_distribution()` avoids this by being honestly named and documented as a
fixed score→shape mapping.

No candidate output crosses into governance/decision authority — the terminal
outputs are labels and a rationale string, which sit on the OBSERVE side of the
Phase 7 boundary. (So does OBSERVE's own `escalation_required`: a derived
boolean indicator, not an act.)

---

## 7. Mathematical Assessment (Phase 5)

### A. "Lyapunov-style" energy — `0.5 · Σ wᵢ (Δmetricᵢ)²`

| Test | Result |
|---|---|
| Mathematically valid as an expression | Yes (it computes a number) |
| Dimensionally consistent | **No.** Sums `dropout_rate²` (dimensionless, 0–1) + `backlog_depth²` (count², unbounded) + `escalation_rate²` with a single set of weights. Adding a squared ratio to a squared count is meaningless. |
| Normalization / scale handling | **None.** harness **(A)**: demo scenario → energy **4622.7** against `energy_threshold = 0.10`. The threshold is unreachable-downward for any real input; the classifier's `REGRESSIVE` branch is effectively always-on once any count-valued metric moves. |
| Scale sensitivity | **Catastrophic.** harness **(B)**: `backlog_depth` 2→12 alone (a trivial move) → energy 250 → `REGRESSIVE`. Rescaling `backlog_depth` to a fraction would silently change every classification. |
| Baseline sensitivity | Uses baseline correctly *here*, but the sibling `evaluate_composite_risk` takes `baseline` and ignores it (harness **(G)**). |
| Dead term | `evaluation_weights` key `"normalized_latency"` ≠ dataclass attr `processing_latency`; `getattr(..., 0.0)` on both sides → the latency term is **always 0** (harness **(F)**). |
| "Lyapunov" justified? | **No.** A Lyapunov function requires a dynamical system, a fixed point, and a monotone-decrease argument along trajectories. This is a weighted squared-error from a static baseline snapshot. The name is decoration. |
| OBSERVE equivalent | `RiskAdapters.drift` z-score — dimensionless by construction (divides by σ), per-signal, interpretable. Strictly better. |

Verdict: **mathematically valid ≠ statistically useful ≠ architecturally useful ≠
empirically validated.** This measure is only the first.

### B. Shannon entropy — `−Σ p ln p`

- Input validity: harness **(A)** — in the `backlog_depth ≥ 10` branch the mock
  distribution is `{.10,.60,.05,.02,.02,.01}` which **sums to 0.80**, not 1.0.
  Entropy is computed on it regardless. Not a probability distribution.
- Units: natural log (nats). OBSERVE uses `log2` (bits) at `observe_consolidated.py:685`.
  Mixing the two across a system is a latent bug.
- Normalization: not normalized; `H_max` for 6 classes is `ln 6 ≈ 1.79`, never
  divided out, so the value isn't comparable across differently-sized class sets.
- What it represents: nominally classifier uncertainty — but the classifier is a
  mock, so the entropy is near-constant and carries **no information**.
- Should it influence risk? The brief says be skeptical; here the answer is
  clearly **no** — `entropy_adjustment` multiplies a near-constant ~1.13 into
  every risk score, i.e. it is a disguised constant. OBSERVE keeps entropy as an
  independent reported dimension and as an adaptive-compute trigger, never as a
  risk multiplier. OBSERVE's design is correct.

### C. Composite risk

- Normalization / units: `backlog_depth · 0.01` adds a count-scaled term to
  rate-scaled terms. harness **(C)**: `backlog_depth = 100`, everything else 0 →
  `base = 1.0` → risk pinned at **1.0** with zero failure signal present.
- Saturation: `min(1.0, …)` masks the fact that `base` routinely exceeds 1.0, so
  the score is a **ceiling indicator**, not a graded risk.
- Weighting: uncalibrated magic numbers (2.0 / 1.5 / 1.5 / 0.01). No source, no
  lifecycle, no validation.
- Double-counting: `escalation_rate` feeds both `evaluate_composite_risk` and
  (via the mock) the regime distribution and thus the `entropy_adjustment`.
- **Should these dimensions be collapsed at all?** No. `dropout` / `backlog` /
  `reentry` / `escalation` answer different operational questions. OBSERVE's
  practice — keep `triggered_rules` + per-engine outputs + a *fused* score whose
  provenance is inspectable — is the better model.

---

## 8. Adversarial Findings (Phase 9) — all empirically confirmed

Harness: `scratchpad/ure_candidate.py` (faithful re-expansion of the flattened
candidate; `Optional` in an annotation is fine under
`from __future__ import annotations`, so the candidate **does execute** — the
weakness is semantic, not a syntax error).

| # | Attack | Observed failure | Class |
|---|---|---|---|
| A | Documented demo inputs | energy `4622.7` vs threshold `0.10`; risk saturates at `1.0`; regime distribution sums to `0.80` | threshold meaningless; risk non-graded; invalid distribution |
| B | Scale mismatch — `backlog_depth` +10, nothing else | `REGRESSIVE` | false positive; scale-dominated energy |
| C | Single-dimension load — `backlog_depth = 100`, zero failures | risk `1.0`, `RISK_INCREASING` | false positive; saturation |
| D | Missing telemetry — default-constructed `current` | `NEUTRAL`, risk `0.0` | **silent false negative** — absent data reads as perfect health |
| E | Regime coverage — sweep `backlog_depth` 0–1000 | only `STABLE`, `SURGE` ever dominant | 4 of 6 regimes dead code |
| F | Config key typo — `normalized_latency` vs `processing_latency` | latency jump 1→999 contributes `0.0` to energy | dead term; silent |
| G | Baseline poisoning irrelevance | `evaluate_composite_risk(baseline=…)` identical for zero vs surge baseline | baseline argument ignored |
| — | Impossible values (negative rates, `NaN`) | no guard; `NaN` propagates through `min()` silently | no input validation |
| — | Oscillation | no hysteresis/cooldown anywhere; a metric hovering at a threshold flaps the label every sweep | unstable classification |
| — | Stale config / version drift | `SystemResilienceConfig` has no identity; two runs with different constants are indistinguishable in output | no reproducibility |

Contrast: OBSERVE handles D (abstention + faults), E (all four regimes reachable
by `regime_distribution`), G (drift explicitly uses baseline), oscillation
(`EscalationPolicy` cooldown `:728`), and validation (`validate_vitals`).

---

## 9. Existing OBSERVE Capabilities (that make the candidate redundant)

- Ensemble risk adapters with per-engine confidence + abstention —
  `observe_consolidated.py:161` onward.
- Confidence-weighted Bayesian fusion, abstention-aware — `:659`.
- True Shannon entropy (bits) as an independent dimension — `:685`.
- Entropy-gated adaptive computation — `:1047`.
- Baseline z-score drift, per signal, None-safe, with rationale strings — `:327`.
- Adversarial / stuck-sensor streak detection — `RiskAdapters.adversarial`.
- Regime as distribution then argmax over `{STABLE,CAUTION,WARNING,CRITICAL}` — `:40`, `regime_distribution()`.
- Escalation as derived indicator + hysteresis/cooldown, per-patient, LRU-evicted — `EscalationPolicy` `:719`, `:1030`.
- SHA-256 canonical-JSON `decision_fingerprint` + hash-chained `ImmutableAuditLedger` — `fingerprint()`, `:769`.
- Provisional verdict + later `reconcile()` against ground truth — `ProvisionalStore` `:941, :966`.

---

## 10. Genuine Gaps

### G-1 (minor, real): Provenance does not bind parameter/calculation version

`FusedVerdict.decision_fingerprint` hashes *vitals + risk + regime + entropy*. It
does **not** hash the parameter set that produced them (`PEDIATRIC_NORMS`,
`DRIFT_SIGMA_THRESHOLD`, the `regime_distribution` cutpoints, fusion weights,
engine-selection entropy threshold `0.6`). Those constants are inline literals
across `observe_consolidated.py` with no version identity. Two builds with
different cutpoints produce fingerprints that collide on identical inputs — the
verdict is **not independently replayable**.

This is a **new invariant revealed by the candidate's failure analysis**, not a
capability the candidate provides — the candidate centralizes constants into
`SystemResilienceConfig` but attaches no version/hash to it and does not fold it
into any output. It aligns with the existing AMC-1.0 "evidence immutability /
reproducibility" methodology note and the `sentinel_os` cassette-versioning
precedent (`docs/CHANGELOG.md`, 2026-07-23: "*binding enforcement correctly
refuses a changed hash under an old version*").

### G-2 (not resilience-related, but on the governing question): canonical source is broken

`observe_clinical_risk_source.py` does not parse. The engine that works is a
vendored copy (`sentinel_os/observe_consolidated.py`) of a file another repo
owns. OBSERVE has no test suite of its own. This is the actual thing standing
between OBSERVE and "better" — and it is confirmed by the
`project_ecosystem_readme_implementation_gap` pattern.

### G-3 (concept only, do not build from candidate): multivariate baseline deviation

OBSERVE's drift is per-signal. A single cross-signal deviation summary *could* be
useful. But (a) the candidate's implementation is unsound, and (b) OBSERVE's
per-signal triggers with rationale strings are more information-preserving. If
ever wanted, it must be dimensionless (Mahalanobis distance over a covariance
estimate, not `Σ wΔ²`) and must not replace the per-signal triggers. **Not
justified on current evidence.**

---

## 11. Redundant / Inferior Capabilities (candidate vs OBSERVE)

Everything in §3's classification table marked ALREADY PRESENT, NO MATERIAL
IMPROVEMENT, UNSOUND, or REJECT. In short: telemetry contract, ingestion, drift,
regime classification, entropy, composite risk, orchestration, escalation
indicator — all present in OBSERVE and all implemented better there.

---

## 12. Test and Invariant Harvest

Even though the candidate is rejected, its failure modes are worth locking down
in OBSERVE. **T-x = a test OBSERVE should add; I-x = an invariant.**

| ID | Statement | Origin | Priority |
|---|---|---|---|
| I-1 | Any distribution passed to an entropy calculation MUST sum to 1 ± 1e-6 before entropy is taken (assert, not silent). | candidate harness (A): mock dist summed 0.80 | High |
| T-1 | Entropy unit test: a uniform 4-class regime distribution yields exactly `2.0` (bits). Guards against a future `ln` vs `log2` regression. | candidate mixed nats/bits | High |
| T-2 | **Missing / `None` telemetry field MUST NOT resolve to a "healthy" value that lowers risk.** A dropped `oxygen_saturation` → abstention or fault, never `stable`. | candidate harness (D): absent data → `NEUTRAL` | High |
| T-3 | Scale-invariance: multiplying any single input signal's unit scale (e.g. expressing a rate per-1000 instead of per-1) MUST NOT change the emitted regime. | candidate harness (B): 10-unit move flipped the label | High |
| T-4 | Non-saturation / monotonicity: fused `risk_score` is strictly `< 1.0` for at least one "elevated but not maximal" fixture, and monotone in each contributing signal holding others fixed. | candidate harness (C): risk pinned at 1.0 | Medium |
| T-5 | Regime reachability: every member of `OperationalRegime` is the argmax for at least one constructed `VitalsSnapshot`. | candidate harness (E): 4/6 unreachable | Medium |
| I-2 | A claimed baseline-relative quantity MUST change when the baseline changes (property test over `RiskAdapters.drift`). | candidate harness (G): baseline arg ignored | Medium |
| I-3 (**from G-1**) | `decision_fingerprint` MUST incorporate a hash of the full active parameter set; a replay with the same inputs and a changed parameter set MUST produce a different fingerprint, and a replay with identical inputs + parameters MUST reproduce the verdict byte-for-byte. | candidate failure analysis (config has no identity) | High — strategic |
| T-6 | `NaN` / `±inf` / negative rate in any input is rejected at validation, never propagated through `min()`/`max()`. | candidate: no input guards | Medium |

I-3 is the strategically valuable one: it is not a candidate test, it is an
invariant the candidate's *absence of versioning* exposed.

---

## 13. Architectural Disposition

| Component | Disposition |
|---|---|
| `SystemResilienceConfig` | **NOT APPROPRIATE** (dumping ground). Do not port. |
| `SystemMetricsTelemetry` | **NOT APPROPRIATE FOR OBSERVE** (wrong domain). |
| `TelemetryIngestionPipeline` | **REJECT** (silent-default anti-pattern → T-2). |
| `StabilityMonitor` / energy | **REJECT** (unsound; concept covered by `drift` → T-3). |
| `SystemRegimeClassifier` | **REJECT** (mock). |
| `calculate_shannon_entropy` | **ALREADY PRESENT** (`:685`); candidate variant **UNSOUND** → I-1, T-1. |
| `evaluate_composite_risk` | **NO CHANGE** — OBSERVE's fusion is superior → T-4, I-2. |
| `IntegratedResilienceOrchestrator` | **ALREADY PRESENT** (`ObserveClinicalEngine.evaluate`). |
| Config-versioning concept | **HARVEST INVARIANT** (I-3) — not from candidate code, from its failure analysis. |
| Failure modes A–G | **HARVEST TESTS** T-1…T-6, I-1…I-2. |

---

## 14. Recommended Change, If Any

**No resilience capability should be added to OBSERVE.** (Phase 14 gate: changing
OBSERVE to absorb any candidate mechanism would *reduce* correctness and
information preservation.)

The smallest justified change, if the team wants one, is **I-3 only**: extend the
existing `decision_fingerprint` computation in
`RegimeClassificationModule.process` / `ObserveClinicalEngine.evaluate` to hash a
canonical serialization of the active parameter set alongside the inputs, and add
the replay test. This is a ~15-line change to one existing function plus a test
file — it introduces **no new abstraction** (no config system, no telemetry
model, no orchestration layer), reuses the SHA-256 canonical-JSON helper already
present, and directly serves reproducibility.

The T-1…T-6 / I-1…I-2 harvest is independent and can land as a new
`test_observe_invariants.py` — OBSERVE's first owned test file — regardless of
the I-3 decision.

Neither is a resilience integration. Both are hygiene the candidate happened to
illuminate.

---

## 15. Historical / Reference Value

| Aspect | Rating | Reason |
|---|---|---|
| Architectural knowledge | **SAFE TO DISCARD** | Nothing OBSERVE's consolidated engine doesn't already express better. |
| Mathematical insight | **SAFE TO DISCARD** | "Lyapunov energy" and entropy-as-risk-multiplier are anti-patterns, not insights. |
| Experiments / failure discoveries | **ARCHIVE** — *this document*, not the code | The adversarial findings (A–G) are the only residue worth keeping; they now live here. |
| Tests / invariants | **PRESERVE** — as §12, transplanted into OBSERVE | — |
| Domain-independent mechanism | none | The "universal" framing is unearned; it is call-centre ops math with generic names. |

The candidate `.py` itself: discard. `~/Downloads/URE.txt` and the
`GSA-GATEWAY/governance-stack/ure-*-flattened.py` duplicate can be deleted once
§12 is captured; they are generation output, not history.

---

## 16. Unresolved Questions

1. **Candidate identity** — confirmed only by exact class-name match. If the user
   intended a *different* artifact, this assessment must be re-run. (Confidence
   HIGH but not verified against a user statement.)
2. **Which OBSERVE source is canonical** — `observe_clinical_risk_source.py`
   (broken) vs `sentinel_os/observe_consolidated.py` (works, vendored) vs the
   `imports/…/Consolidated_V2.py` copy. The repo does not say. **UNKNOWN** —
   needs an owner decision, and it is the real blocker for "BETTER OBSERVE".
3. **Is OBSERVE meant to consume operational/service telemetry at all**, or is it
   strictly clinical-vitals? The candidate assumes the former; the codebase is
   entirely the latter. If OBSERVE is ever meant to observe *its own* runtime
   health, that is a separate, legitimate design question — but it belongs to
   `sentinel_os` observability (`metrics_prometheus.py`, `circuit_breaker.py`,
   `telemetry_pipeline.py`), which already covers it.
4. **G-1 scope** — does I-3 need to cover the vendored `sentinel_os` parameters
   too, or only OBSERVE-owned constants? Depends on (2).

---

## 17. Final Recommendation

**REJECT the candidate implementation in full. HARVEST the §12 tests/invariants.
Do not integrate, adapt, reimplement, or relocate any candidate component.**

The candidate answers "MORE OBSERVE", not "BETTER OBSERVE". The genuine path to a
better OBSERVE runs through G-2 (reconstruct the canonical source, give OBSERVE an
owned test suite) and I-3 (bind parameter version into decision provenance) —
neither of which is a resilience feature.

---

# EXECUTIVE VERDICT

**VERDICT:** REJECT (implementation) + HARVEST (tests/invariants)

**CONFIDENCE:** HIGH on the architectural conclusion; MEDIUM on
implementation-level specifics (candidate supplied no tests or repo provenance).

**GENUINELY MISSING CAPABILITY:** NO — for resilience/operational-state.
PARTIALLY — a provenance *invariant* (parameter-version binding, I-3) is missing,
but the candidate does not provide it; failure analysis of the candidate reveals
it.

**PRIMARY REASON:** OBSERVE already implements every mechanism the candidate
contains — telemetry ingestion, validation, baseline drift, regime-as-
distribution, Shannon entropy, composite risk via principled fusion, escalation
as a derived indicator, provenance hashing, abstention — and implements each more
soundly. The candidate's regime classifier is an admitted mock, its "Lyapunov
energy" is dimensionally incoherent (energy 4622 vs threshold 0.10), its
composite risk saturates to 1.0 on pure queue depth with zero failure signal,
and its domain is service operations, not clinical vitals. Integrating any part
would reduce OBSERVE's information preservation and correctness.

---

# CAPABILITY MATRIX

| Candidate | Disposition | Existing OBSERVE Capability | Genuine Gap? | Information Value | Risk | Destination |
|---|---|---|---|---|---|---|
| `SystemResilienceConfig` | NOT APPROPRIATE | inline constants across `observe_consolidated.py` | No (but see I-3) | Low (15 dead fields) | Med (dumping ground) | nowhere |
| `SystemMetricsTelemetry` | NOT APPROPRIATE | `VitalsSnapshot` `:57`; `sentinel_os/telemetry_pipeline.py` for ops | No | Low (wrong domain) | Low | nowhere (ops → sentinel_os, already covered) |
| `TelemetryIngestionPipeline` | REJECT | `VitalValidationModule` / `validate_vitals` | No | Negative (silent defaults) | High (false negatives) | nowhere → T-2 |
| `StabilityMonitor` (energy) | REJECT | `RiskAdapters.drift` `:327` | No | Negative (scalar collapse) | High (scale-dominated) | nowhere → T-3 |
| `SystemRegimeClassifier` | REJECT | `regime_distribution()` + `FusionEngineModule` | No | None (mock) | High (fabricated probabilities) | nowhere → T-5 |
| `calculate_shannon_entropy` | ALREADY PRESENT / UNSOUND | `BayesianFusion.fuse` `:685` (bits) | No | Neutral | Med (nats vs bits) | nowhere → I-1, T-1 |
| `evaluate_composite_risk` | NO CHANGE | `BayesianFusion.fuse` `:659` | No | Negative (saturates, baseline-blind) | Med | nowhere → T-4, I-2 |
| `IntegratedResilienceOrchestrator` | ALREADY PRESENT | `ObserveClinicalEngine.evaluate` `:1074` | No | None | Low | nowhere |
| parameter-version provenance | HARVEST INVARIANT | `decision_fingerprint` (inputs only) | **Partial (I-3)** | High | Low | **OBSERVE** — extend existing fingerprint fn |

---

# KEEP

- The **adversarial findings A–G** (this document, §8) as the archived residue of the candidate.
- **I-3**: parameter/calculation-version must be bound into decision provenance for replayability.
- **I-1**: entropy inputs must be normalized distributions.
- **T-2**: missing telemetry must never read as healthy.
- **T-3**: regime classification must be scale-invariant.

# REJECT

- "Lyapunov-style" `0.5 Σ wΔ²` energy over mixed-unit metrics.
- Entropy as a risk multiplier (`entropy_adjustment`).
- Hardcoded "probability distribution" classifiers presented as inferred.
- `.get(key, 0.0)` telemetry ingestion (missing → healthy).
- Composite-risk scalar as the primary output (collapses independent dimensions).
- `SystemResilienceConfig` as a shape (26 fields, 15 unused).
- The `SystemMetricsTelemetry` operational-metrics vocabulary inside OBSERVE.

# REIMPLEMENT

- Nothing. No candidate capability survives that OBSERVE lacks. (G-3 multivariate
  deviation is a concept to consider *independently* someday, with Mahalanobis
  distance, never from this code, and never replacing per-signal triggers.)

# TEST / INVARIANT HARVEST

- I-1, I-2, I-3, T-1, T-2, T-3, T-4, T-5, T-6 as specified in §12.
- Land as `sentinel_os/test_observe_invariants.py` (or repo-root, pending the §16.2 ownership decision) — **OBSERVE's first owned test file.**

# NO CHANGE

- Fusion (`BayesianFusion.fuse` `:659`), entropy (`:685`), drift (`:327`),
  regime classification (`regime_distribution`), escalation policy /
  hysteresis (`:719`), audit ledger (`:769`), provisional store (`:941`),
  adaptive engine selection (`:1047`). All adequate or superior to the candidate.

# ARCHITECTURAL DESTINATION

| Surviving concept | Destination | Why |
|---|---|---|
| I-3 parameter-version provenance | **OBSERVE** — extend `decision_fingerprint` in `RegimeClassificationModule.process` / `ObserveClinicalEngine.evaluate` | Reuses existing SHA-256 canonical-JSON helper; no new abstraction; serves reproducibility the repo already values (cassette version binding, `docs/CHANGELOG.md`). |
| I-1/T-1…T-6 test harvest | **OBSERVE** test suite | Locks the candidate's failure modes out of OBSERVE permanently. |
| Operational self-telemetry (if ever wanted) | **sentinel_os** observability (`metrics_prometheus.py`, `telemetry_pipeline.py`, `circuit_breaker.py`) | Already the owner; OBSERVE is a clinical judgment layer, not a service-health monitor. |
| The candidate `.py` / `URE.txt` / flattened duplicate | **discard** after §12 capture | Generation output, not history. |

---

# CORE ARCHITECTURAL FINDING

**The candidate revealed no missing capability in OBSERVE. It is another — and
weaker — implementation of capabilities OBSERVE already has: telemetry ingestion,
validation, baseline drift, regime classification as a distribution, Shannon
entropy, composite risk, orchestration, and escalation-as-indicator.**

What it *did* usefully expose, by failing, are hygiene gaps that are not
resilience features at all:

1. OBSERVE's decision provenance hashes inputs but not the parameter set that
   interpreted them — verdicts are not independently replayable (I-3).
2. OBSERVE has no owned test suite, and its nominal canonical source
   (`observe_clinical_risk_source.py`) does not parse; the working engine is a
   vendored copy of another repo's file (G-2).

"BETTER OBSERVE, WITH LESS UNNECESSARY COMPLEXITY" is served by fixing those two
things and adding nine invariant tests — and by adding **zero** new abstractions
from the candidate.

---

# RECOMMENDED NEXT STEP

Put the §16.2 question to the repo owner: **designate the canonical OBSERVE
source** (reconstruct `observe_clinical_risk_source.py` from
`sentinel_os/observe_consolidated.py`, or formally adopt the consolidated file as
OBSERVE-owned). Everything else — the I-3 provenance change and the §12 test
harvest — is blocked on knowing which file they land in. No resilience
integration work should be scheduled.

---

# Implementation status (post-authorization, 2026-08-27)

Candidate: **REJECTED**, as recommended. Nothing from the URE code was
integrated, adapted, or relocated. `~/Downloads/URE.txt` and
`GSA-GATEWAY/governance-stack/ure-universal-resilience-engine-flattened.py`
remain on disk for the user to discard; the only residue worth keeping (the
adversarial findings) is this document.

Three findings were fixed on branch `fix/resilience-assessment-findings`
(not committed / not pushed):

| Finding | Change | Files |
|---|---|---|
| **G-2** canonical source | `observe_consolidated.py` + `test_observe_consolidated.py` promoted to repo root as OBSERVE-owned; flattened `observe_clinical_risk_source.py` retired to `.broken`. Vendored `sentinel_os/observe_consolidated.py` kept in sync. | root (new), `observe_clinical_risk_source.py.broken` |
| **T-2 / T-6** input validation | `VITALS_PHYSICAL_BOUNDS` + `validate_vitals()` ported back from the retired source. `ObserveClinicalEngine.evaluate()` gates on it: a non-finite / out-of-range vital returns a `WARNING` verdict carrying `validation_faults` (never `STABLE`), and is written to the audit ledger as `clinical_assessment_rejected`. | `observe_consolidated.py` |
| **I-3** parameter provenance | Buried calibration literals hoisted to named module constants; declared in `PARAMETER_SET`; `PARAMETER_SET_VERSION` (SHA-256) added to `FusedVerdict` and every audit entry; `compute_decision_fingerprint(vitals, verdict)` added — deterministic, wall-clock-free, moves with the parameter version. Adapter-internal `score +=` increments are **not** yet hoisted (noted in code). | `observe_consolidated.py` |

Test harvest (§12) landed as `test_observe_invariants.py` — 23 property tests
(I-1, T-1, T-2/T-6, T-4, T-5, I-2, I-3). **OBSERVE's first repo-owned test file.**

Suites after the change: `test_observe_consolidated.py` + `test_observe_invariants.py`
= **99 passed**; vendored `sentinel_os` suite = **82 passed**.

Not done (out of scope / needs separate decision):
- Hoisting adapter-internal score weights into `PARAMETER_SET`.
- Reconciling the wider vendored `sentinel_os/` tree to a single source of truth.
- `origin/main` is ahead (`2b660b9`, README); this branch was cut from detached `d44e15e`. A rebase/merge is needed before any push.
