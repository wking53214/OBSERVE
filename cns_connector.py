"""Optional CNS connector: OBSERVE as a CNS gate, usable at either end.

ALPHA guards the input. It judges the vitals before any scoring happens and
refuses readings that fail sensor-plausibility checks, so a faulty sensor
produces a request for a new reading rather than a score.

OMEGA guards the output. It judges the fused verdict before it leaves and
refuses any verdict that is only a partial assessment or that no engine
backed with evidence. A verdict with nothing behind it is abstention, not
normality.

Evidence at OMEGA. A verdict's active_engines lists the engines that were
SELECTED, including ones that ran and abstained, so it is not evidence. The
verdict does not record which engines abstained, so OMEGA needs the engine
that produced it (ObserveCnsGate("omega", engine=...)). The gate finds the
verdict's entry in that engine's audit ledger by audit_hash, re-runs each
recorded engine on the recorded reading through the engine's cassette, and
counts only the engines that did not abstain. An engine the cassette cannot
re-run (the stateful Kalman adapter) is never counted as evidence. Built
without an engine, OMEGA cannot confirm any evidence and never passes a
verdict; it refuses it as a fault.

Engine policy at OMEGA comes from the application, through the constructor,
never from the verdict being judged. mandatory_engines must each have run
and produced evidence, or the verdict is RETRY. advisory_engines count as
evidence but may be absent or abstain. When either set is given, only the
engines they name count as evidence. With no policy, no engine is mandatory
and any engine that produced evidence is enough: that is the safest reading
available without one, and it still never passes a verdict on selection
alone.

Record integrity at OMEGA. Before counting evidence the gate checks that the
ledger entry still hashes to its own immutable_hash, recomputes the decision
fingerprint from the recorded payload with observe_consolidated's
decision_fingerprint, and requires the verdict's fingerprint, regime, risk,
engines, parameter set and state commitments to equal the record. Any
difference is a TERMINAL_BREACH. OMEGA binds its result to the verdict
without its wall-clock timestamp and its ledger position (audit_hash), so the
same decision binds to the same digest in any run; the fingerprint is what
identifies the decision.

Patient linkage. FusedVerdict carries no patient id, so OMEGA takes it from
the verdict's ledger entry and names it in the subject
(observe:omega:<patient>:<fingerprint>). A caller that judges one patient
builds both gates with patient_id=..., and each end then refuses content
for any other patient as a TERMINAL_BREACH, so ALPHA vitals for one patient
and an OMEGA verdict for another cannot pass as one run.

OBSERVE never authorizes anything. These gates only decide whether an
observation or verdict is sound enough to pass along. Refusals that a fresh
reading can fix are RETRY. Anything else is TERMINAL_BREACH. An exception,
a bad candidate, or content that cannot be bound is a fault, and a fault is
never a pass.

CNS is imported only when a connector is built. Without it, building one
raises CnsNotInstalled with the install command and nothing else changes.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from types import ModuleType
from typing import Any, Dict, FrozenSet, Iterable, Optional, Union

from observe_consolidated import FusedVerdict, VitalsSnapshot, decision_fingerprint, validate_vitals

__all__ = [
    "CnsNotInstalled",
    "ObserveCnsGate",
    "cns_available",
]

INSTALL_HINT = "pip install -r requirements-cns.txt (cns @ git+https://github.com/wking53214/CNS.git@v4.0.0)"

_ALPHA = "alpha"
_OMEGA = "omega"

#: Written into a ledger entry beside the fingerprinted payload, not part of it.
_BESIDE_FINGERPRINT = ("decision_fingerprint", "predecessor_state_commitment", "state_commitment")
#: Left out of the OMEGA binding: wall-clock time and ledger position, not the decision.
_UNBOUND_VERDICT_FIELDS = ("timestamp", "audit_hash")


class CnsNotInstalled(ImportError):
    """Raised when cns.gate cannot be imported, or is too old to use."""


def _cns_gate() -> ModuleType:
    """Import cns.gate on demand, or say exactly what is missing."""
    try:
        module = importlib.import_module("cns.gate")
    except ImportError as exc:
        raise CnsNotInstalled(
            "OBSERVE's CNS connector needs the CNS package (cns.gate), which is not "
            f"installed. Install it with: {INSTALL_HINT}."
        ) from exc
    needed = ("GateOutcome", "GatePosition", "GateResult", "subject_digest")
    missing = [name for name in needed if not hasattr(module, name)]
    if missing:
        raise CnsNotInstalled(
            "the installed cns.gate lacks " + ", ".join(missing) + ". The connector "
            f"needs the pinned CNS release. Install it with: {INSTALL_HINT}."
        )
    return module


def cns_available() -> bool:
    """Whether the CNS gate contract can be imported in this environment."""
    try:
        _cns_gate()
    except CnsNotInstalled:
        return False
    return True


def _plain(value: Any, non_finite: bool = False) -> Any:
    """Reduce a value to the plain types a digest accepts.

    With non_finite, a NaN or infinite float is described as text, so a
    reading carrying one can still be bound and refused as a sensor fault.
    The digest refuses such floats by design; without the flag they stay
    unbindable, which is a fault.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if non_finite and isinstance(value, float) and not math.isfinite(value):
        return {"non_finite_float": repr(value)}
    if isinstance(value, dict):
        return {str(k): _plain(v, non_finite) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v, non_finite) for v in value]
    return value


def _engine_set(names: Iterable[str]) -> FrozenSet[str]:
    """An engine policy set. A bare string is refused: it would read as its letters."""
    if isinstance(names, str):
        raise TypeError("an engine policy is a collection of engine names, not one string")
    return frozenset(names)


def _record_problem(entry: Dict[str, Any], verdict: Any) -> str:
    """Why a verdict and its ledger entry disagree, or "" when they agree."""
    target = {k: v for k, v in entry.items() if k != "immutable_hash"}
    rehashed = hashlib.sha256(json.dumps(target, sort_keys=True, default=str).encode()).hexdigest()
    if rehashed != entry.get("immutable_hash"):
        return "the verdict's audit ledger entry has been altered"
    data = entry["data"]
    payload = {k: v for k, v in data.items() if k not in _BESIDE_FINGERPRINT}
    fingerprint = decision_fingerprint(payload)
    if fingerprint != data.get("decision_fingerprint") or fingerprint != verdict.decision_fingerprint:
        return "the decision fingerprint does not match the recorded decision"
    recorded = data["verdict"]
    expected = {
        "regime": recorded.get("regime"),
        "risk_score": recorded.get("risk_score"),
        "entropy": recorded.get("entropy"),
        "escalation_required": recorded.get("escalation_required"),
        "unassessable": bool(recorded.get("unassessable", False)),
        "validation_faults": list(data.get("validation_faults", [])),
        "active_engines": list(data.get("selected_engines", [])),
        "parameter_set_version": data.get("parameter_set_version"),
        "predecessor_state_commitment": data.get("predecessor_state_commitment"),
        "state_commitment": data.get("state_commitment"),
    }
    actual = {name: _plain(getattr(verdict, name)) for name in expected}
    differ = sorted(name for name in expected if actual[name] != expected[name])
    if differ:
        return "verdict does not match its audit record: " + ", ".join(differ)
    return ""


def _cassette_of(engine: Any) -> Any:
    """The cassette an ObserveClinicalEngine scores with."""
    return engine._cassette


class ObserveCnsGate:
    """OBSERVE as a CNS gate. ALPHA takes vitals, OMEGA takes a fused verdict."""

    def __init__(
        self,
        position: str = _ALPHA,
        *,
        engine: Any = None,
        mandatory_engines: Iterable[str] = (),
        advisory_engines: Iterable[str] = (),
        patient_id: Optional[str] = None,
    ) -> None:
        """Build the gate for one end.

        engine is the ObserveClinicalEngine whose verdicts OMEGA judges; its
        audit ledger and cassette are where OMEGA confirms evidence. The two
        engine sets are the application's policy (see the module docstring).
        All three belong to OMEGA only. patient_id, at either end, refuses
        content for any other patient.
        """
        cns = _cns_gate()
        if position not in (_ALPHA, _OMEGA):
            raise ValueError(f"position must be 'alpha' or 'omega', not {position!r}")
        mandatory, advisory = _engine_set(mandatory_engines), _engine_set(advisory_engines)
        if position == _ALPHA and (engine is not None or mandatory or advisory):
            raise ValueError("engine, mandatory_engines and advisory_engines belong to the omega end")
        if patient_id is not None and (not isinstance(patient_id, str) or not patient_id):
            raise ValueError("patient_id must be a non-empty string")
        if mandatory & advisory:
            raise ValueError(f"engines cannot be both mandatory and advisory: {sorted(mandatory & advisory)}")
        if engine is not None:
            known = set(_cassette_of(engine).engines())
            unknown = (mandatory | advisory) - known
            if unknown:
                raise ValueError(f"the engine's cassette cannot re-run {sorted(unknown)}, so the gate "
                                 "could never confirm their evidence")
        self._engine = engine
        self._patient_id = patient_id
        self._mandatory: FrozenSet[str] = mandatory
        self._advisory: FrozenSet[str] = advisory
        self._cns = cns
        self._position = position
        self.position = cns.GatePosition.ALPHA if position == _ALPHA else cns.GatePosition.OMEGA
        self.name = "observe.vitals_ingress" if position == _ALPHA else "observe.verdict_egress"

    def check(self, candidate: Union[VitalsSnapshot, FusedVerdict]) -> Any:
        """Judge one candidate and return a CNS GateResult bound to its content."""
        cns = self._cns
        expected = VitalsSnapshot if self._position == _ALPHA else FusedVerdict
        if not isinstance(candidate, expected):
            return self._result(
                cns.GateOutcome.TERMINAL_BREACH,
                f"fault: {self._position} end takes {expected.__name__}, "
                f"got {type(candidate).__name__}",
            )
        try:
            # A NaN or infinite vital is a sensor fault (RETRY, as documented), not
            # content that cannot be bound, so ALPHA describes it rather than refusing it.
            content = asdict(candidate)
            if self._position == _OMEGA:
                for name in _UNBOUND_VERDICT_FIELDS:
                    content.pop(name, None)
            digest = cns.subject_digest(_plain(content, non_finite=self._position == _ALPHA))
        except (TypeError, ValueError) as exc:
            return self._result(cns.GateOutcome.TERMINAL_BREACH, f"fault: content cannot be bound ({exc})")

        subject = self._subject(candidate)
        try:
            outcome, reason = self._judge(candidate)
        except Exception as exc:  # a gate that raises is a fault, never a pass
            return self._result(
                cns.GateOutcome.TERMINAL_BREACH,
                f"fault: gate raised {type(exc).__name__}: {exc}",
                subject, digest,
            )
        return self._result(outcome, reason, subject, digest)

    def _judge(self, candidate: Any) -> tuple:
        cns = self._cns
        if self._position == _ALPHA:
            if self._patient_id is not None and candidate.patient_id != self._patient_id:
                return cns.GateOutcome.TERMINAL_BREACH, (
                    f"fault: vitals are for patient {candidate.patient_id!r}, this gate judges {self._patient_id!r}")
            faults = validate_vitals(candidate)
            if faults:
                return cns.GateOutcome.RETRY, "sensor fault, re-read required: " + "; ".join(faults)
            return cns.GateOutcome.PASS, ""
        if candidate.unassessable or candidate.validation_faults:
            # Either one marks a partial assessment. A verdict carrying faults with the
            # flag cleared is inconsistent, and is refused the same way.
            faults = "; ".join(candidate.validation_faults) or "verdict is flagged unassessable"
            return cns.GateOutcome.RETRY, "partial assessment: " + faults
        if not candidate.active_engines:
            return cns.GateOutcome.RETRY, "no engine produced evidence for this verdict"
        if self._engine is None:
            return cns.GateOutcome.TERMINAL_BREACH, (
                "fault: evidence cannot be confirmed: this gate was built without the engine whose "
                "audit ledger records the verdict, and active_engines lists engines that abstained"
            )
        entry = self._entry(candidate)
        if entry is None:
            return cns.GateOutcome.TERMINAL_BREACH, "fault: the verdict has no entry in the engine's audit ledger"
        problem = _record_problem(entry, candidate)
        if problem:
            return cns.GateOutcome.TERMINAL_BREACH, "fault: " + problem
        if self._patient_id is not None and entry["patient_id"] != self._patient_id:
            return cns.GateOutcome.TERMINAL_BREACH, (
                f"fault: verdict is for patient {entry['patient_id']!r}, this gate judges {self._patient_id!r}")
        return self._judge_evidence(entry["data"])

    def _judge_evidence(self, data: Dict[str, Any]) -> tuple:
        """Re-run the recorded engines on the recorded reading; count those that did not abstain."""
        cns = self._cns
        selected = list(data["selected_engines"])
        recorded = {o["engine"]: o for o in data["outputs"]}
        reading = VitalsSnapshot(**copy.deepcopy(data["vitals"]))
        engines = _cassette_of(self._engine).engines()
        contributed, silent = [], []
        for name in selected:
            run = engines.get(name)
            if run is None:  # not re-runnable, so its evidence cannot be confirmed
                silent.append(name)
                continue
            out = run(reading)
            rec = recorded.get(name)
            if rec is None or (out.risk_score, out.confidence, list(out.triggered_rules)) != (
                    rec["risk"], rec["confidence"], list(rec["rules"])):
                return cns.GateOutcome.TERMINAL_BREACH, (
                    f"fault: the recorded output of {name} is not what it gives on the recorded reading")
            (silent if out.abstained else contributed).append(name)
        not_run = sorted(self._mandatory - set(selected))
        abstained = sorted(self._mandatory & set(silent))
        if not_run or abstained:
            parts = ([f"{', '.join(not_run)} not run"] if not_run else []) + (
                [f"{', '.join(abstained)} abstained or unconfirmed"] if abstained else [])
            return cns.GateOutcome.RETRY, "mandatory engine gave no evidence: " + "; ".join(parts)
        policy = self._mandatory | self._advisory
        counted = [n for n in contributed if n in policy] if policy else contributed
        if not counted:
            return cns.GateOutcome.RETRY, (
                "no engine produced evidence for this verdict (selected: " + ", ".join(selected)
                + "; abstained or unconfirmed: " + (", ".join(silent) or "none") + ")")
        return cns.GateOutcome.PASS, ""

    def _entry(self, candidate: Any) -> Optional[Dict[str, Any]]:
        """The engine's audit ledger entry for this verdict, or None."""
        if not candidate.audit_hash:
            return None
        for entry in reversed(self._engine.audit_ledger.entries):
            if entry.get("immutable_hash") == candidate.audit_hash:
                return entry
        return None

    def _subject(self, candidate: Any) -> str:
        if self._position == _ALPHA:
            return f"observe:alpha:{candidate.patient_id}"
        patient = None
        if self._engine is not None:
            try:
                entry = self._entry(candidate)
            except Exception:  # an unreadable ledger leaves the subject unnamed; _judge refuses it
                entry = None
            patient = entry.get("patient_id") if entry else None
        fingerprint = candidate.decision_fingerprint or "unfingerprinted"
        return f"observe:omega:{patient}:{fingerprint}" if patient else f"observe:omega:{fingerprint}"

    def _result(self, outcome: Any, reason: str, subject: str = "", digest: str = "") -> Any:
        return self._cns.GateResult(
            gate=self.name,
            position=self.position,
            outcome=outcome,
            reason=reason,
            subject=subject,
            subject_digest=digest,
        )
