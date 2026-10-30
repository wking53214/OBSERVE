"""
Invariant / property tests for the consolidated OBSERVE clinical engine.

Harvested from the adversarial analysis of the rejected "URE" resilience
candidate (RESILIENCE_INTEGRATION_ASSESSMENT.md, section 12). Each test locks
out a failure mode the candidate exhibited, restated against OBSERVE's own
mechanisms. IDs match the assessment.

Run: python3 -m pytest test_observe_invariants.py -v
"""

import hashlib
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

from observe_consolidated import (
    ObserveClinicalEngine,
    VitalsSnapshot,
    BayesianFusion,
    RiskAdapters,
    OperationalRegime,
    regime_distribution,
    validate_vitals,
    decision_fingerprint,
    compute_state_commitment,
    PARAMETER_SET,
    PARAMETER_SET_VERSION,
    _canonical_json,
    REGIME_DISTRIBUTION_BANDS,
    DRIFT_SIGMA_THRESHOLD,
    REGIME_CRITICAL_FLOOR_DEFAULT,
    DRIFT_CRITICAL_FLOOR,
    ESCALATION_DWELL_THRESHOLD,
    ESCALATION_LOCK_SECONDS,
    VITALS_PHYSICAL_BOUNDS,
    REGIME_RISK_FLOOR,
    PEDIATRIC_NORMS,
)


def make_vitals(**overrides) -> VitalsSnapshot:
    defaults = dict(
        patient_id="P-INV",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        heart_rate=100.0,
        oxygen_saturation=97.0,
        respiratory_rate=24.0,
        temperature=37.0,
        context={"age_months": 24},
    )
    defaults.update(overrides)
    return VitalsSnapshot(**defaults)


_PROVENANCE_KEYS = ("decision_fingerprint", "predecessor_state_commitment", "state_commitment")


def _replay_fingerprint(entry, **overrides) -> str:
    """Recompute the fingerprint from a stored audit entry, as a verifier would."""
    payload = {k: v for k, v in entry["data"].items() if k not in _PROVENANCE_KEYS}
    payload.update(overrides)
    return decision_fingerprint(payload)


class StateContinuityBoundary(unittest.TestCase):
    """Narrow continuity checks at the evidence boundary."""

    def test_state_commitment_is_deterministic(self):
        payload = {"patient_id": "P-STATE", "risk_score": 0.63, "regime": "warning"}
        self.assertEqual(
            compute_state_commitment("", payload),
            compute_state_commitment("", {"patient_id": "P-STATE", "risk_score": 0.63, "regime": "warning"}),
        )

    def test_state_commitment_binds_to_predecessor(self):
        payload = {"patient_id": "P-STATE", "risk_score": 0.63, "regime": "warning"}
        self.assertNotEqual(
            compute_state_commitment("prev-1", payload),
            compute_state_commitment("prev-2", payload),
        )

    def test_engine_binds_each_verdict_to_the_previous_state(self):
        engine = ObserveClinicalEngine()
        first = engine.evaluate(make_vitals(patient_id="P-CHAIN", oxygen_saturation=97.0, heart_rate=100.0))
        second = engine.evaluate(make_vitals(patient_id="P-CHAIN", oxygen_saturation=88.0, heart_rate=170.0))
        self.assertNotEqual(first.state_commitment, second.state_commitment)
        self.assertEqual(second.predecessor_state_commitment, first.state_commitment)
        self.assertTrue(engine.audit_ledger.verify_integrity())


class I1_EntropyInputIsAValidDistribution(unittest.TestCase):
    """I-1: any distribution fed to an entropy calc must sum to 1 (+/- 1e-9)."""

    def test_regime_distribution_normalized_across_risk_sweep(self):
        for i in range(0, 101):
            s = i / 100.0
            d = regime_distribution(s)
            self.assertAlmostEqual(sum(d.values()), 1.0, places=9, msg=f"risk={s}: {d}")
            for k, v in d.items():
                self.assertGreaterEqual(v, 0.0, msg=f"risk={s} {k}={v}")

    def test_regime_distribution_bands_each_normalized(self):
        for lb, shape in REGIME_DISTRIBUTION_BANDS:
            self.assertAlmostEqual(sum(shape.values()), 1.0, places=9, msg=f"band {lb}: {shape}")

    def test_fused_regime_probs_normalized(self):
        engine = ObserveClinicalEngine()
        for v in (make_vitals(), make_vitals(oxygen_saturation=84.0, heart_rate=170.0),
                  make_vitals(oxygen_saturation=90.0)):
            selected = engine.select_engines(v)
            outputs = [engine.ENGINE_MAP[n](v) for n in selected]
            _, entropy, regime_probs, _ = BayesianFusion.fuse(outputs)
            self.assertAlmostEqual(sum(regime_probs.values()), 1.0, places=6,
                                   msg=f"{regime_probs}")
            self.assertGreaterEqual(entropy, 0.0)


class T1_EntropyIsInBits(unittest.TestCase):
    """T-1: Shannon entropy uses log2. Uniform 4-class => exactly 2.0 bits.

    Guards against a future ln/log2 regression (the candidate used nats).
    """

    def test_uniform_four_class_entropy_is_two_bits(self):
        uniform = {"stable": 0.25, "caution": 0.25, "warning": 0.25, "critical": 0.25}
        out = RiskAdapters.heuristic(make_vitals())
        out.regime_classification = uniform
        out.confidence = 1.0
        out.abstained = False
        _, entropy, regime_probs, _ = BayesianFusion.fuse([out])
        self.assertAlmostEqual(sum(regime_probs.values()), 1.0, places=9)
        self.assertAlmostEqual(entropy, 2.0, places=9)

    def test_degenerate_distribution_entropy_is_zero(self):
        certain = {"stable": 1.0, "caution": 0.0, "warning": 0.0, "critical": 0.0}
        out = RiskAdapters.heuristic(make_vitals())
        out.regime_classification = certain
        out.confidence = 1.0
        out.abstained = False
        _, entropy, _, _ = BayesianFusion.fuse([out])
        self.assertAlmostEqual(entropy, 0.0, places=9)


class T2_MissingOrGarbageTelemetryNeverReadsAsHealthy(unittest.TestCase):
    """T-2 / T-6: a non-finite or out-of-range vital is unassessable.

    The candidate silently coerced missing metrics to 0.0 and returned NEUTRAL.
    OBSERVE must return WARNING + faults, never STABLE.
    """

    def test_nan_vital_rejected(self):
        engine = ObserveClinicalEngine()
        v = make_vitals(oxygen_saturation=float("nan"))
        verdict = engine.evaluate(v)
        self.assertNotEqual(verdict.regime, OperationalRegime.STABLE)
        self.assertEqual(verdict.regime, OperationalRegime.WARNING)  # fresh engine, prior STABLE
        self.assertTrue(verdict.validation_faults)
        self.assertTrue(verdict.unassessable)
        self.assertTrue(verdict.escalation_required)

    def test_inf_vital_rejected(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(temperature=float("inf")))
        self.assertTrue(verdict.validation_faults)
        self.assertNotEqual(verdict.regime, OperationalRegime.STABLE)

    def test_out_of_range_vital_rejected(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(heart_rate=999.0))
        self.assertIn("heart_rate=999.0 outside physical range [0.0, 350.0]", verdict.validation_faults)
        self.assertNotEqual(verdict.regime, OperationalRegime.STABLE)

    def test_negative_vital_rejected(self):
        self.assertTrue(validate_vitals(make_vitals(respiratory_rate=-5.0)))

    def test_clean_vitals_have_no_faults(self):
        self.assertEqual(validate_vitals(make_vitals()), [])

    def test_abstentions_do_not_dilute_a_real_detection(self):
        # No trajectory/drift telemetry -> those engines abstain. A genuine
        # low-O2 reading must still drive the verdict, not average back to stable.
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(oxygen_saturation=82.0, heart_rate=175.0))
        self.assertIn(verdict.regime, (OperationalRegime.WARNING, OperationalRegime.CRITICAL))


class T2b_ValidationFaultOverlayIsSafe(unittest.TestCase):
    """Review findings 1-4: a faulted channel must not (1) downgrade a tracked
    regime, (2) suppress signals in the still-valid channels, (3) read as benign,
    or (4) produce an escalation storm that ignores the cooldown.
    """

    def _drive_to_critical(self, engine, pid):
        crit = make_vitals(patient_id=pid, oxygen_saturation=70.0, heart_rate=190.0,
                           respiratory_rate=65.0, temperature=39.5)
        v = engine.evaluate(crit)
        self.assertEqual(v.regime, OperationalRegime.CRITICAL)
        return crit

    def test_fault_does_not_downgrade_a_tracked_critical_patient(self):
        engine = ObserveClinicalEngine()
        self._drive_to_critical(engine, "crit1")
        # SpO2 probe falls off mid-monitoring
        after = engine.evaluate(make_vitals(patient_id="crit1", oxygen_saturation=float("nan"),
                                            heart_rate=190.0, respiratory_rate=65.0, temperature=39.5))
        self.assertTrue(after.unassessable)
        self.assertEqual(after.regime, OperationalRegime.CRITICAL)  # NOT downgraded to WARNING

    def test_fault_in_one_channel_preserves_signals_in_the_others(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(patient_id="multi", oxygen_saturation=float("nan"),
                                              heart_rate=210.0, respiratory_rate=70.0))
        self.assertTrue(verdict.unassessable)
        self.assertTrue(any("DATA_INTEGRITY_FAULT" in r for r in verdict.triggered_rules))
        # the real tachycardia / tachypnea must still surface
        self.assertTrue(any(("tachy" in r.lower() or "hr" in r.lower() or "rr" in r.lower()
                             or "DANGEROUS_PATTERN" in r)
                            for r in verdict.triggered_rules if "DATA_INTEGRITY_FAULT" not in r),
                        msg=verdict.triggered_rules)
        self.assertIn(verdict.regime, (OperationalRegime.WARNING, OperationalRegime.CRITICAL))

    def test_fault_verdict_is_not_benign(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(oxygen_saturation=float("nan")))
        self.assertNotEqual(verdict.regime, OperationalRegime.STABLE)
        self.assertGreaterEqual(_severity(verdict.regime), _severity(OperationalRegime.WARNING))

    def test_escalation_storm_is_bounded_by_the_cooldown(self):
        engine = ObserveClinicalEngine()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = engine.evaluate(make_vitals(patient_id="flap", oxygen_saturation=float("nan"),
                                            timestamp=t0))
        self.assertTrue(first.escalation_required)
        # a loose lead re-faults 10s later, well inside the 300s lock
        second = engine.evaluate(make_vitals(patient_id="flap", oxygen_saturation=float("nan"),
                                             timestamp=t0 + timedelta(seconds=10)))
        self.assertFalse(second.escalation_required)
        self.assertEqual(second.regime, OperationalRegime.WARNING)  # still held, just not re-paged

    def test_clinically_extreme_but_real_values_are_assessed_not_rejected(self):
        # profound hypothermia: a real emergency, above the sensor-fault floor (12 C)
        self.assertEqual(validate_vitals(make_vitals(temperature=21.0)), [])
        # a temperature probe reading a cold room is a sensor fault
        self.assertTrue(validate_vitals(make_vitals(temperature=8.0)))
        # infant SVT ~300 bpm is real; 999 is a sensor fault
        self.assertEqual(validate_vitals(make_vitals(heart_rate=300.0)), [])
        self.assertTrue(validate_vitals(make_vitals(heart_rate=999.0)))

    # ---- review round 2 ----

    def test_risk_floor_is_applied_on_hold_calls_not_just_the_change_call(self):
        # Finding: the floor was only applied when the regime changed; on a
        # subsequent hold call regime=WARNING but risk_score fell back to ~0.05.
        engine = ObserveClinicalEngine()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = engine.evaluate(make_vitals(patient_id="hold", oxygen_saturation=float("nan"), timestamp=t0))
        held = engine.evaluate(make_vitals(patient_id="hold", oxygen_saturation=float("nan"),
                                           timestamp=t0 + timedelta(seconds=10)))
        self.assertEqual(held.regime, OperationalRegime.WARNING)
        self.assertGreaterEqual(held.risk_score, first.risk_score)
        self.assertGreaterEqual(held.risk_score, 0.50)

    def test_sustained_fault_does_not_corrupt_or_lock_the_escalation_policy(self):
        # Finding: the overlay wiped pending/dwell and armed a 300s lock every
        # call, so a real gradual CRITICAL could never accumulate dwell.
        engine = ObserveClinicalEngine()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(4):
            engine.evaluate(make_vitals(patient_id="frozen", oxygen_saturation=float("nan"),
                                        timestamp=t0 + timedelta(seconds=30 * i)))
        policy = engine._patient_policies["frozen"]
        self.assertEqual(policy.current_regime, OperationalRegime.STABLE)  # not bumped
        self.assertFalse(policy.escalation_locked)                          # not locked
        self.assertEqual(policy.dwell_count, 0)

    def test_transient_fault_does_not_permanently_bump_the_tracked_regime(self):
        # Finding: a one-reading fault bumped policy.current_regime to WARNING,
        # so a later genuine WARNING->CRITICAL yielded escalation=False.
        engine = ObserveClinicalEngine()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        engine.evaluate(make_vitals(patient_id="tr", oxygen_saturation=float("nan"), timestamp=t0))
        self.assertEqual(engine._patient_policies["tr"].current_regime, OperationalRegime.STABLE)
        crash = engine.evaluate(make_vitals(patient_id="tr", oxygen_saturation=76.0, heart_rate=188.0,
                                            respiratory_rate=62.0, temperature=39.7,
                                            timestamp=t0 + timedelta(seconds=120)))
        self.assertEqual(crash.regime, OperationalRegime.CRITICAL)
        self.assertTrue(crash.escalation_required)  # the real CRITICAL still pages

    def test_bypass_during_a_fault_does_not_mutate_the_tracked_regime(self):
        # Review round 3: NaN SpO2 + real HR=210 fires the hard-rule bypass; the
        # masked distribution resolves to WARNING and the old code wrote
        # policy.current_regime=WARNING, suppressing a later genuine CRITICAL.
        engine = ObserveClinicalEngine()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        engine.evaluate(make_vitals(patient_id="bpf", oxygen_saturation=float("nan"),
                                    heart_rate=210.0, timestamp=t0))
        self.assertEqual(engine._patient_policies["bpf"].current_regime, OperationalRegime.STABLE)
        recovered = engine.evaluate(make_vitals(patient_id="bpf", oxygen_saturation=75.0,
                                                heart_rate=150.0, respiratory_rate=45.0,
                                                timestamp=t0 + timedelta(seconds=600)))
        self.assertEqual(recovered.regime, OperationalRegime.CRITICAL)
        self.assertTrue(recovered.escalation_required)

    def test_fault_reading_does_not_overwrite_carried_entropy(self):
        # Review round 3: entropy from masked (agreeing) engines was stored and
        # then demoted the next real reading to the light engine set.
        engine = ObserveClinicalEngine()
        engine._patient_entropy["ent"] = 1.5  # prior genuine disagreement
        engine.evaluate(make_vitals(patient_id="ent", oxygen_saturation=float("nan")))
        self.assertEqual(engine._patient_entropy["ent"], 1.5)

    def test_masked_channel_does_not_inject_a_synthetic_improving_trend(self):
        # Finding: masking O2 to 98 while previous_o2=90 fabricated a +8 %/min
        # uptrend that cancelled real deterioration.
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(
            patient_id="trend", oxygen_saturation=float("nan"), heart_rate=155.0,
            context={"age_months": 24, "previous_o2": 90, "previous_hr": 120,
                     "history_o2": [90, 89, 88, 90, 89], "time_delta_seconds": 60},
        ))
        # no fabricated O2-improvement rule; the real HR climb still surfaces
        self.assertFalse(any("O2_MOMENTUM" in r and "+" in r for r in verdict.triggered_rules),
                         msg=verdict.triggered_rules)
        self.assertTrue(any("HR_MOMENTUM" in r for r in verdict.triggered_rules), msg=verdict.triggered_rules)


def _severity(regime: OperationalRegime) -> int:
    return {"stable": 0, "caution": 1, "warning": 2, "critical": 3}[regime.value]


class T4_RiskIsGradedNotSaturated(unittest.TestCase):
    """T-4: fused risk is a graded score in [0,1), monotone in severity.

    The candidate's composite risk pinned to 1.0 under ordinary load.
    """

    def test_moderate_case_is_strictly_between_zero_and_one(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(oxygen_saturation=90.0))
        self.assertGreater(verdict.risk_score, 0.0)
        self.assertLess(verdict.risk_score, 1.0)

    def test_worse_oxygen_does_not_lower_risk(self):
        engine = ObserveClinicalEngine()
        last = -1.0
        for o2 in (98.0, 94.0, 90.0, 86.0, 82.0):
            r = engine.evaluate(make_vitals(patient_id=f"P{o2}", oxygen_saturation=o2)).risk_score
            self.assertGreaterEqual(round(r, 6), round(last, 6), msg=f"o2={o2} risk={r}")
            last = r


class T5_EveryRegimeIsReachable(unittest.TestCase):
    """T-5: no dead regime. The candidate defined 6 regimes; only 2 could ever win."""

    def test_all_four_regimes_are_argmax_for_some_risk(self):
        seen = set()
        for i in range(0, 101):
            d = regime_distribution(i / 100.0)
            seen.add(max(d, key=d.get))
        self.assertEqual(seen, {"stable", "caution", "warning", "critical"})

    def test_engine_reaches_stable_and_critical_end_to_end(self):
        engine = ObserveClinicalEngine()
        stable = engine.evaluate(make_vitals(patient_id="well"))
        self.assertEqual(stable.regime, OperationalRegime.STABLE)
        severe = engine.evaluate(make_vitals(patient_id="sick", oxygen_saturation=78.0,
                                             heart_rate=180.0, respiratory_rate=60.0))
        self.assertIn(severe.regime, (OperationalRegime.WARNING, OperationalRegime.CRITICAL))


class I2_BaselineRelativeClaimsUseTheBaseline(unittest.TestCase):
    """I-2: the drift adapter's output must actually depend on the baseline arg.

    The candidate's evaluate_composite_risk took a baseline and ignored it.
    """

    HISTORY = [95.0, 96.0, 95.0, 94.0, 96.0, 95.0, 95.0, 96.0]

    def _drift(self, baseline_o2):
        v = make_vitals(context={
            "age_months": 24,
            "baseline_o2": baseline_o2,
            "history_o2": self.HISTORY,
        })
        return RiskAdapters.drift(v)

    def test_baseline_far_from_history_triggers_drift(self):
        out = self._drift(baseline_o2=80.0)
        self.assertFalse(out.abstained)
        self.assertGreater(out.risk_score, 0.0)
        self.assertTrue(any("O2_DRIFT" in r for r in out.triggered_rules))

    def test_baseline_at_history_mean_does_not_trigger_drift(self):
        mean = sum(self.HISTORY) / len(self.HISTORY)
        out = self._drift(baseline_o2=mean)
        self.assertEqual(out.risk_score, 0.0)
        self.assertFalse(any("O2_DRIFT" in r for r in out.triggered_rules))

    def test_drift_score_changes_with_baseline(self):
        self.assertNotEqual(self._drift(80.0).risk_score, self._drift(95.0).risk_score)


class I3_ParameterSetVersionIsBoundIntoProvenance(unittest.TestCase):
    """I-3: the calibration set is versioned and bound into every verdict.

    Two builds with different constants must be distinguishable; a verdict must
    be independently replayable.
    """

    def test_every_verdict_carries_the_active_parameter_version(self):
        engine = ObserveClinicalEngine()
        for v in (make_vitals(), make_vitals(oxygen_saturation=85.0),
                  make_vitals(heart_rate=float("nan"))):  # fault path too
            verdict = engine.evaluate(v)
            self.assertEqual(verdict.parameter_set_version, PARAMETER_SET_VERSION)
            self.assertEqual(len(verdict.parameter_set_version), 64)

    def test_audit_entry_records_the_parameter_version(self):
        engine = ObserveClinicalEngine()
        engine.evaluate(make_vitals())
        entry = engine.audit_ledger.entries[-1]
        self.assertEqual(entry["data"]["parameter_set_version"], PARAMETER_SET_VERSION)

    def test_decision_fingerprint_is_deterministic_and_timestamp_free(self):
        v = make_vitals(patient_id="replay", oxygen_saturation=88.0)
        fp1 = ObserveClinicalEngine().evaluate(v).decision_fingerprint
        fp2 = ObserveClinicalEngine().evaluate(v).decision_fingerprint
        self.assertEqual(fp1, fp2)

    def test_decision_fingerprint_is_persisted_on_verdict_and_in_audit(self):
        # Review finding 6: the fingerprint must be produced by evaluate() and
        # stored, or "replay / drift detection" has no baseline in production.
        engine = ObserveClinicalEngine()
        v = make_vitals(patient_id="persist", oxygen_saturation=88.0)
        verdict = engine.evaluate(v)
        self.assertEqual(len(verdict.decision_fingerprint), 64)
        entry = engine.audit_ledger.entries[-1]
        self.assertEqual(entry["data"]["decision_fingerprint"], verdict.decision_fingerprint)
        self.assertEqual(_replay_fingerprint(entry), verdict.decision_fingerprint)

    def test_manifest_entries_track_their_live_module_constants(self):
        # Review finding 5: the version only means something if the manifest
        # actually references the constants the decision path uses, rather than
        # holding a stale hand-copied value.
        self.assertEqual(PARAMETER_SET["drift_sigma_threshold"], DRIFT_SIGMA_THRESHOLD)
        self.assertEqual(PARAMETER_SET["regime_critical_floor_default"], REGIME_CRITICAL_FLOOR_DEFAULT)
        self.assertEqual(PARAMETER_SET["drift_critical_floor"], DRIFT_CRITICAL_FLOOR)
        self.assertEqual(PARAMETER_SET["escalation_dwell_threshold"], ESCALATION_DWELL_THRESHOLD)
        self.assertEqual(PARAMETER_SET["escalation_lock_seconds"], ESCALATION_LOCK_SECONDS)
        self.assertEqual(PARAMETER_SET["regime_risk_floor"], REGIME_RISK_FLOOR)
        self.assertEqual(
            {k: list(v) for k, v in VITALS_PHYSICAL_BOUNDS.items()},
            PARAMETER_SET["vitals_physical_bounds"],
        )

    def test_manifest_is_a_snapshot_immune_to_runtime_mutation(self):
        # Review round 2 finding 5: PARAMETER_SET aliased mutable module dicts, so
        # a runtime mutation shifted the effective config while the version stamp
        # stayed byte-identical. It must be a deep copy, and drift must be visible.
        self.assertIsNot(PARAMETER_SET["pediatric_norms"], PEDIATRIC_NORMS)
        original = PEDIATRIC_NORMS["child"]["hr_high"]
        try:
            PEDIATRIC_NORMS["child"]["hr_high"] = original + 99
            self.assertNotEqual(PARAMETER_SET["pediatric_norms"]["child"]["hr_high"],
                                PEDIATRIC_NORMS["child"]["hr_high"])
        finally:
            PEDIATRIC_NORMS["child"]["hr_high"] = original

    def test_regime_risk_floor_covers_every_regime(self):
        self.assertEqual(set(REGIME_RISK_FLOOR), {r.value for r in OperationalRegime})
        # monotone with severity
        self.assertLess(REGIME_RISK_FLOOR["stable"], REGIME_RISK_FLOOR["caution"])
        self.assertLess(REGIME_RISK_FLOOR["caution"], REGIME_RISK_FLOOR["warning"])
        self.assertLess(REGIME_RISK_FLOOR["warning"], REGIME_RISK_FLOOR["critical"])

    def test_engine_uses_the_declared_escalation_constants(self):
        # Review finding 5: EscalationPolicy(dwell_threshold=5) would carry the
        # same version stamp. Assert the engine's actual policy IS the declared one.
        policy = ObserveClinicalEngine()._get_policy("x")
        self.assertEqual(policy.dwell_threshold, ESCALATION_DWELL_THRESHOLD)
        self.assertEqual(policy.lock_seconds, ESCALATION_LOCK_SECONDS)

    def test_version_is_a_stable_sha256_of_the_manifest(self):
        recomputed = hashlib.sha256(_canonical_json(PARAMETER_SET).encode("utf-8")).hexdigest()
        self.assertEqual(recomputed, PARAMETER_SET_VERSION)
        self.assertEqual(len(PARAMETER_SET_VERSION), 64)

    def test_mutating_a_declared_constant_would_change_the_version(self):
        # Spot-check a representative entry actually participates in the hash
        # (not a tautology over an arbitrary dict — these keys are the real ones).
        for key in ("drift_sigma_threshold", "heavy_path_entropy_trigger",
                    "escalation_lock_seconds", "vitals_physical_bounds",
                    "regime_distribution_bands"):
            mutated = dict(PARAMETER_SET)
            mutated[key] = "__MUTATED__"
            self.assertNotEqual(
                hashlib.sha256(_canonical_json(mutated).encode("utf-8")).hexdigest(),
                PARAMETER_SET_VERSION,
            )

    def test_fingerprint_moves_with_the_parameter_version(self):
        engine = ObserveClinicalEngine()
        engine.evaluate(make_vitals(oxygen_saturation=88.0))
        entry = engine.audit_ledger.entries[-1]
        self.assertNotEqual(_replay_fingerprint(entry, parameter_set_version="different-version"),
                            entry["data"]["decision_fingerprint"])


class VendoredCopyStaysInSync(unittest.TestCase):
    """TEMPORARY STOPGAP (owner-approved 2026-10-29), not the original assertion.

    The original test asserted that the root and sentinel_os/ copies of
    observe_consolidated.py are byte-identical (review finding 8). They have
    not been since 2026-09-08. Since PR-2 the root engine is observe-perceive
    e8186599 (byte-identical, with its four sibling modules), while sentinel_os/
    still holds the older upstream snapshot 717c2e2 until PR-3 re-syncs it.
    This test asserts both facts and still fails loudly (never skips) if either
    side, or any pinned file, changes unexpectedly. The identical assertion
    between root and sentinel_os/ is restored by PR-4 of RECONCILE_UPSTREAM_PLAN.md.
    """

    # Root: observe-perceive e8186599 (merge of #67). Also recorded in VENDORED.md.
    ROOT_UPSTREAM_COMMIT = "e8186599e2399157feaa1592bf1399ff37d5c3d2"
    ROOT_PINS = {
        "observe_consolidated.py": "0a1cc62de6d391b21476b6116b669081ed47141ac3a6c71a2d0a8d5899ddd566",
        "cassette.py": "7e5465d65e2095df547641bd4d814ef496d3d9ac3f81e8ac77c14fb6055965d4",
        "pediatric_cassette.py": "71774badff2c698e694c61189ec59003b23c288b0efe215304d88d987e991f20",
        "kalman_trajectory.py": "03be64ba12cbcb3c9fce5b0e20d839bac83537775bbc1a09f9d6c6f45a2e5e9a",
        "governance_contracts.py": "2145fb7d4daf1e99e74858a92bd86185650fcf6debb470273411a280091e1aca",
    }
    # sentinel_os/: observe-perceive 717c2e2, observe_consolidated.py. Also recorded in VENDORED.md.
    SNAPSHOT_COMMIT = "717c2e2"
    SNAPSHOT_SHA256 = "66feebf5974bd60fcb7721bcb93477edad7a8fe5a0b7a21bf20e860b6846b53c"

    def test_root_is_the_pinned_upstream_engine_and_sentinel_os_is_the_pinned_snapshot(self):
        here = pathlib.Path(__file__).parent
        for name, pin in self.ROOT_PINS.items():
            path = here / name
            self.assertTrue(path.exists(), f"{name} is missing")
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                pin,
                msg=(
                    f"{name} no longer matches observe-perceive {self.ROOT_UPSTREAM_COMMIT}. These files are "
                    "copied, never edited here. If this was a deliberate re-sync, update the pins here and "
                    "in VENDORED.md together."
                ),
            )
        vendored = here / "sentinel_os" / "observe_consolidated.py"
        self.assertTrue(vendored.exists(), "sentinel_os/observe_consolidated.py is missing")
        self.assertEqual(
            hashlib.sha256(vendored.read_bytes()).hexdigest(),
            self.SNAPSHOT_SHA256,
            msg=(
                "sentinel_os/observe_consolidated.py no longer matches the pinned upstream snapshot "
                f"(observe-perceive {self.SNAPSHOT_COMMIT}). If this was a deliberate re-sync, update the "
                "pin here and in VENDORED.md together."
            ),
        )
        manifest = (here / "VENDORED.md").read_text(encoding="utf-8")
        for pin in (self.SNAPSHOT_SHA256, *self.ROOT_PINS.values()):
            self.assertIn(pin, manifest, msg="VENDORED.md does not record the same pin as this test")
        for name in self.ROOT_PINS:
            rows = [ln for ln in manifest.splitlines() if ln.startswith(f"| `{name}` |")]
            self.assertEqual(len(rows), 1, msg=f"VENDORED.md must have exactly one row for the root {name}")
            self.assertTrue(
                rows[0].rstrip().endswith("| identical |"),
                msg=f"VENDORED.md must declare the root {name} as 'identical' to observe-perceive",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
