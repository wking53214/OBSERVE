"""Differential test for the PR-2b re-sync of the root engine.

Before PR-2b the root `observe_consolidated.py` was OBSERVE's own engine. It is now observe-perceive
e8186599 (byte-identical), with OBSERVE's clinical rule for when the behavioral engine runs kept by
`observe_engine_gate.ENGINE_GATE`. The old engine no longer exists here, so its behaviour on a fixed,
deterministic corpus of 600 readings was recorded once, before the re-sync, in
`testdata/old_engine_corpus_20261029.json`. This test replays the same corpus through the engine in
force and compares.

What it proves:

1. Parity. With the one input-handling difference removed from the old engine's run (a junk
   `previous_o2`), the engine in force agrees with the old engine on EVERY reading: regime,
   escalation, engine set, unassessable flag and risk. There is no clinical scoring difference.
2. Every remaining difference against the old engine's run as it actually ran is on the allow-list:
   either the old engine crashed on a junk context value and the new engine scores the reading, or the
   reading carries an impossible `previous_o2` (200) the new engine drops, or the reading is on a patient
   whose earlier readings were affected by one of those two. Zero unclassified differences.
3. The chosen gate matters: the same corpus under upstream's widened rule selects the behavioral
   engine more often, so the equality in 1 is not a coincidence of an unused setting.
4. Faulted and junk-context input always produces a verdict with a fingerprint, never an exception, the
   fingerprint is reproducible across processes, and the state-commitment chain verifies.
"""

import json
import os
import pathlib
import random
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

from observe_consolidated import ObserveClinicalEngine, VitalsSnapshot
from observe_engine_gate import ENGINE_GATE, make_engine
from pediatric_cassette import (
    ENGINE_GATE_CONSERVATIVE_LEGACY,
    ENGINE_GATE_WIDENED_PROVISIONAL,
    PediatricCassette,
)

_FIXTURE = pathlib.Path(__file__).parent / "testdata" / "old_engine_corpus_20261029.json"
_JUNK = (200, "x")


def _corpus():
    """The plan's 600-reading corpus (RECONCILE_UPSTREAM_PLAN.md, Appendix A). Same seed, same draws."""
    rng = random.Random(20261029)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    patients = [f"P{i}" for i in range(12)]
    clock = {p: t0 for p in patients}
    readings = []
    for n in range(600):
        p = rng.choice(patients)
        clock[p] += timedelta(seconds=rng.choice([30, 60, 120, 400]))
        kind = rng.random()
        if kind < 0.55:
            hr, o2, rr, temp = rng.uniform(70, 150), rng.uniform(90, 100), rng.uniform(15, 40), rng.uniform(36, 39.5)
        elif kind < 0.85:
            hr, o2, rr, temp = rng.uniform(130, 190), rng.uniform(78, 92), rng.uniform(35, 60), rng.uniform(38.5, 41)
        elif kind < 0.93:
            hr, o2, rr, temp = (rng.uniform(70, 150), float("nan") if rng.random() < .5 else 250.0,
                                rng.uniform(15, 40), rng.uniform(36, 39))
        else:
            hr, o2, rr, temp = rng.uniform(70, 150), rng.uniform(90, 100), rng.uniform(15, 40), rng.uniform(36, 39)
        ctx = {"age_months": rng.choice([1, 6, 18, 48, None])}
        if kind >= 0.93:
            ctx["previous_o2"] = rng.choice([200, "x", 91])
        if rng.random() < .2:
            ctx["force_heavy"] = True
        readings.append((n, p, VitalsSnapshot(p, clock[p], hr, o2, rr, temp, context=ctx)))
    return readings


def _run(engine):
    """Replay the corpus; one row per reading, or an error row if the engine raised."""
    rows = []
    for n, _p, v in _corpus():
        try:
            r = engine.evaluate(v)
        except Exception as e:  # recorded, not hidden: the test asserts on it
            rows.append({"i": n, "error": type(e).__name__})
            continue
        rows.append({"i": n, "risk": round(r.risk_score, 9), "regime": r.regime.value, "esc": r.escalation_required,
                     "engines": list(r.active_engines), "unassess": r.unassessable})
    return rows


def _differences(old_rows, new_rows):
    """(reading, field, old, new) for every field that differs; an error on one side only counts as 'error'."""
    out = []
    for o, n in zip(old_rows, new_rows):
        if ("error" in o) != ("error" in n):
            out.append((o["i"], "error", o.get("error"), n.get("error")))
            continue
        if "error" in o:
            continue
        for k in ("regime", "esc", "engines", "unassess", "risk"):
            if o[k] != n[k]:
                out.append((o["i"], k, o[k], n[k]))
    return out


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        cls.readings = _corpus()
        cls.legacy_rows = _run(make_engine())

    def test_the_engine_in_force_uses_the_legacy_gate(self):
        self.assertEqual(ENGINE_GATE, ENGINE_GATE_CONSERVATIVE_LEGACY)
        engine = make_engine()
        self.assertEqual(engine._cassette.engine_gate, ENGINE_GATE_CONSERVATIVE_LEGACY)
        self.assertEqual(engine._cassette.identity_extras, {"engine_gate": ENGINE_GATE_CONSERVATIVE_LEGACY})

    def test_a_caller_that_passes_its_own_cassette_keeps_it(self):
        own = PediatricCassette(engine_gate=ENGINE_GATE_WIDENED_PROVISIONAL)
        self.assertIs(make_engine(cassette=own)._cassette, own)


class ParityWithTheOldEngine(_Base):
    def test_the_corpus_is_the_recorded_corpus(self):
        self.assertEqual(self.fixture["corpus_seed"], 20261029)
        self.assertEqual(len(self.readings), 600)
        self.assertEqual(len(self.fixture["as_run"]), 600)
        self.assertEqual(len(self.fixture["junk_previous_o2_stripped"]), 600)
        self.assertEqual(sum(1 for r in self.fixture["as_run"] if "error" in r), 12)
        self.assertEqual(sum(1 for r in self.fixture["junk_previous_o2_stripped"] if "error" in r), 0)

    def test_with_the_junk_value_removed_the_new_engine_agrees_with_the_old_on_every_reading(self):
        diffs = _differences(self.fixture["junk_previous_o2_stripped"], self.legacy_rows)
        self.assertEqual(diffs, [], msg=f"{len(diffs)} unexplained differences; first: {diffs[:5]}")

    def test_every_difference_against_the_old_engine_as_it_ran_is_classified(self):
        diffs = _differences(self.fixture["as_run"], self.legacy_rows)
        # Which readings carry a junk previous_o2, and for each patient the first one that does.
        junk_at = {}
        first_junk = {}
        for n, p, v in self.readings:
            if v.context.get("previous_o2") in _JUNK:
                junk_at[n] = v.context["previous_o2"]
                first_junk.setdefault(p, n)
        patient_of = {n: p for n, p, _v in self.readings}
        unclassified = []
        classes = {"old_crashed_new_scores": 0, "impossible_previous_o2_dropped": 0, "after_an_affected_reading": 0}
        for i, field, old, new in diffs:
            if field == "error":
                self.assertEqual(junk_at.get(i), "x", msg=f"reading {i}")
                self.assertEqual((old, new), ("TypeError", None), msg=f"reading {i}")
                classes["old_crashed_new_scores"] += 1
            elif junk_at.get(i) == 200:
                classes["impossible_previous_o2_dropped"] += 1
            elif first_junk.get(patient_of[i], 10 ** 9) < i:
                classes["after_an_affected_reading"] += 1
            else:
                unclassified.append((i, field, old, new))
        self.assertEqual(unclassified, [], msg=f"unclassified differences: {unclassified}")
        # Pinned so a change in either direction is noticed and decided on purpose.
        self.assertEqual(len(diffs), 40)
        self.assertEqual(classes, {"old_crashed_new_scores": 12, "impossible_previous_o2_dropped": 13,
                                   "after_an_affected_reading": 15})

    def test_regime_and_escalation_differ_only_on_patients_with_an_affected_reading(self):
        diffs = [d for d in _differences(self.fixture["as_run"], self.legacy_rows) if d[1] in ("regime", "esc")]
        self.assertEqual(sorted({d[0] for d in diffs}),
                         [195, 270, 271, 295, 350, 357, 492, 510, 527, 556, 558, 576])

    def test_the_new_engine_never_raises_on_the_corpus(self):
        self.assertEqual([r for r in self.legacy_rows if "error" in r], [])


class TheGateMatters(_Base):
    def test_upstreams_widened_rule_selects_the_behavioral_engine_more_often(self):
        widened_rows = _run(ObserveClinicalEngine())  # upstream's default: widened_provisional
        widened = _differences(self.fixture["junk_previous_o2_stripped"], widened_rows)
        engine_set = [d for d in widened if d[1] == "engines"]
        self.assertGreater(len(engine_set), 0)
        # every one is the widened rule ADDING the behavioral engine, never removing anything
        for _i, _f, old, new in engine_set:
            self.assertEqual(sorted(set(new) - set(old)), ["behavioral"])
            self.assertEqual(set(old) - set(new), set())
        legacy = _differences(self.fixture["junk_previous_o2_stripped"], self.legacy_rows)
        self.assertEqual([d for d in legacy if d[1] == "engines"], [])


class PropertiesOfTheEngineInForce(_Base):
    def test_faulted_and_junk_context_input_always_yields_a_verdict_with_a_fingerprint(self):
        engine = make_engine()
        for n, _p, v in self.readings:
            verdict = engine.evaluate(v)
            self.assertEqual(len(verdict.decision_fingerprint), 64, msg=n)
        faulted = [r for r in self.legacy_rows if r["unassess"]]
        self.assertGreater(len(faulted), 0)

    def test_the_state_commitment_chain_verifies_after_the_corpus(self):
        engine = make_engine()
        for _n, _p, v in self.readings:
            engine.evaluate(v)
        self.assertTrue(engine.audit_ledger.verify_integrity())
        entries = engine.audit_ledger.entries
        self.assertEqual(len(entries), 600)
        last = {}
        chained = 0
        for e in entries:
            data = e["data"]
            subject = data["vitals"]["patient_id"]
            pred = data.get("predecessor_state_commitment")
            if subject in last:
                self.assertEqual(pred, last[subject], msg=subject)
                chained += 1
            else:
                self.assertEqual(pred, "", msg=f"{subject}: the first reading of a subject has no predecessor")
            last[subject] = data["state_commitment"]
        self.assertEqual(len(last), 12)
        self.assertEqual(chained, 600 - 12)

    def test_the_fingerprint_is_the_same_across_processes_and_hash_seeds(self):
        script = (
            "import sys\n"
            "from datetime import datetime, timezone\n"
            "from observe_engine_gate import make_engine\n"
            "from observe_consolidated import VitalsSnapshot\n"
            "v = VitalsSnapshot('P-PROC', datetime(2026, 1, 1, tzinfo=timezone.utc), 120.0, 88.0, 40.0, 38.9,"
            " context={'age_months': 18})\n"
            "print(make_engine().evaluate(v).decision_fingerprint)\n"
        )
        here = str(pathlib.Path(__file__).parent)
        seen = set()
        for seed in ("1", "2", "random"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=here)
            out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env,
                                 cwd=here, check=True)
            seen.add(out.stdout.strip().splitlines()[-1])
        self.assertEqual(len(seen), 1, msg=seen)

    def test_the_legacy_gate_is_named_in_the_stored_entry_and_moves_the_fingerprint(self):
        _n, _p, v = self.readings[0]
        legacy = make_engine()
        legacy.evaluate(v)
        default = ObserveClinicalEngine()
        default.evaluate(v)
        e_legacy = legacy.audit_ledger.entries[-1]["data"]
        e_default = default.audit_ledger.entries[-1]["data"]
        self.assertEqual(e_legacy["cassette"]["engine_gate"], ENGINE_GATE_CONSERVATIVE_LEGACY)
        self.assertNotIn("engine_gate", e_default["cassette"])
        self.assertNotEqual(e_legacy["decision_fingerprint"], e_default["decision_fingerprint"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
