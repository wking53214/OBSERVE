"""Optional CNS connector: OBSERVE as a CNS gate, usable at either end.

ALPHA guards the input. It judges the vitals before any scoring happens and
refuses readings that fail sensor-plausibility checks, so a faulty sensor
produces a request for a new reading rather than a score.

OMEGA guards the output. It judges the fused verdict before it leaves and
refuses any verdict that is only a partial assessment or that no engine
backed with evidence. A verdict with nothing behind it is abstention, not
normality.

OBSERVE never authorizes anything. These gates only decide whether an
observation or verdict is sound enough to pass along. Refusals that a fresh
reading can fix are RETRY. Anything else is TERMINAL_BREACH. An exception,
a bad candidate, or content that cannot be bound is a fault, and a fault is
never a pass.

CNS is imported only when a connector is built. Without it, building one
raises CnsNotInstalled with the install command and nothing else changes.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from types import ModuleType
from typing import Any, Dict, Union

from observe_consolidated import FusedVerdict, VitalsSnapshot, validate_vitals

__all__ = [
    "CnsNotInstalled",
    "ObserveCnsGate",
    "cns_available",
]

INSTALL_HINT = "pip install 'cns @ git+https://github.com/wking53214/cns.git@v1.4.0'"

_ALPHA = "alpha"
_OMEGA = "omega"


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


def _plain(value: Any) -> Any:
    """Reduce a value to the plain types a digest accepts."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


class ObserveCnsGate:
    """OBSERVE as a CNS gate. ALPHA takes vitals, OMEGA takes a fused verdict."""

    def __init__(self, position: str = _ALPHA) -> None:
        cns = _cns_gate()
        if position not in (_ALPHA, _OMEGA):
            raise ValueError(f"position must be 'alpha' or 'omega', not {position!r}")
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
            digest = cns.subject_digest(_plain(asdict(candidate)))
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
            faults = validate_vitals(candidate)
            if faults:
                return cns.GateOutcome.RETRY, "sensor fault, re-read required: " + "; ".join(faults)
            return cns.GateOutcome.PASS, ""
        if candidate.unassessable:
            return cns.GateOutcome.RETRY, "partial assessment: " + "; ".join(candidate.validation_faults)
        if not candidate.active_engines:
            return cns.GateOutcome.RETRY, "no engine produced evidence for this verdict"
        return cns.GateOutcome.PASS, ""

    def _subject(self, candidate: Any) -> str:
        if self._position == _ALPHA:
            return f"observe:alpha:{candidate.patient_id}"
        return f"observe:omega:{candidate.decision_fingerprint or 'unfingerprinted'}"

    def _result(self, outcome: Any, reason: str, subject: str = "", digest: str = "") -> Any:
        return self._cns.GateResult(
            gate=self.name,
            position=self.position,
            outcome=outcome,
            reason=reason,
            subject=subject,
            subject_digest=digest,
        )
