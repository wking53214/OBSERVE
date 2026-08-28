# OBSERVE — Clinical Scoring Reference

**Status: FOR CLINICAL REVIEW. Not yet reviewed by a pediatric clinician.**

This document is a complete, hand-extracted transcription of every threshold and
score weight in the OBSERVE pediatric vitals risk engine
(`observe_consolidated.py`), cross-checked against the source line by line. It
exists so that a pediatric intensivist / rapid-response medical director can
review the engine's clinical logic **against your institution's PEWS and the
pediatric early-warning evidence base** without reading Python.

No engine behavior changes with this document. If review finds a weight or
threshold wrong, that correction is a separate code change.

- Engine version at extraction: `main` @ `73eff68`
- Every value below is quoted with its `observe_consolidated.py` line number.
- Values are grouped at the end into **CLINICAL CALIBRATION** (please review) vs
  **STRUCTURAL** (changing these alters engine mechanics/statistics, not clinical
  sensitivity in a simple way — flag for engineering, not clinical tuning).

---

## 0. Observed engine behaviors that need clinical sign-off

These are **real end-to-end runs of the current engine**, not hypotheticals.
They are not necessarily defects — whether they are acceptable depends entirely
on your clinical model, the reading cadence, and how OBSERVE sits alongside a
nurse's own PEWS. But a reviewer must see them.

**"page" below = `escalation_required` = a new alert/page is raised.**

### 0.1 Sub-threshold multi-system abnormality can sit at STABLE indefinitely

| # | Patient (age) | Vitals, held | Engine result |
|---|---|---|---|
| A | infant (6 mo) | SpO2 **89%**, HR **155** (norms: <90, >150) | **STABLE, never pages.** Risk 0.54 on reading 1, then **drops to 0.40** and holds. |
| B | infant (6 mo) | HR **78** — isolated bradycardia (norm low 90) | **STABLE, never pages.** Risk 0.30 → 0.25. |
| C | child (4 y) | SpO2 **90%**, HR **135**, RR **36** (norms: <92, >130, >35) | **STABLE, never pages.** Risk 0.39 → 0.31. |

In all three, every individual vital is abnormal for age and the heuristic
adapter scores them 0.40–0.55 — but the **fused** risk lands below the STABLE/…
boundary and the displayed regime is STABLE.

**Why (case A, reading 2, verified per-engine):** three engines are active —
heuristic 0.40, behavioral 0.70, **bayesian 0.13**. Fusion is a
confidence-weighted mean, so bayesian's low score (at full 0.85 confidence)
pulls the fused risk to 0.40 and its stable-dominant regime shape pulls the
argmax to STABLE. The bayesian adapter assigns near-zero O2 risk here because
SpO2 89% is **exactly** z = −2.0 against its model (expected 95%, SD 3%), and
its trigger is `z < −2.0` (strict). See §4b.

> **SIGN-OFF Q-0.1** — Should a low-scoring engine be able to pull a
> high-scoring engine's assessment down to STABLE via averaging? (The engine
> already protects *named syndromes* from this via the syndrome floor, §4c, but
> not the general multi-system case.)
> **SIGN-OFF Q-0.2** — Is it acceptable for an infant at SpO2 89 / HR 155, or a
> bradycardic infant, or a tachypneic hypoxic 4-year-old, to display **STABLE**
> with no page, indefinitely?
> **SIGN-OFF Q-0.3** — the heuristic hard-rule (score ≥ 0.50, §4a) and the named
> syndromes (§4e) are the *only* reliable escalation triggers for the routine
> path. Everything that stays under 0.50 heuristic and doesn't match a syndrome
> is subject to Q-0.1 dilution. Is that safety net wide enough?

### 0.2 The acute path works

| # | Patient | Vitals | Result |
|---|---|---|---|
| D | toddler (2 y) | SpO2 89, HR 150, RR 42, temp 38.0 → heuristic 0.55 | **WARNING + page on reading 1** (hard-rule bypass, no confirmation delay). |
| E | infant (6 mo) | SpO2 **87%** (crosses the 88% acute cut) | **WARNING + page on reading 1** (`CRITICAL_O2` → hard-rule bypass). |

When a hard cut (SpO2 < 88%, temp < 35°C) or a named syndrome is crossed, the
engine escalates immediately on a single reading. This path is sound.

### 0.3 WARNING → CRITICAL does not raise a new page

Continuing case D: three readings later the child meets **septic-shock
criteria** (SpO2 88, HR 155, RR 46, temp 39.0). Engine result:
**regime → CRITICAL, but `page = False`.**

`escalation_required` is only `True` when crossing *up from* STABLE/CAUTION
(§5c). A child already at WARNING who deteriorates to CRITICAL has the regime
updated but no new alert fires — on the assumption they're already flagged and
the RRT is engaged.

> **SIGN-OFF Q-0.4** — Does your RRT protocol want a distinct, escalated alert
> on WARNING → CRITICAL, or is updating the displayed regime sufficient?

### 0.4 A 5-minute blind window after any escalation (slow path)

After an escalation, the slow path applies a **300-second cooldown**
(`ESCALATION_LOCK_SECONDS`) during which it will not change the regime or fire a
new page. Acute hard-rules/syndromes still update the regime during the cooldown
(but see Q-0.4). See §5c.

> **SIGN-OFF Q-0.5** — Is a 5-minute regime-change blind window immediately
> after an escalation acceptable for the non-acute deterioration pattern?

---

## 1. How a verdict is produced

```
vitals ─► sensor-plausibility validation (§7)
       ─► pick which adapters run (§6)
       ─► each adapter returns risk 0–1 + confidence 0–1 + triggered findings
       ─► confidence-weighted fusion into one risk 0–1  (§5)
             └─ "dangerous syndrome" floor can raise it (§4c)
       ─► risk 0–1 ─► regime probability distribution ─► argmax regime  (§5)
             regimes: STABLE < CAUTION < WARNING < CRITICAL
       ─► escalation decision: does this reading page someone?  (§5c)
             fast path (bypass) for hard rules / named syndromes
             slow path (dwell + cooldown) for everything else
```

The two outputs a clinician cares about:
- **`regime`** — the displayed acuity level.
- **`escalation_required`** — `True` means *this reading should generate a new
  alert/page*.

---

## 2. Age bands  (`get_age_group`, lines 307–317)

| Age | Band | Boundary |
|---|---|---|
| unknown / not supplied | `generic` | — (also logs a warning, line 361) |
| < 3 months | `neonatal` | |
| 3 – < 12 months | `infant` | |
| 12 – < 36 months | `toddler` | |
| ≥ 36 months | `child` | |

> **Review Q2.1** — are 3 / 12 / 36 months the right cut points for these vital
> norms? Some PEWS use finer bands under 12 months.

---

## 3. Age-adjusted vital norms  (`PEDIATRIC_NORMS`, lines 116–122)

These define "abnormal" for the heuristic and bayesian adapters. Units: HR bpm,
RR breaths/min, SpO2 %, temp °C.

| Band | HR high | HR low | RR high | SpO2 low | Temp high |
|---|---|---|---|---|---|
| neonatal | > 160 | < 80 | > 50 | < 90 | > 38.5 |
| infant | > 150 | < 90 | > 45 | < 90 | > 39.0 |
| toddler | > 140 | < 95 | > 40 | < 91 | > 39.0 |
| child | > 130 | < 100 | > 35 | < 92 | > 39.5 |
| generic (age unknown) | > 140 | < 95 | > 40 | < 91 | > 39.0 |

> **Review Q3.1** — do these match your institution's age-banded PEWS
> parameters?
> **Review Q3.2** — `generic` (used whenever age is missing) is the toddler-ish
> midpoint. For a missing-age neonate this *understates* the HR-low and
> *overstates* the acceptable RR. Is "assume toddler" the safe default, or
> should missing age force the most conservative band?

---

## 4. Per-adapter scoring

Each adapter accumulates a `score` (additive unless noted), capped at 1.0, then
maps it through the regime distribution (§5). All "→ +X" values are the amount
added to that adapter's score.

### 4a. Heuristic adapter  (`RiskAdapters.heuristic`, lines 352–400)

Runs on **every** evaluation. Uses age-adjusted norms from §3.

| Condition | Finding | Score |
|---|---|---|
| SpO2 < **88.0%** | `CRITICAL_O2` | **+0.50** |
| else SpO2 < band `o2_low` | `WARNING_O2` | +0.20 |
| HR > band `hr_high` | `TACHYCARDIA` | +0.20 |
| else HR < band `hr_low` | `BRADYCARDIA` | **+0.30** |
| RR > band `rr_high` | `TACHYPNEA` | +0.15 |
| temp > band `temp_high` | `FEVER` | +0.10 |
| else temp < **35.0°C** | `HYPOTHERMIA` | +0.40 |

Confidence: age + prior-reading history present → 0.95; age only → 0.85; no age
→ 0.70.

**The heuristic score also drives the fast escalation path:** if the heuristic
score alone reaches **≥ 0.50** (`HEURISTIC_HARD_RULE_THRESHOLD`, line 206), the
engine bypasses the confirmation-delay logic and escalates on this single
reading (§5c).

> **Review Q4a.1** — SpO2 < 88% is age- and baseline-independent. A child with
> cyanotic congenital heart disease may have a baseline SpO2 of 75–85%. This
> engine will fire `CRITICAL_O2` + hard-rule bypass on **every** reading for
> that child. Baseline-relative assessment exists (drift adapter, §4d) but only
> if a baseline and ≥5-reading history are supplied in context. Is there a
> workflow to supply those for chronic-hypoxia patients, or should such patients
> be flagged out of this engine?
> **Review Q4a.2** — `BRADYCARDIA` (+0.30) does not by itself reach the 0.50
> hard-rule threshold. In pediatrics bradycardia is a pre-arrest sign. A
> bradycardic child needs a second finding worth ≥ 0.20 before the engine
> escalates without waiting for a confirming reading. Is +0.30 the right weight,
> or should bradycardia alone bypass?
> **Review Q4a.3** — weight ordering: `CRITICAL_O2` 0.50 > `HYPOTHERMIA` 0.40 >
> `BRADYCARDIA` 0.30 > `TACHYCARDIA`/`WARNING_O2` 0.20 > `TACHYPNEA` 0.15 >
> `FEVER` 0.10. Does this ranking match clinical ominousness in your population?
> **Review Q4a.4** — the "35.0°C" hypothermia cut and the "88%" critical-O2 cut
> are the only two heuristic thresholds that are **not** age-adjusted. Correct?

### 4b. Bayesian adapter  (`RiskAdapters.bayesian`, lines 402–444)

Runs on the "heavy path" (§6). Scores by how many standard deviations a vital
sits from its expected value.

- SpO2 expected = (band `o2_low` + 100) / 2, SD = **3.0**
- HR expected = (band `hr_high` + band `hr_low`) / 2, SD = (`hr_high` − `hr_low`) / 4

| Condition | Finding | Score |
|---|---|---|
| SpO2 z-score < **−2.0** | `O2_DEVIATION` | +0.40 × *likelihood* |
| \|HR z-score\| > **2.0** | `HR_DEVIATION` | +0.30 × *likelihood* |

*likelihood* is a continuous 0–1 factor that grows with the deviation
(`1 − exp(−0.15·z²)` for O2, `1 − exp(−0.10·z²)` for HR). Confidence fixed at
0.85.

> **Review Q4b.1** — SpO2 SD = 3.0% and the "expected = midpoint between
> band-low and 100" model. For the infant band (`o2_low` 90) expected = 95%,
> SD 3, so z = −2 at SpO2 89%. Is a fixed 3% SD clinically reasonable across
> all ages and conditions?
> **Review Q4b.2** — this adapter has **no bradycardia / hypoxia-floor term** —
> it is symmetric on HR (\|z\| > 2 fires for tachy *or* brady) but the O2 term
> only fires on the *low* side, which is correct. Confirm the HR SD derivation
> (`range / 4`) gives sensible deviation flags.

### 4c. Trajectory adapter  (`RiskAdapters.trajectory`, lines 446–511)

Runs when a previous reading is supplied. **Abstains** (contributes nothing) if
no `previous_*` value or a non-positive time delta. Rates are per minute;
default gap between readings assumed 60 s if not supplied.

| Condition | Finding | Score |
|---|---|---|
| SpO2 falling faster than **−3.0 %/min** | `O2_MOMENTUM` | +0.40 |
| HR rising faster than **+20 bpm/min** | `HR_MOMENTUM` | +0.30 |
| HR falling faster than **−30 bpm/min** | `HR_DECELERATION` | +0.40 |
| RR rising faster than **+5 /min** | `RR_MOMENTUM` | +0.25 |
| temp falling faster than **−1.0 °C/min** | `TEMP_DROP` | +0.30 |
| ≥ **2** of {O2, HR-up, RR} trends bad at once | `MULTI_TREND_DETERIORATION` | +0.20 |

Confidence: 0.60 + 0.30 × (fraction of the 4 previous-vitals present).

> **Review Q4c.1** — are these rate-of-change thresholds right for the
> monitoring cadence? At a 15-minute reading interval, "−3 %/min" means a
> 45-point SpO2 drop between readings — effectively unreachable. These thresholds
> assume high-frequency (~1–2 min) sampling. **What is the actual reading
> cadence in production?** If it is not ~1–2 min, this adapter is largely inert.
> **Review Q4c.2** — `HR_DECELERATION` (−30 bpm/min, +0.40) — a rapidly
> dropping HR is a pre-arrest sign; is a single-reading momentum flag the right
> instrument and weight?

### 4d. Drift adapter  (`RiskAdapters.drift`, lines 513–558)

Runs on the heavy path. **Abstains** unless a `baseline_o2` or `baseline_hr` AND
≥ 5 readings of the corresponding history are supplied in context. Compares the
baseline against the mean of recent history in standard-deviation units.

| Condition | Finding | Score |
|---|---|---|
| SpO2 baseline > **2.0 SD** from recent-history mean | `O2_DRIFT` | +0.30 |
| HR baseline > **2.0 SD** from recent-history mean | `HR_DRIFT` | +0.25 |

(`DRIFT_SIGMA_THRESHOLD` = 2.0, line 127.) Confidence scales with history length
(0.50 at 5 readings → 0.95 at ≥ 100).

> **Review Q4d.1** — this is the only baseline-relative adapter, and it only
> works when the caller supplies a baseline + history. Is that data available in
> your workflow? Without it, every assessment is against population norms only.

### 4e. Behavioral / pattern adapter  (`RiskAdapters.behavioral_vaccine`, lines 560–616)

Runs when SpO2 < 92 **or** HR > 140 **or** HR < 90 (line 1260). Combines a base
score with **named syndrome patterns**. **Syndrome thresholds here are NOT
age-adjusted — they are fixed numbers.**

**Base score:**

| Condition | Score |
|---|---|
| SpO2 < 90.0% | +0.40 |
| else SpO2 < 92.0% | +0.20 |
| HR > 150 **or** HR < 80 | +0.30 |

**Named syndromes (each fires independently; all can stack):**

| Syndrome | Criteria (all must hold) | Score | Effect |
|---|---|---|---|
| `SEPTIC_SHOCK` | SpO2 < 92 **and** HR > 140 **and** RR > 35 **and** temp > 38.5 | +0.40 | `DANGEROUS_PATTERN` → syndrome floor (§4f) + fast escalation (§5c) |
| `RESPIRATORY_DISTRESS` | SpO2 < 90 **and** RR > 45 | +0.35 | same |
| `HYPOVOLEMIC_SHOCK` | HR > 150 **and** SpO2 < 88 | +0.35 | same |

**Benign-pattern reductions** (only applied if *no* syndrome fired **and** an
`alert` context value is known):

| Pattern | Criteria | Effect |
|---|---|---|
| `fever_response` | temp > 38.5 **and** HR > 130 **and** RR > 28 | score → `max(score − 0.15, base × 0.5)` |
| `crying_baby` | `alert == "crying"` **and** HR > 140 | score → `max(score − 0.10, base × 0.5)` |

Confidence: 0.90 if `alert` known, else 0.75.

> **Review Q4e.1 (highest priority)** — the syndrome criteria use fixed
> thresholds (HR > 140/150, RR > 35/45, SpO2 < 88/90/92, temp > 38.5). These are
> **not** age-scaled. For a neonate, RR 44 and HR 155 can be normal; for a
> 10-year-old, HR 145 is markedly abnormal. Do these fixed criteria correctly
> identify septic/hypovolemic shock across the **whole 0–18y range**, or do they
> need age bands like the heuristic adapter has?
> **Review Q4e.2** — the base score checks `HR < 80` for the +0.30 bradycardia
> contribution. A neonate (normal HR-low 80) or infant (HR-low 90) can be
> significantly bradycardic at HR 85 and **not** trip this. Should the base
> bradycardia check use the age band?
> **Review Q4e.3** — the benign reductions subtract up to 0.15 from the score.
> They only apply when `alert` is supplied and no syndrome fired. Is the
> `fever_response` pattern (temp > 38.5 + HR > 130 + RR > 28) safe to
> down-weight? A septic child early in their course can look like a fever
> response.

### 4f. Adversarial / sensor-integrity adapter  (`RiskAdapters.adversarial`, lines 618–672)

Runs when `recent_o2_readings` are supplied. Detects **sensor problems, not
clinical severity.**

| Condition | Finding | Score |
|---|---|---|
| ≥ 5 identical consecutive SpO2 readings | `CONSTANT_VALUE_STREAK` | +0.30 |
| 10-reading window variance < 0.01 (and not all identical) | `LOW_VARIANCE_SENSOR` | +0.15 |
| SpO2 change > 15 %/min | `IMPLAUSIBLE_RATE` | +0.25 |

Confidence fixed 0.70. Note (line 659): low SpO2 + low HR is deliberately **not**
flagged here — it is a real danger sign, handled by the heuristic/behavioral
adapters.

### 4g. Physiological-reserve adapter  (`RiskAdaptersPhysiological`, lines 701–838)

Runs only when "rich" telemetry (NIRS perfusion, continuous lactate, HRV, organ
indices — not bedside monitor data) is present, **or** on the heavy path if
`hr_history` is available for the instability axis. **Abstains** entirely if no
rich telemetry.

Six axes, each 0–1, each contributing only if its telemetry is present. Final
risk = **mean of the present axes**. Axis internal formulas (lines 727–788):

| Axis | Formula (all clamped 0–1) |
|---|---|
| topology | 0.6·(1−organ_coupling) + 0.4·(organ_failures / total_organs) |
| capacity | 0.6·(1 − perfusion/load) + 0.4·(\|perfusion−demand\| / demand) |
| resource | 0.5·(1−reserve) + 0.5·[0.4·(1−substrate) + 0.3·(1−viability) + 0.3·(1−energy)] |
| integrity | 0.6·(0.10·events + 0.30·critical_events) + 0.4·infection_burden |
| phase | base + 0.3·decomp − 0.2·comp, where base = {stable 0.1, compensation 0.3, decompensation 0.6, collapse 0.9} |
| instability | mean(\|ΔHR\|) / 30 over `hr_history` |

An axis value ≥ 0.5 emits a `PHYSIO_<AXIS>` finding. Confidence = 0.45 + 0.50·(axes_present / 6).

> **Review Q4g.1** — this adapter is only meaningful with instrumentation most
> wards don't have. Confirm which of these inputs (`perfusion_index`,
> `lactate`-derived, `organ_coupling_index`, …) your deployment can actually
> supply. If none, this adapter always abstains and can be ignored for review.

---

## 5. Fusion, regime mapping, and escalation

### 5a. Fusion  (`BayesianFusion.fuse`, lines 848–902)

- Engines that **abstained** are excluded entirely (an engine saying "no data"
  must not dilute an engine that detected something).
- `fused_risk` = confidence-weighted mean of the active engines' risk scores.
- `regime distribution` = confidence-weighted mean of the active engines' regime
  distributions.
- **Syndrome floor:** if any active engine emitted a `DANGEROUS_PATTERN`, the
  fused risk is raised to at least that engine's own risk score (a named
  syndrome is not averaged down by other engines assessing other things).

### 5b. Risk score → regime  (`regime_distribution` + `REGIME_DISTRIBUTION_BANDS`, lines 196–202, 320–342)

The fused risk selects a probability shape; the regime is the argmax.

| Fused risk | P(stable) | P(caution) | P(warning) | P(critical) | Argmax regime |
|---|---|---|---|---|---|
| ≥ 0.75 | 0.05 | 0.10 | 0.25 | **0.60** | CRITICAL |
| 0.50 – 0.75 | 0.10 | 0.20 | **0.55** | 0.15 | WARNING |
| 0.25 – 0.50 | 0.35 | **0.50** | 0.12 | 0.03 | CAUTION |
| < 0.25 | **0.88** | 0.08 | 0.03 | 0.01 | STABLE |

(A small `critical_floor` — 0.01 normally, 0.02 for the drift adapter — keeps
P(critical) from ever reaching exactly zero.)

> **Review Q5b.1 (highest priority — the single most consequential mechanism in
> the system)** — two things interact here and both need sign-off:
>
> 1. **The regime is the argmax of a *confidence-weighted mean of each engine's
>    own regime distribution*** — NOT `regime_distribution(fused_risk)`. So a
>    low-scoring engine at high confidence flattens the distribution toward
>    STABLE even when another engine detected real abnormality (§0.1, Q-0.1).
> 2. **The 0.25 / 0.50 / 0.75 cut points and the four probability shapes.** In
>    isolation, fused risk 0.60 → WARNING-dominant, 0.80 → CRITICAL-dominant.
>    But after the weighted-mean-of-distributions step, the effective mapping is
>    softer than the table suggests (§0.1 case A: fused risk 0.40 → STABLE, not
>    the CAUTION the table implies).
>
> Verified end-to-end (see §0): infant SpO2 89/HR 155 → **STABLE**; toddler
> heuristic-0.55 → **WARNING+page**; SpO2 <88 anything → **CRITICAL/WARNING +
> page** via hard-rule.
>
> Is this mapping right for **which tier pages the RRT vs the covering
> clinician**, and is the argmax-of-averaged-distributions method the one you
> want (vs. mapping the fused risk scalar directly through the band table)?

### 5c. Escalation — does this reading page someone?

`escalation_required = True` means *raise a new alert now*.

**Fast path (bypass — no confirmation delay):** if the heuristic score ≥ 0.50
(hard rule) **or** any `DANGEROUS_PATTERN` fired, and the resulting regime is
WARNING or CRITICAL:
- `escalation_required = True` **only if the patient's tracked regime was
  STABLE or CAUTION** before this reading (lines 1354–1363).

**Slow path (everything else — `EscalationPolicy`, lines 909–952):**
- The new regime must be observed on **2 consecutive readings**
  (`ESCALATION_DWELL_THRESHOLD`, line 207) before the tracked regime changes.
- `escalation_required = True` when the tracked regime crosses from
  STABLE/CAUTION **up to** WARNING/CRITICAL.
- After any escalation, a **300-second cooldown**
  (`ESCALATION_LOCK_SECONDS`, line 208): during it, the slow path does not
  change the regime or fire a new escalation.

> **Review Q5c.1 (high priority)** — **WARNING → CRITICAL produces no new
> page.** On both paths, `escalation_required` is only `True` when crossing *up
> from* STABLE/CAUTION. A child already at WARNING who then meets septic-shock
> criteria has their regime updated to CRITICAL but `escalation_required`
> stays `False`. Rationale in code: they're already flagged. Does your RRT
> protocol want a distinct, louder alert on WARNING → CRITICAL?
> **Review Q5c.2 (high priority)** — the **300 s cooldown** on the slow path.
> A child who escalates STABLE → WARNING and then genuinely deteriorates toward
> CRITICAL within 5 minutes has the CRITICAL regime change *suppressed* unless a
> hard-rule/syndrome bypass fires. Is 5 minutes an acceptable blind window right
> after an escalation? (The bypass path *does* still update the regime during
> the cooldown, so an acute `CRITICAL_O2` or named syndrome will show CRITICAL —
> just without a new `escalation_required`, see Q5c.1.)
> **Review Q5c.3** — the **2-reading dwell** on the slow path. Time to
> escalation = 2 × reading interval. Only acute hard-rules/syndromes skip it.
> Is a 2-reading confirmation delay acceptable for the non-acute deterioration
> pattern, at your reading cadence?

---

## 6. Which adapters run  (`select_engines`, lines 1245–1273)

| Adapter | Runs when |
|---|---|
| heuristic | always |
| behavioral | SpO2 < 92 **or** HR > 140 **or** HR < 90 |
| trajectory | any `previous_*` supplied (or heavy path) |
| adversarial | `recent_o2_readings` supplied |
| bayesian, drift | heavy path only |
| physiological_reserve | heavy path, or rich telemetry present |

**Heavy path** triggers when the patient's *previous* reading had high engine
disagreement (Shannon entropy > 0.6, `HEAVY_PATH_ENTROPY_TRIGGER`, line 205) or
the caller sets `force_heavy`.

> **Review Q6.1** — the bayesian and drift adapters only run once a *prior*
> reading was ambiguous. A first-contact reading of a deteriorating child runs
> only heuristic (+ behavioral/trajectory if their gates trip). Is the heuristic
> adapter alone sufficient for first-contact safety, given the review questions
> in §4a?

---

## 7. Unassessable / sensor-fault handling  (§7, lines 211–224, 1330–1375)

- A **non-finite** (NaN/inf) or **physically impossible** vital
  (`VITALS_PHYSICAL_BOUNDS`: HR 0–400, SpO2 0–100, RR 0–250, temp 12–50 °C) is
  treated as a faulted channel.
- The faulted channel is masked and the **other** channels are still assessed.
- The verdict is floored at **WARNING**, never below the patient's tracked
  regime, and `unassessable = True`.
- The engine pages once per 300 s while a fault persists (or immediately if a
  valid channel meets a bypass rule).

> **Review Q7.1** — the temperature *lower* bound is 12 °C. Profound hypothermia
> (a real emergency) between 12 and ~28 °C is assessed as a real reading; below
> 12 °C it's treated as a sensor fault (→ WARNING + unassessable). Is 12 °C the
> right "no living patient reads this" floor for your population?

---

## 8. Value classification

### CLINICAL CALIBRATION — please review against evidence / institutional PEWS

| Group | Values | Ref |
|---|---|---|
| Age band boundaries | 3, 12, 36 months | §2 |
| Age-adjusted vital norms | all of `PEDIATRIC_NORMS` (25 values) | §3 |
| Heuristic O2/temp hard cuts | SpO2 88%, temp 35 °C | §4a |
| Heuristic weights | 0.50, 0.20, 0.20, 0.30, 0.15, 0.10, 0.40 | §4a |
| Hard-rule bypass threshold | heuristic score ≥ 0.50 | §4a / §5c |
| Bayesian deviation triggers | z < −2.0 (O2), \|z\| > 2.0 (HR); weights 0.40, 0.30 | §4b |
| Trajectory rate thresholds | −3 %/min, +20 / −30 bpm/min, +5 /min, −1 °C/min | §4c |
| Trajectory weights | 0.40, 0.30, 0.40, 0.25, 0.30, 0.20 | §4c |
| Multi-trend trigger | ≥ 2 concurrent bad trends | §4c |
| Drift trigger | > 2.0 SD; weights 0.30, 0.25 | §4d |
| Behavioral base thresholds | SpO2 90/92, HR 80/150; weights 0.40, 0.20, 0.30 | §4e |
| Syndrome definitions + weights | SEPTIC_SHOCK / RESPIRATORY_DISTRESS / HYPOVOLEMIC_SHOCK criteria; 0.40, 0.35, 0.35 | §4e |
| Benign-pattern criteria + reductions | fever_response, crying_baby; −0.15, −0.10 | §4e |
| Adversarial implausible-rate | 15 %/min | §4f |
| **Regime band cut points** | **0.25, 0.50, 0.75** and the four probability shapes | §5b |
| Escalation timing | 2-reading dwell, 300 s cooldown | §5c |
| Temp sensor-fault floor | 12 °C | §7 |

### STRUCTURAL — changing these alters engine mechanics; route to engineering, not clinical tuning

Bayesian SD model (`o2_std = 3.0`, `hr_std = range/4`) and sigmoid decay
constants (0.15, 0.10); adversarial streak length (5), window (10), variance
floor (0.01); trajectory/drift confidence formulas and history-length gates
(5 / 10 / 50 / 100); `critical_floor` (0.01, 0.02); physiological-axis internal
weights and the `/30` instability normalizer; `HEAVY_PATH_ENTROPY_TRIGGER`
(0.6); `_VITALS_NEUTRAL` masking values; `UNASSESSABLE_CONFIDENCE_PENALTY`
(0.5); confidence values on every adapter.

> Note: a few STRUCTURAL values have clinical *consequences* even though they
> aren't clinical thresholds — most notably the 2-reading dwell and 300 s
> cooldown (§5c) and the heavy-path gating (§6). Those are called out with
> review questions above even though the raw numbers are engineering choices.

---

## 9. Consolidated review checklist (priority order)

1. **§0.1 Q-0.1 / Q-0.2 / Q-0.3** — sub-threshold multi-system abnormality
   (abnormal infant sitting at STABLE); low-scoring engine diluting a
   high-scoring one via the confidence-weighted mean. **This is the finding most
   likely to miss a deteriorating child.**
2. **§5b Q5b.1** — the argmax-of-averaged-distributions regime method + the
   0.25/0.50/0.75 cut points. Which fused risk should page the RRT?
3. **§4e Q4e.1** — syndrome criteria (septic/hypovolemic shock) are not
   age-scaled. Do they hold across 0–18 y?
4. **§0.3 Q-0.4 / §0.4 Q-0.5** — no new page on WARNING → CRITICAL; 300 s
   regime-change blind window after an escalation.
5. **§4a Q4a.1 / Q4a.2** — chronic-hypoxia (cyanotic CHD) patients read as
   permanent CRITICAL; isolated bradycardia does not reach the hard-rule.
6. **§4c Q4c.1** — production reading cadence (trajectory adapter assumes
   ~1–2 min sampling; inert at 15-min intervals).
7. **§3 Q3.1 / Q3.2** — age-banded norms vs your PEWS; missing-age default is
   "toddler", not "most conservative".
8. **§6 Q6.1** — a first-contact reading runs only the heuristic adapter (+
   conditional behavioral/trajectory).
9. Everything else in §8's CLINICAL CALIBRATION table.

---

## 10. Provenance

- `PARAMETER_SET_VERSION` (stamped on every verdict) currently attests the
  age-band norms, sensor bounds, regime band table, and the escalation-timing
  constants — **not** the `score += X` weights inside the adapters. Those are
  attested only by the source-control revision (`main` @ `73eff68` at
  extraction). If review approves the weights, hoisting the genuine tunable ones
  into that versioned surface is the follow-up (see
  `RESILIENCE_INTEGRATION_ASSESSMENT.md` §14, item 2).
- This document was extracted by hand and cross-checked line by line. If it
  disagrees with the code, **the code is authoritative** — report the
  discrepancy.
