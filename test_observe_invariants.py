"""
Invariant / property tests for the consolidated OBSERVE clinical engine.

Harvested from the adversarial analysis of the rejected "URE" resilience
candidate (RESILIENCE_INTEGRATION_ASSESSMENT.md, section 12). Each test locks
out a failure mode the candidate exhibited, restated against OBSERVE's own
mechanisms. IDs match the assessment.

Run: python3 -m pytest test_observe_invariants.py -v
"""

import math
import unittest
from datetime import datetime, timezone

from observe_consolidated import (
    ObserveClinicalEngine,
    VitalsSnapshot,
    BayesianFusion,
    RiskAdapters,
    OperationalRegime,
    regime_distribution,
    validate_vitals,
    compute_decision_fingerprint,
    PARAMETER_SET,
    PARAMETER_SET_VERSION,
    _canonical_json,
    REGIME_DISTRIBUTION_BANDS,
)
import hashlib


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
        self.assertEqual(verdict.regime, OperationalRegime.WARNING)
        self.assertTrue(verdict.validation_faults)
        self.assertTrue(verdict.escalation_required)

    def test_inf_vital_rejected(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(temperature=float("inf")))
        self.assertTrue(verdict.validation_faults)
        self.assertNotEqual(verdict.regime, OperationalRegime.STABLE)

    def test_out_of_range_vital_rejected(self):
        engine = ObserveClinicalEngine()
        verdict = engine.evaluate(make_vitals(heart_rate=999.0))
        self.assertIn("heart_rate=out_of_range(999.0)", verdict.validation_faults)
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
        engine = ObserveClinicalEngine()
        v = make_vitals(patient_id="replay", oxygen_saturation=88.0)
        fp1 = compute_decision_fingerprint(v, engine.evaluate(v))
        fp2 = compute_decision_fingerprint(v, ObserveClinicalEngine().evaluate(v))
        self.assertEqual(fp1, fp2)

    def test_changing_any_calibration_constant_changes_the_version(self):
        for key in PARAMETER_SET:
            if key == "schema":
                continue
            mutated = dict(PARAMETER_SET)
            mutated[key] = "__MUTATED__"
            new_version = hashlib.sha256(_canonical_json(mutated).encode("utf-8")).hexdigest()
            self.assertNotEqual(new_version, PARAMETER_SET_VERSION,
                                msg=f"PARAMETER_SET['{key}'] is not covered by the version hash")

    def test_fingerprint_moves_with_the_parameter_version(self):
        engine = ObserveClinicalEngine()
        v = make_vitals(oxygen_saturation=88.0)
        verdict = engine.evaluate(v)
        fp_real = compute_decision_fingerprint(v, verdict)
        verdict.parameter_set_version = "different-version"
        self.assertNotEqual(compute_decision_fingerprint(v, verdict), fp_real)


if __name__ == "__main__":
    unittest.main(verbosity=2)
