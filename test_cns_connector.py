"""OBSERVE's CNS connector: one gate per end, fail-closed, bound to content."""

import importlib
from datetime import datetime, timezone

import pytest

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
    result = ObserveCnsGate("omega").check(make_verdict())
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
