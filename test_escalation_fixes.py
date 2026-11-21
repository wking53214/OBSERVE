"""Guards for the four escalation fixes, re-checked on the re-synced engine (observe-perceive d596262).

Each test drives one patient through a short, fixed sequence of readings and checks whether an alert
(`escalation_required`) fires and why (`escalation_kind`). The vitals are chosen to land clearly in
normal, warning and critical territory. They are synthetic; they are not the 600-reading corpus.

The last test pins a behavior that is NOT yet reviewed: after a critical alert, a dip to warning and a
return to critical inside the cooldown sends no second alert. It is pinned so a change is deliberate.
See docs/CLINICAL_REVIEW_SHEET_v1.md, item 1.
"""

import unittest
from datetime import datetime, timedelta, timezone

from observe_consolidated import OperationalRegime, VitalsSnapshot
from observe_engine_gate import make_engine

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_NORMAL = (110, 98, 25, 37.0)
_WARNING = (150, 91, 40, 38.8)
_CRITICAL = (185, 80, 55, 40.8)
_OXYGEN_CASE = (138, 86, 34, 39.1)  # 24 months old: SpO2 86, temp 39.1, HR 138, RR 34


def _run(steps, age_months=24):
    """steps: (seconds, (hr, spo2, rr, temp)). Returns one verdict per step."""
    engine = make_engine()
    out = []
    for secs, (hr, o2, rr, temp) in steps:
        v = VitalsSnapshot("PX", _T0 + timedelta(seconds=secs), hr, o2, rr, temp, context={"age_months": age_months})
        out.append(engine.evaluate(v))
    return out


class TheFourEscalationFixes(unittest.TestCase):
    def test_a_cooldown_does_not_hide_a_worsening_patient(self):
        r = _run([(0, _NORMAL), (30, _NORMAL), (60, _WARNING), (90, _WARNING), (120, _WARNING), (180, _CRITICAL)])
        self.assertTrue(r[2].escalation_required)
        self.assertEqual(r[2].escalation_kind, "new_escalation")
        self.assertFalse(r[3].escalation_required)  # a repeat at the same severity stays quiet
        self.assertEqual(r[5].regime, OperationalRegime.CRITICAL)
        self.assertTrue(r[5].escalation_required)
        self.assertEqual(r[5].escalation_kind, "severity_increase")

    def test_an_escalated_patient_who_worsens_alerts_on_one_reading(self):
        r = _run([(0, _NORMAL), (30, _NORMAL), (60, _WARNING), (90, _WARNING), (120, _WARNING), (600, _CRITICAL)])
        self.assertEqual(r[5].regime, OperationalRegime.CRITICAL)
        self.assertTrue(r[5].escalation_required)
        self.assertEqual(r[5].escalation_kind, "severity_increase")

    def test_a_missing_or_impossible_reading_does_not_block_the_next_real_alert(self):
        for bad_o2 in (float("nan"), 250.0):
            with self.subTest(bad_spo2=bad_o2):
                bad = (110, bad_o2, 25, 37.0)
                r = _run([(0, _NORMAL), (30, bad), (60, _CRITICAL), (90, _CRITICAL)])
                self.assertTrue(r[1].unassessable)
                self.assertEqual(r[2].regime, OperationalRegime.CRITICAL)
                self.assertTrue(r[2].escalation_required)
                self.assertFalse(r[3].escalation_required)

    def test_the_oxygen_case_is_not_averaged_away_by_history(self):
        history = [(i * 30, _NORMAL) for i in range(8)]
        for label, steps in (("with normal history", history + [(300, _OXYGEN_CASE)]), ("no history", [(0, _OXYGEN_CASE)])):
            with self.subTest(label):
                last = _run(steps)[-1]
                self.assertNotEqual(last.regime, OperationalRegime.STABLE)
                self.assertTrue(last.escalation_required)


class PinnedPendingClinicalReview(unittest.TestCase):
    def test_a_dip_then_critical_inside_the_cooldown_sends_no_second_alert(self):
        r = _run([(0, _NORMAL), (30, _NORMAL), (60, _CRITICAL), (90, _CRITICAL),
                  (120, _WARNING), (150, _WARNING), (180, _CRITICAL)])
        self.assertTrue(r[2].escalation_required)
        self.assertTrue(all(not x.escalation_required for x in r[3:]))
        self.assertEqual(r[6].regime, OperationalRegime.CRITICAL)


if __name__ == "__main__":
    unittest.main()
