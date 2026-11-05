"""OBSERVE's CNS connector: one gate per end, fail-closed, bound to content.

These skip where ``cns`` is not installed. CI installs requirements-cns.txt and sets OBSERVE_REQUIRE_CNS=1, so there
they cannot skip.
"""

import importlib
import os
from datetime import datetime, timezone

import pytest

if os.environ.get("OBSERVE_REQUIRE_CNS") == "1":  # CI: a missing cns is a failure, not a skip
    import cns.gate  # noqa: F401
else:
    pytest.importorskip("cns.gate", reason="needs the pinned CNS package")

import cns_connector  # noqa: E402
from cns_connector import CnsNotInstalled, ObserveCnsGate, cns_available  # noqa: E402
from cns.gate import GateOutcome, GatePosition  # noqa: E402
from observe_consolidated import FusedVerdict, OperationalRegime, VitalsSnapshot, validate_vitals  # noqa: E402


def make_vitals(**overrides):
    defaults = dict(
        patient_id="P001",
        timestamp=datetime.now(timezone.utc),
        heart_rate=100,
        oxygen_saturation=97.0,
        respiratory_rate=24,
        temperature=37.0,
        context={"age_months": 24},
    )
    defaults.update(overrides)
    return VitalsSnapshot(**defaults)


def make_verdict(**overrides):
    defaults = dict(
        risk_score=0.3,
        regime=OperationalRegime.STABLE,
        confidence=0.9,
        entropy=0.1,
        active_engines=["heuristic"],
        triggered_rules=[],
        timestamp=datetime.now(timezone.utc),
        audit_hash="a" * 64,
        decision_fingerprint="f" * 64,
    )
    defaults.update(overrides)
    return FusedVerdict(**defaults)


def test_alpha_passes_plausible_vitals():
    gate = ObserveCnsGate("alpha")
    result = gate.check(make_vitals())
    assert result.outcome is GateOutcome.PASS
    assert result.position is GatePosition.ALPHA
    assert result.gate == "observe.vitals_ingress"


def test_alpha_asks_for_a_new_reading_on_a_sensor_fault():
    faulty = make_vitals(heart_rate=-5)
    assert validate_vitals(faulty), "fixture must actually be a sensor fault"
    result = ObserveCnsGate("alpha").check(faulty)
    assert result.outcome is GateOutcome.RETRY
    assert "re-read required" in result.reason


def test_omega_passes_a_verdict_backed_by_evidence():
    engine = ObserveClinicalEngine()
    result = ObserveCnsGate("omega", engine=engine).check(engine.evaluate(make_vitals()))
    assert result.outcome is GateOutcome.PASS
    assert result.position is GatePosition.OMEGA
    assert result.gate == "observe.verdict_egress"


def test_omega_refuses_a_partial_assessment():
    partial = make_verdict(unassessable=True, validation_faults=["heart_rate=-5"])
    result = ObserveCnsGate("omega").check(partial)
    assert result.outcome is GateOutcome.RETRY
    assert "partial assessment" in result.reason


def test_omega_refuses_a_verdict_no_engine_backed():
    result = ObserveCnsGate("omega").check(make_verdict(active_engines=[]))
    assert result.outcome is GateOutcome.RETRY
    assert "no engine produced evidence" in result.reason


def test_verdict_binds_to_the_content_it_judged():
    gate = ObserveCnsGate("alpha")
    result = gate.check(make_vitals(heart_rate=100))
    assert result.bound()
    assert result.binds(result.subject, result.subject_digest)
    other = gate.check(make_vitals(heart_rate=101))
    assert not result.binds(other.subject, other.subject_digest)


def test_wrong_candidate_for_the_end_is_a_fault_not_a_pass():
    result = ObserveCnsGate("alpha").check(make_verdict())
    assert result.outcome is GateOutcome.TERMINAL_BREACH
    assert "fault" in result.reason


def test_a_raising_check_is_a_fault_not_a_pass(monkeypatch):
    def explode(vitals):
        raise RuntimeError("boom")

    monkeypatch.setattr(cns_connector, "validate_vitals", explode)
    result = ObserveCnsGate("alpha").check(make_vitals())
    assert result.outcome is GateOutcome.TERMINAL_BREACH
    assert "boom" in result.reason


def test_unknown_position_is_rejected():
    with pytest.raises(ValueError):
        ObserveCnsGate("middle")


def test_missing_cns_raises_with_the_install_command(monkeypatch):
    real_import = importlib.import_module

    def no_cns(name, *args, **kwargs):
        if name == "cns.gate":
            raise ModuleNotFoundError("No module named 'cns'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", no_cns)
    assert cns_available() is False
    with pytest.raises(CnsNotInstalled, match="cns @ git"):
        ObserveCnsGate("alpha")


# ------------------------------------------------- audit findings OBS-1 .. OBS-6

#
# These drive the real engine and its real audit ledger, so the OMEGA gate is judged on verdicts the engine
# actually produced, not on hand-built ones.

import dataclasses  # noqa: E402

from cns_composition.gate_chain import run_chain  # noqa: E402
from observe_consolidated import ObserveClinicalEngine, RiskOutput  # noqa: E402
from pediatric_cassette import PediatricCassette  # noqa: E402

READING_TIME = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
HEAVY = {"age_months": 24, "force_heavy": True}  # selects trajectory and drift, which abstain without history


def reading(**overrides):
    return make_vitals(**{"timestamp": READING_TIME, **overrides})


class AbstainingCassette(PediatricCassette):
    """Every engine says it has no data. Selected, run, and not one of them assessed the patient."""

    def engines(self):
        def abstain(name):
            def run(vitals):
                return RiskOutput(name, 0.0, 0.0, {"stable": 1.0, "caution": 0.0, "warning": 0.0, "critical": 0.0},
                                  [], READING_TIME, abstained=True)
            return run
        return {name: abstain(name) for name in super().engines()}


def evaluated(engine=None, **overrides):
    engine = engine or ObserveClinicalEngine()
    return engine, engine.evaluate(reading(**overrides))


def test_obs1_omega_refuses_a_verdict_every_engine_abstained_from():
    engine, verdict = evaluated(ObserveClinicalEngine(cassette=AbstainingCassette()))
    assert verdict.active_engines, "fixture: the engines were selected, so active_engines is not empty"
    result = ObserveCnsGate("omega", engine=engine).check(verdict)
    assert result.outcome is GateOutcome.RETRY
    assert "no engine produced evidence" in result.reason


def test_obs1_omega_passes_a_real_verdict_an_engine_backed():
    engine, verdict = evaluated()
    result = ObserveCnsGate("omega", engine=engine).check(verdict)
    assert result.outcome is GateOutcome.PASS
    assert result.bound()


def test_obs1_omega_without_an_evidence_source_never_passes():
    # Without the engine's ledger the gate cannot tell a selected engine from one that assessed the patient.
    result = ObserveCnsGate("omega").check(make_verdict())
    assert result.outcome is GateOutcome.TERMINAL_BREACH
    assert "evidence cannot be confirmed" in result.reason


def test_obs1_omega_refuses_a_verdict_naming_an_engine_that_does_not_exist():
    engine, _ = evaluated()
    fake = make_verdict(active_engines=["ghost_engine"], decision_fingerprint="", audit_hash="")
    assert ObserveCnsGate("omega", engine=engine).check(fake).outcome is GateOutcome.TERMINAL_BREACH


def test_obs2_a_mandatory_engine_that_abstained_is_not_a_pass():
    engine, verdict = evaluated(context=HEAVY)
    gate = ObserveCnsGate("omega", engine=engine, mandatory_engines={"heuristic", "trajectory"})
    result = gate.check(verdict)
    assert result.outcome is GateOutcome.RETRY
    assert "trajectory" in result.reason and "abstained" in result.reason


def test_obs2_a_mandatory_engine_that_never_ran_is_not_a_pass():
    engine, verdict = evaluated()  # heart rate 100: the behavioral engine is not selected
    assert "behavioral" not in verdict.active_engines
    gate = ObserveCnsGate("omega", engine=engine, mandatory_engines={"heuristic", "behavioral"})
    result = gate.check(verdict)
    assert result.outcome is GateOutcome.RETRY
    assert "behavioral" in result.reason and "not run" in result.reason


def test_obs2_an_advisory_engine_that_abstained_does_not_block():
    engine, verdict = evaluated(context=HEAVY)
    gate = ObserveCnsGate("omega", engine=engine, mandatory_engines={"heuristic"},
                          advisory_engines={"trajectory", "drift"})
    assert gate.check(verdict).outcome is GateOutcome.PASS


def test_obs2_only_engines_the_policy_names_count_as_evidence():
    engine, verdict = evaluated()  # only heuristic is selected, and the policy does not name it
    gate = ObserveCnsGate("omega", engine=engine, advisory_engines={"bayesian"})
    assert gate.check(verdict).outcome is GateOutcome.RETRY


def test_obs2_the_policy_is_checked_when_the_gate_is_built():
    engine = ObserveClinicalEngine()
    with pytest.raises(ValueError):
        ObserveCnsGate("omega", engine=engine, mandatory_engines={"heuristic"}, advisory_engines={"heuristic"})
    with pytest.raises(ValueError):
        ObserveCnsGate("omega", engine=engine, mandatory_engines={"no_such_engine"})
    with pytest.raises(ValueError):
        ObserveCnsGate("alpha", mandatory_engines={"heuristic"})
    with pytest.raises(TypeError):
        ObserveCnsGate("omega", engine=engine, mandatory_engines="heuristic")


def test_obs5_validation_faults_without_the_unassessable_flag_are_a_retry():
    inconsistent = make_verdict(validation_faults=["heart_rate=nan is not a finite number"], unassessable=False)
    result = ObserveCnsGate("omega").check(inconsistent)
    assert result.outcome is GateOutcome.RETRY
    assert "partial assessment" in result.reason


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_obs6_a_non_finite_reading_asks_for_a_new_reading(value):
    result = ObserveCnsGate("alpha").check(reading(heart_rate=value))
    assert result.outcome is GateOutcome.RETRY
    assert "re-read required" in result.reason
    assert result.bound()


def test_retry_and_terminal_breach_survive_the_chain():
    alpha, omega = ObserveCnsGate("alpha"), ObserveCnsGate("omega")
    retry = run_chain([(alpha, reading(heart_rate=float("nan")))], [(omega, make_verdict())])
    assert retry.outcome is GateOutcome.RETRY and not retry.omega_ran
    both = run_chain([(alpha, reading(heart_rate=-5)), (alpha, make_verdict())], [(omega, make_verdict())])
    assert both.outcome is GateOutcome.TERMINAL_BREACH and not both.omega_ran
    late = run_chain([(alpha, reading())], [(omega, make_verdict(validation_faults=["x"]))])
    assert late.outcome is GateOutcome.RETRY and late.omega_ran


def test_obs3_omega_subject_names_the_patient_the_ledger_records():
    engine, verdict = evaluated(patient_id="PATIENT_A")
    result = ObserveCnsGate("omega", engine=engine).check(verdict)
    assert result.subject == f"observe:omega:PATIENT_A:{verdict.decision_fingerprint}"


def test_obs3_alpha_and_omega_for_different_patients_do_not_pass_as_one_run():
    engine, verdict_a = evaluated(patient_id="PATIENT_A")
    vitals_b = reading(patient_id="PATIENT_B", oxygen_saturation=84.0, heart_rate=190)
    run = run_chain([(ObserveCnsGate("alpha", patient_id="PATIENT_B"), vitals_b)],
                    [(ObserveCnsGate("omega", engine=engine, patient_id="PATIENT_B"), verdict_a)])
    assert run.outcome is GateOutcome.TERMINAL_BREACH
    assert "PATIENT_A" in run.results[-1].reason


def test_obs3_alpha_refuses_vitals_for_another_patient():
    result = ObserveCnsGate("alpha", patient_id="PATIENT_B").check(reading(patient_id="PATIENT_A"))
    assert result.outcome is GateOutcome.TERMINAL_BREACH


def test_obs4_a_verdict_edited_after_evaluation_is_refused():
    engine, verdict = evaluated(oxygen_saturation=84.0, heart_rate=190)
    assert verdict.regime is not OperationalRegime.STABLE
    edited = dataclasses.replace(verdict, regime=OperationalRegime.STABLE, risk_score=0.0)
    result = ObserveCnsGate("omega", engine=engine).check(edited)
    assert result.outcome is GateOutcome.TERMINAL_BREACH


def test_obs4_a_forged_fingerprint_is_refused():
    engine, verdict = evaluated()
    forged = dataclasses.replace(verdict, decision_fingerprint="0" * 64)
    assert ObserveCnsGate("omega", engine=engine).check(forged).outcome is GateOutcome.TERMINAL_BREACH


def test_obs4_an_edited_audit_record_is_refused():
    engine, verdict = evaluated()
    engine.audit_ledger.entries[-1]["data"]["verdict"]["regime"] = "critical"
    assert ObserveCnsGate("omega", engine=engine).check(verdict).outcome is GateOutcome.TERMINAL_BREACH


def test_obs4_omega_binding_leaves_wall_clock_time_out():
    first, v1 = evaluated(ObserveClinicalEngine())
    second, v2 = evaluated(ObserveClinicalEngine())
    assert v1.timestamp != v2.timestamp or v1.audit_hash != v2.audit_hash
    r1 = ObserveCnsGate("omega", engine=first).check(v1)
    r2 = ObserveCnsGate("omega", engine=second).check(v2)
    assert (r1.subject, r1.subject_digest) == (r2.subject, r2.subject_digest)
