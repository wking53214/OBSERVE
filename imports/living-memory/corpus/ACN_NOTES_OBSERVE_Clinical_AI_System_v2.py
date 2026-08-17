"""
===============================================================================
ACN NOTES
OBSERVE Clinical AI System — Consolidated v2
Architecture Context Notes
===============================================================================

SYSTEM FILE:
ACN_OBSERVE_Clinical_AI_System_v2.py

SYSTEM CLASS:
Production-oriented pediatric clinical risk assessment and governance engine.

PURPOSE:
OBSERVE transforms physiological observations into explainable, auditable,
and governed risk assessments through independent reasoning engines, evidence
fusion, operational policy controls, and immutable forensic logging.

ARCHITECTURAL INVARIANT:

    Observation
          |
          v
    Validation Boundary
          |
          v
    Independent Risk Engines
          |
          v
    Evidence Fusion
          |
          v
    Operational Policy
          |
          v
    Audit + Traceability


===============================================================================
DESIGN PRINCIPLES
===============================================================================

1. MULTI-ENGINE REASONING

Risk assessment is generated from independent analytical perspectives:

- Heuristic physiological rules
- Bayesian inference
- Temporal trajectory analysis
- Drift detection
- Behavioral syndrome detection
- Adversarial telemetry analysis
- Physiological reserve modeling

The architecture avoids single-model dependency and preserves reasoning
diversity.


===============================================================================
2. SAFETY-FIRST INPUT VALIDATION
===============================================================================

Telemetry integrity is evaluated before clinical interpretation.

The system separates:

    Clinical abnormality

from:

    Data integrity failure

Invalid data is never interpreted as a healthy patient state.


===============================================================================
3. EXPLAINABLE DECISIONS
===============================================================================

Every inference engine produces:

- risk score
- confidence
- regime probabilities
- triggered evidence
- diagnostic metadata

Every final decision must remain explainable.


===============================================================================
4. ABSTENTION SUPPORT
===============================================================================

An engine lacking sufficient evidence may abstain.

The system distinguishes:

"No detected risk"

from:

"Unable to evaluate risk."


===============================================================================
5. GOVERNED FUSION
===============================================================================

Fusion combines independent evidence while preserving:

- uncertainty
- high-risk syndrome floors
- confidence weighting
- safety escalation rules


===============================================================================
6. OPERATIONAL SAFETY
===============================================================================

The policy layer provides:

- hysteresis
- dwell control
- escalation locking
- emergency bypass behavior


===============================================================================
7. FORENSIC ACCOUNTABILITY
===============================================================================

OBSERVE maintains:

Decision Fingerprint:
- deterministic replay
- identical inputs produce identical signatures

Audit Hash:
- immutable chained history
- tamper evidence


===============================================================================
8. DEPLOYMENT BOUNDARY
===============================================================================

OBSERVE is a clinical decision-support architecture.

It assists qualified healthcare professionals.

It does not autonomously diagnose, prescribe treatment, or replace clinical
authority.

===============================================================================
END ACN NOTES
===============================================================================
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import threading
import copy

from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4


logger = logging.getLogger("OBSERVE")


# =============================================================================
# ENUMS & DATA CONTRACTS
# =============================================================================


class OperationalRegime(Enum):
    STABLE = "stable"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class VitalsSnapshot:
    patient_id: str
    timestamp: datetime
    heart_rate: float
    oxygen_saturation: float
    respiratory_rate: float
    temperature: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskOutput:
    engine_name: str
    risk_score: float
    confidence: float
    regime_classification: Dict[str, float]
    triggered_rules: List[str]
    timestamp: datetime
    debug_info: Dict[str, Any] = field(default_factory=dict)
    abstained: bool = False


@dataclass
class FusedVerdict:
    risk_score: float
    regime: OperationalRegime
    confidence: float
    entropy: float
    active_engines: List[str]
    triggered_rules: List[str]
    timestamp: datetime
    audit_hash: str = ""
    decision_fingerprint: str = ""
    escalation_required: bool = False


@dataclass
class ScheduledJob:
    patient_id: str
    vitals_snapshot: Dict[str, Any]
    job_id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: JobStatus = JobStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    final_result: Optional[Dict[str, Any]] = None


# =============================================================================
# PEDIATRIC CLINICAL POLICY
# =============================================================================


PEDIATRIC_NORMS = {
    "neonatal": {
        "hr_high": 160,
        "hr_low": 80,
        "rr_high": 50,
        "o2_low": 90,
        "temp_high": 38.5,
    },
    "infant": {
        "hr_high": 150,
        "hr_low": 90,
        "rr_high": 45,
        "o2_low": 90,
        "temp_high": 39.0,
    },
    "toddler": {
        "hr_high": 140,
        "hr_low": 95,
        "rr_high": 40,
        "o2_low": 91,
        "temp_high": 39.0,
    },
    "child": {
        "hr_high": 130,
        "hr_low": 100,
        "rr_high": 35,
        "o2_low": 92,
        "temp_high": 39.5,
    },
    "generic": {
        "hr_high": 140,
        "hr_low": 95,
        "rr_high": 40,
        "o2_low": 91,
        "temp_high": 39.0,
    },
}


DRIFT_SIGMA_THRESHOLD = 2.0


# =============================================================================
# INPUT VALIDATION
# =============================================================================


VITALS_PHYSICAL_BOUNDS = {
    "heart_rate": (0.0, 350.0),
    "oxygen_saturation": (0.0, 100.0),
    "respiratory_rate": (0.0, 150.0),
    "temperature": (20.0, 45.0),
}


def validate_vitals(vitals: VitalsSnapshot) -> List[str]:
    faults = []

    for name, (low, high) in VITALS_PHYSICAL_BOUNDS.items():
        value = getattr(vitals, name, None)

        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            faults.append(f"{name}={value!r} invalid")

        elif not low <= value <= high:
            faults.append(
                f"{name}={value} outside [{low}, {high}]"
            )

    return faults


def decision_fingerprint(data: Dict[str, Any]) -> str:
    payload = json.dumps(
        data,
        sort_keys=True,
        default=str
    )

    return hashlib.sha256(
        payload.encode()
    ).hexdigest()


def get_age_group(age_months: Optional[int]) -> str:

    if age_months is None:
        return "generic"

    if age_months < 3:
        return "neonatal"

    if age_months < 12:
        return "infant"

    if age_months < 36:
        return "toddler"

    return "child"


def regime_distribution(
    risk_score: float,
    critical_floor: float = 0.01
) -> Dict[str, float]:

    if risk_score >= 0.75:
        result = {
            "stable": 0.05,
            "caution": 0.10,
            "warning": 0.25,
            "critical": 0.60,
        }

    elif risk_score >= 0.50:
        result = {
            "stable": 0.10,
            "caution": 0.20,
            "warning": 0.55,
            "critical": 0.15,
        }

    elif risk_score >= 0.25:
        result = {
            "stable": 0.35,
            "caution": 0.50,
            "warning": 0.12,
            "critical": 0.03,
        }

    else:
        result = {
            "stable": 0.88,
            "caution": 0.08,
            "warning": 0.03,
            "critical": 0.01,
        }

    if result["critical"] < critical_floor:
        difference = critical_floor - result["critical"]
        result["critical"] = critical_floor
        result["stable"] = max(
            0.0,
            result["stable"] - difference
        )

    return result

    # =============================================================================
# RISK ASSESSMENT ADAPTERS
# =============================================================================


class RiskAdapters:
    """
    Core clinical reasoning engines.
    Each adapter evaluates a different dimension of patient state.
    """

    @staticmethod
    def heuristic(vitals: VitalsSnapshot) -> RiskOutput:

        triggered = []
        score = 0.0

        age_months = vitals.context.get("age_months")
        age_group = get_age_group(age_months)

        thresholds = PEDIATRIC_NORMS[age_group]

        history_available = (
            "previous_o2" in vitals.context
            and "previous_hr" in vitals.context
        )

        if vitals.oxygen_saturation < 88:
            triggered.append(
                f"CRITICAL_O2: {vitals.oxygen_saturation}%"
            )
            score += 0.5

        elif vitals.oxygen_saturation < thresholds["o2_low"]:
            triggered.append(
                f"WARNING_O2: {vitals.oxygen_saturation}%"
            )
            score += 0.2


        if vitals.heart_rate > thresholds["hr_high"]:
            triggered.append(
                "TACHYCARDIA"
            )
            score += 0.2

        elif vitals.heart_rate < thresholds["hr_low"]:
            triggered.append(
                "BRADYCARDIA"
            )
            score += 0.3


        if vitals.respiratory_rate > thresholds["rr_high"]:
            triggered.append(
                "TACHYPNEA"
            )
            score += 0.15


        if vitals.temperature > thresholds["temp_high"]:
            triggered.append(
                "FEVER"
            )
            score += 0.1


        elif vitals.temperature < 35:
            triggered.append(
                "HYPOTHERMIA"
            )
            score += 0.4


        score = min(score, 1.0)


        confidence = (
            0.95
            if history_available and age_months is not None
            else 0.85
            if age_months is not None
            else 0.70
        )


        return RiskOutput(
            "heuristic",
            score,
            confidence,
            regime_distribution(score),
            triggered,
            datetime.now(timezone.utc),
        )


    @staticmethod
    def bayesian(vitals: VitalsSnapshot) -> RiskOutput:

        triggered = []
        debug = {}

        age_group = get_age_group(
            vitals.context.get("age_months")
        )

        thresholds = PEDIATRIC_NORMS[age_group]


        o2_mean = (
            thresholds["o2_low"] + 100
        ) / 2

        o2_std = 3.0


        hr_mean = (
            thresholds["hr_high"]
            +
            thresholds["hr_low"]
        ) / 2

        hr_std = (
            thresholds["hr_high"]
            -
            thresholds["hr_low"]
        ) / 4


        z_o2 = (
            vitals.oxygen_saturation - o2_mean
        ) / o2_std


        z_hr = (
            vitals.heart_rate - hr_mean
        ) / hr_std


        debug["z_o2"] = round(z_o2, 3)
        debug["z_hr"] = round(z_hr, 3)


        score = 0.0


        if z_o2 < -2:

            likelihood = (
                1 -
                math.exp(
                    -0.15 *
                    (abs(z_o2) ** 2)
                )
            )

            triggered.append(
                f"O2_DEVIATION {z_o2:.2f} SD"
            )

            score += (
                0.4 *
                likelihood
            )


        if abs(z_hr) > 2:

            likelihood = (
                1 -
                math.exp(
                    -0.10 *
                    (z_hr ** 2)
                )
            )

            triggered.append(
                f"HR_DEVIATION {z_hr:.2f} SD"
            )

            score += (
                0.3 *
                likelihood
            )


        score = min(score, 1.0)


        result = RiskOutput(
            "bayesian",
            score,
            0.85,
            regime_distribution(score),
            triggered,
            datetime.now(timezone.utc),
        )

        result.debug_info = debug

        return result


    @staticmethod
    def trajectory(vitals: VitalsSnapshot) -> RiskOutput:

        previous_o2 = vitals.context.get(
            "previous_o2"
        )

        previous_hr = vitals.context.get(
            "previous_hr"
        )

        previous_rr = vitals.context.get(
            "previous_rr"
        )

        previous_temp = vitals.context.get(
            "previous_temp"
        )

        delta_seconds = vitals.context.get(
            "time_delta_seconds",
            60
        )


        if (
            delta_seconds <= 0
            or
            (
                previous_o2 is None
                and previous_hr is None
                and previous_rr is None
            )
        ):

            return RiskOutput(
                "trajectory",
                0.0,
                0.2,
                {
                    "stable":1.0,
                    "caution":0.0,
                    "warning":0.0,
                    "critical":0.0
                },
                [
                    "Insufficient history"
                ],
                datetime.now(timezone.utc),
                abstained=True
            )


        dt_minutes = (
            delta_seconds / 60
        )


        score = 0.0
        triggered = []


        o2_momentum = None
        hr_momentum = None
        rr_momentum = None


        if previous_o2 is not None:

            o2_momentum = (
                vitals.oxygen_saturation
                -
                previous_o2
            ) / dt_minutes


            if o2_momentum < -3:

                triggered.append(
                    "O2_MOMENTUM"
                )

                score += 0.4



        if previous_hr is not None:

            hr_momentum = (
                vitals.heart_rate
                -
                previous_hr
            ) / dt_minutes


            if hr_momentum > 20:

                triggered.append(
                    "HR_MOMENTUM"
                )

                score += 0.3



        if previous_rr is not None:

            rr_momentum = (
                vitals.respiratory_rate
                -
                previous_rr
            ) / dt_minutes


            if rr_momentum > 5:

                triggered.append(
                    "RR_MOMENTUM"
                )

                score += 0.25



        worsening = sum(
            [
                o2_momentum is not None
                and o2_momentum < -3,

                hr_momentum is not None
                and hr_momentum > 20,

                rr_momentum is not None
                and rr_momentum > 5,
            ]
        )


        if worsening >= 2:

            triggered.append(
                "MULTI_TREND_DETERIORATION"
            )

            score += 0.2


        score = min(score,1.0)


        history_quality = sum(
            x is not None
            for x in [
                previous_o2,
                previous_hr,
                previous_rr,
                previous_temp
            ]
        ) / 4


        confidence = (
            0.6
            +
            0.3 *
            history_quality
        )


        return RiskOutput(
            "trajectory",
            score,
            confidence,
            regime_distribution(score),
            triggered,
            datetime.now(timezone.utc),
        )


    @staticmethod
    def drift(vitals: VitalsSnapshot) -> RiskOutput:

        baseline_o2 = vitals.context.get(
            "baseline_o2"
        )

        baseline_hr = vitals.context.get(
            "baseline_hr"
        )

        history_o2 = vitals.context.get(
            "history_o2",
            []
        )

        history_hr = vitals.context.get(
            "history_hr",
            []
        )


        if (
            not any(
                x is not None
                for x in [
                    baseline_o2,
                    baseline_hr
                ]
            )
            or
            (
                len(history_o2) < 5
                and
                len(history_hr) < 5
            )
        ):

            return RiskOutput(
                "drift",
                0.0,
                0.3,
                {
                    "stable":1.0,
                    "caution":0,
                    "warning":0,
                    "critical":0
                },
                [
                    "Insufficient drift history"
                ],
                datetime.now(timezone.utc),
                abstained=True
            )


        score = 0.0
        triggered = []


        if baseline_o2 is not None and len(history_o2) >= 5:

            mean = sum(history_o2) / len(history_o2)

            variance = sum(
                (x-mean)**2
                for x in history_o2
            ) / len(history_o2)

            std = math.sqrt(
                variance
            )

            z = (
                abs(baseline_o2 - mean)
                /
                std
                if std > 0
                else 0
            )


            if z > DRIFT_SIGMA_THRESHOLD:

                triggered.append(
                    "O2_DRIFT"
                )

                score += 0.3


        if baseline_hr is not None and len(history_hr) >= 5:

            mean = sum(history_hr) / len(history_hr)

            variance = sum(
                (x-mean)**2
                for x in history_hr
            ) / len(history_hr)

            std = math.sqrt(
                variance
            )


            z = (
                abs(baseline_hr - mean)
                /
                std
                if std > 0
                else 0
            )


            if z > DRIFT_SIGMA_THRESHOLD:

                triggered.append(
                    "HR_DRIFT"
                )

                score += 0.25


        score = min(score,1.0)


        return RiskOutput(
            "drift",
            score,
            0.85,
            regime_distribution(
                score,
                critical_floor=0.02
            ),
            triggered,
            datetime.now(timezone.utc),
        )

            @staticmethod
    def behavioral_vaccine(vitals: VitalsSnapshot) -> RiskOutput:
        """
        Behavioral safety adapter.

        Detects dangerous multi-variable clinical patterns while avoiding
        false reductions from unknown context.
        """

        triggered = []
        score = 0.0

        # Independent base risk calculation
        if vitals.oxygen_saturation < 90.0:
            score += 0.4
            triggered.append(
                f"LOW_O2: {vitals.oxygen_saturation}%"
            )

        elif vitals.oxygen_saturation < 92.0:
            score += 0.2
            triggered.append(
                f"BORDERLINE_O2: {vitals.oxygen_saturation}%"
            )

        if vitals.heart_rate > 150:
            score += 0.3
            triggered.append(
                f"TACHYCARDIA: {vitals.heart_rate}"
            )

        elif vitals.heart_rate < 80:
            score += 0.3
            triggered.append(
                f"BRADYCARDIA: {vitals.heart_rate}"
            )

        initial_risk = min(score, 1.0)

        dangerous_patterns = []

        # Septic shock pattern
        if (
            vitals.oxygen_saturation < 92.0
            and vitals.heart_rate > 140
            and vitals.respiratory_rate > 35
            and vitals.temperature > 38.5
        ):
            dangerous_patterns.append("SEPTIC_SHOCK")
            triggered.append(
                "DANGEROUS_PATTERN: septic_shock"
            )
            score += 0.40

        # Respiratory distress pattern
        if (
            vitals.oxygen_saturation < 90.0
            and vitals.respiratory_rate > 45
        ):
            dangerous_patterns.append("RESPIRATORY_DISTRESS")
            triggered.append(
                "DANGEROUS_PATTERN: respiratory_distress"
            )
            score += 0.35

        # Shock pattern
        if (
            vitals.heart_rate > 150
            and vitals.oxygen_saturation < 88.0
        ):
            dangerous_patterns.append("HYPOVOLEMIC_SHOCK")
            triggered.append(
                "DANGEROUS_PATTERN: hypovolemic_shock"
            )
            score += 0.35


        alert_status = vitals.context.get("alert")


        # Only apply benign reductions if dangerous patterns are absent
        if not dangerous_patterns:

            if alert_status is not None:

                if (
                    vitals.temperature > 38.5
                    and vitals.heart_rate > 130
                    and vitals.respiratory_rate > 28
                ):
                    triggered.append(
                        "BENIGN_PATTERN: fever_response"
                    )
                    score = max(
                        score - 0.15,
                        initial_risk * 0.5
                    )

                if (
                    alert_status == "crying"
                    and vitals.heart_rate > 140
                ):
                    triggered.append(
                        "BENIGN_PATTERN: crying_baby"
                    )
                    score = max(
                        score - 0.10,
                        initial_risk * 0.5
                    )

        else:
            triggered.append(
                f"DANGEROUS_PATTERNS_ACTIVE: "
                f"{len(dangerous_patterns)} suppressed benign reductions"
            )


        score = max(
            0.0,
            min(score, 1.0)
        )


        confidence = (
            0.90
            if alert_status is not None
            else 0.75
        )


        return RiskOutput(
            "behavioral",
            score,
            confidence,
            regime_distribution(score),
            triggered,
            datetime.now(timezone.utc),
        )


    @staticmethod
    def adversarial(vitals: VitalsSnapshot) -> RiskOutput:
        """
        Sensor integrity and adversarial telemetry detection.

        Detects:
        - impossible values
        - frozen sensors
        - unrealistic rate changes
        - low variance telemetry
        """

        triggered = []
        score = 0.0


        recent_readings = vitals.context.get(
            "recent_o2_readings",
            []
        )


        # Frozen sensor detection
        if len(recent_readings) >= 5:

            last_five = recent_readings[-5:]

            if len(set(last_five)) == 1:

                triggered.append(
                    f"CONSTANT_VALUE_STREAK: "
                    f"{len(last_five)} identical readings"
                )

                score += 0.3


        # Low variance sensor detection
        if len(recent_readings) >= 10:

            window = recent_readings[-10:]

            mean = sum(window) / len(window)

            variance = sum(
                (x - mean) ** 2
                for x in window
            ) / len(window)


            if variance < 0.01 and len(set(window)) > 1:

                triggered.append(
                    f"LOW_VARIANCE_SENSOR: variance={variance:.4f}"
                )

                score += 0.15


        # Impossible oxygen saturation
        if (
            vitals.oxygen_saturation > 100.0
            or vitals.oxygen_saturation < 0.0
        ):

            triggered.append(
                f"OUT_OF_RANGE_O2: {vitals.oxygen_saturation}"
            )

            score += 0.3


        # Unrealistic rate-of-change detection
        previous_o2 = vitals.context.get(
            "previous_o2"
        )

        time_delta = vitals.context.get(
            "time_delta_seconds",
            60
        )


        if previous_o2 is not None and time_delta > 0:

            pct_change = (
                abs(
                    vitals.oxygen_saturation - previous_o2
                )
                /
                (time_delta / 60.0)
            )


            if pct_change > 15.0:

                triggered.append(
                    f"IMPLAUSIBLE_RATE: "
                    f"{pct_change:.1f}%/min"
                )

                score += 0.25


        score = min(
            score,
            1.0
        )


        if score < 0.01:

            regimes = {
                "stable": 1.0,
                "caution": 0.0,
                "warning": 0.0,
                "critical": 0.0,
            }

        else:

            regimes = regime_distribution(score)


        return RiskOutput(
            "adversarial",
            score,
            0.70,
            regimes,
            triggered,
            datetime.now(timezone.utc),
        )

# =============================================================================
# PHYSIOLOGICAL TELEMETRY DETECTION
# GATING FOR ADVANCED ADAPTER
# =============================================================================


_PHYSIO_AXIS_KEYS = {

    "topology": [
        "organ_coupling_index",
        "organ_failures",
    ],

    "capacity": [
        "perfusion_index",
        "metabolic_load_index",
        "oxygen_demand_index",
    ],

    "resource": [
        "reserve_index",
        "substrate_level",
        "tissue_viability",
        "energy_ratio",
    ],

    "integrity": [
        "integrity_events",
        "critical_integrity_events",
        "infection_burden_index",
    ],

    "phase": [
        "phase",
        "compensation_index",
        "decomp_index",
    ],
}


def _has_physiological_telemetry(
    vitals: VitalsSnapshot
) -> bool:

    """
    Determines whether advanced physiological telemetry exists.

    Missing telemetry does not equal healthy.
    Missing telemetry means the adapter cannot assess.
    """

    context = vitals.context

    for axis_keys in _PHYSIO_AXIS_KEYS.values():

        if any(
            key in context
            for key in axis_keys
        ):
            return True

    return False



class RiskAdaptersPhysiological:

    """
    Advanced physiological reserve adapter.

    Evaluates deeper systems physiology:

    - topology
    - capacity
    - resource depletion
    - integrity failure
    - phase transition
    - instability

    Safety properties:

    1. Missing telemetry causes abstention.
    2. Missing axes never imply normal.
    3. Scores use shared regime calibration.
    """


    @staticmethod
    def _topology_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        if not any(
            k in ctx
            for k in _PHYSIO_AXIS_KEYS["topology"]
        ):
            return None


        coupling = ctx.get(
            "organ_coupling_index",
            1.0
        )

        failures = ctx.get(
            "organ_failures",
            0
        )

        total = ctx.get(
            "total_organs",
            6
        )


        coupling_risk = max(
            0.0,
            min(
                1.0,
                1.0 - coupling
            )
        )


        failure_risk = max(
            0.0,
            min(
                1.0,
                failures / max(total, 1)
            )
        )


        return max(
            0.0,
            min(
                1.0,
                (
                    0.6 * coupling_risk
                    +
                    0.4 * failure_risk
                )
            )
        )


    @staticmethod
    def _capacity_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        if not any(
            k in ctx
            for k in _PHYSIO_AXIS_KEYS["capacity"]
        ):
            return None


        perfusion = ctx.get(
            "perfusion_index",
            1.0
        )

        metabolic_load = ctx.get(
            "metabolic_load_index",
            1.0
        )

        oxygen_demand = ctx.get(
            "oxygen_demand_index",
            1.0
        )


        reserve_risk = (

            1.0
            if metabolic_load <= 0
            else
            max(
                0.0,
                min(
                    1.0,
                    1.0 -
                    (
                        perfusion /
                        metabolic_load
                    )
                )
            )
        )


        imbalance_risk = (

            1.0
            if oxygen_demand <= 0
            else
            max(
                0.0,
                min(
                    1.0,
                    abs(
                        perfusion -
                        oxygen_demand
                    )
                    /
                    oxygen_demand
                )
            )
        )


        return max(
            0.0,
            min(
                1.0,
                (
                    0.6 * reserve_risk
                    +
                    0.4 * imbalance_risk
                )
            )
        )


    @staticmethod
    def _resource_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        if not any(
            k in ctx
            for k in _PHYSIO_AXIS_KEYS["resource"]
        ):
            return None


        reserve = ctx.get(
            "reserve_index",
            1.0
        )

        substrate = ctx.get(
            "substrate_level",
            1.0
        )

        viability = ctx.get(
            "tissue_viability",
            1.0
        )

        energy = ctx.get(
            "energy_ratio",
            1.0
        )


        reserve_risk = max(
            0.0,
            min(
                1.0,
                1.0 - reserve
            )
        )


        biological_risk = max(
            0.0,
            min(
                1.0,
                (
                    0.4 * (1 - substrate)
                    +
                    0.3 * (1 - viability)
                    +
                    0.3 * (1 - energy)
                )
            )
        )


        return max(
            0.0,
            min(
                1.0,
                (
                    0.5 * reserve_risk
                    +
                    0.5 * biological_risk
                )
            )
        )


    @staticmethod
    def _integrity_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        if not any(
            k in ctx
            for k in _PHYSIO_AXIS_KEYS["integrity"]
        ):
            return None


        events = ctx.get(
            "integrity_events",
            0.0
        )

        critical = ctx.get(
            "critical_integrity_events",
            0.0
        )

        infection = ctx.get(
            "infection_burden_index",
            0.0
        )


        event_risk = max(
            0.0,
            min(
                1.0,
                (
                    0.10 * events
                    +
                    0.30 * critical
                )
            )
        )


        return max(
            0.0,
            min(
                1.0,
                (
                    0.6 * event_risk
                    +
                    0.4 *
                    max(
                        0.0,
                        min(
                            1.0,
                            infection
                        )
                    )
                )
            )
        )


    @staticmethod
    def _phase_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        if not any(
            k in ctx
            for k in _PHYSIO_AXIS_KEYS["phase"]
        ):
            return None


        phase = ctx.get(
            "phase",
            "stable"
        )


        base = {

            "stable": 0.1,

            "compensation": 0.3,

            "decompensation": 0.6,

            "collapse": 0.9,

        }.get(
            phase,
            0.3
        )


        compensation = max(
            0.0,
            min(
                1.0,
                ctx.get(
                    "compensation_index",
                    0.0
                )
            )
        )


        decompensation = max(
            0.0,
            min(
                1.0,
                ctx.get(
                    "decomp_index",
                    0.0
                )
            )
        )


        return max(
            0.0,
            min(
                1.0,
                (
                    base
                    +
                    0.3 * decompensation
                    -
                    0.2 * compensation
                )
            )
        )
    @staticmethod
    def _instability_risk(
        ctx: Dict[str, Any]
    ) -> Optional[float]:

        """
        Measures short-term physiological instability.

        Uses HR variability because this is available from standard
        telemetry streams. Other axes require advanced instrumentation.
        """

        history = ctx.get(
            "hr_history",
            []
        )


        if len(history) < 3:
            return None


        differences = [

            abs(
                history[i]
                -
                history[i - 1]
            )

            for i in range(
                1,
                len(history)
            )
        ]


        mean_difference = (
            sum(differences)
            /
            len(differences)
        )


        return max(
            0.0,
            min(
                1.0,
                mean_difference / 30.0
            )
        )


    @staticmethod
    def physiological_reserve(
        vitals: "VitalsSnapshot"
    ) -> "RiskOutput":

        """
        Advanced physiological reserve evaluation.

        Computes only from available telemetry axes.

        Absent telemetry:
            - adapter abstains
            - does not emit stable
            - does not dilute other engines
        """

        ctx = vitals.context

        triggered = []

        debug_info = {}


        axes = {

            "topology":
                RiskAdaptersPhysiological._topology_risk(ctx),

            "capacity":
                RiskAdaptersPhysiological._capacity_risk(ctx),

            "resource":
                RiskAdaptersPhysiological._resource_risk(ctx),

            "integrity":
                RiskAdaptersPhysiological._integrity_risk(ctx),

            "phase":
                RiskAdaptersPhysiological._phase_risk(ctx),

            "instability":
                RiskAdaptersPhysiological._instability_risk(ctx),

        }


        present_axes = {

            key: value

            for key, value in axes.items()

            if value is not None

        }


        debug_info["axes_present"] = list(
            present_axes.keys()
        )


        debug_info["axes_values"] = {

            key:
            round(value, 3)

            for key, value in present_axes.items()

        }


        # No telemetry available
        if not present_axes:

            return RiskOutput(

                "physiological_reserve",

                0.0,

                0.2,

                {
                    "stable": 1.0,
                    "caution": 0.0,
                    "warning": 0.0,
                    "critical": 0.0,
                },

                [
                    "No rich physiological telemetry available; adapter abstains"
                ],

                datetime.now(timezone.utc),

                debug_info,

                abstained=True,

            )


        risk_score = (

            sum(
                present_axes.values()
            )
            /
            len(present_axes)

        )


        risk_score = max(
            0.0,
            min(
                1.0,
                risk_score
            )
        )


        for axis, value in present_axes.items():

            if value >= 0.5:

                triggered.append(

                    f"PHYSIO_{axis.upper()}: "
                    f"risk={value:.2f}"

                )


        confidence = (

            0.45
            +
            (
                0.50
                *
                (
                    len(present_axes)
                    /
                    6.0
                )
            )

        )


        return RiskOutput(

            "physiological_reserve",

            risk_score,

            confidence,

            regime_distribution(
                risk_score
            ),

            triggered
            if triggered
            else
            [
                (
                    "Physiological reserve assessed "
                    f"across {len(present_axes)} axes"
                )
            ],

            datetime.now(timezone.utc),

            debug_info,

        )


# =============================================================================
# BAYESIAN FUSION
# ENTROPY-BASED ENGINE SELECTION FEEDBACK
# =============================================================================


class BayesianFusion:

    """
    Confidence-weighted fusion of multiple risk engines.

    Principles:

    - Abstaining engines do not vote.
    - Confidence weights influence contribution.
    - Dangerous clinical syndromes receive safety floors.
    """


    @staticmethod
    def fuse(
        outputs: List[RiskOutput]
    ) -> Tuple[
        float,
        float,
        Dict[str, float],
        str
    ]:


        if not outputs:

            return (

                0.0,

                0.0,

                {
                    "stable": 1.0,
                    "caution": 0.0,
                    "warning": 0.0,
                    "critical": 0.0,
                },

                "No outputs"

            )


        # Remove abstaining engines
        active = [

            output

            for output in outputs

            if not output.abstained

        ]


        fusion_set = (
            active
            if active
            else outputs
        )


        abstained = [

            output.engine_name

            for output in outputs

            if output.abstained

        ]


        total_confidence = sum(

            output.confidence

            for output in fusion_set

        )


        fused_risk = (

            sum(

                output.risk_score
                *
                output.confidence

                for output in fusion_set

            )
            /
            total_confidence

            if total_confidence > 0

            else 0.0

        )


        regime_probs = {

            "stable": 0.0,

            "caution": 0.0,

            "warning": 0.0,

            "critical": 0.0,

        }


        for output in fusion_set:

            for regime, probability in output.regime_classification.items():

                regime_probs[regime] += (

                    probability
                    *
                    output.confidence

                )


        if total_confidence > 0:

            regime_probs = {

                key:
                value / total_confidence

                for key, value in regime_probs.items()

            }


        entropy = (

            -sum(

                probability
                *
                math.log2(probability)

                for probability in regime_probs.values()

                if probability > 0

            )

        )


        # Clinical syndrome floor
        syndrome_floor = 0.0


        for output in fusion_set:

            if any(

                "DANGEROUS_PATTERN:" in rule

                for rule in output.triggered_rules

            ):

                syndrome_floor = max(

                    syndrome_floor,

                    output.risk_score

                )


        rationale_floor = ""


        if syndrome_floor > fused_risk:

            rationale_floor = (

                f"; syndrome floor raised "
                f"risk {fused_risk:.2f}"
                f"->{syndrome_floor:.2f}"

            )


            fused_risk = syndrome_floor


            regime_probs = regime_distribution(
                fused_risk
            )


            entropy = -sum(

                probability
                *
                math.log2(probability)

                for probability in regime_probs.values()

                if probability > 0

            )


        engines = ", ".join(

            output.engine_name

            for output in fusion_set

        )


        rationale = (

            f"Fused {len(fusion_set)} active engines "
            f"({engines})"

        )


        if abstained:

            rationale += (

                f"; {len(abstained)} abstained "
                f"({', '.join(abstained)})"

            )


        rationale += rationale_floor


        return (

            fused_risk,

            entropy,

            regime_probs,

            rationale,

        )
# =============================================================================
# ESCALATION POLICY
# HYSTERESIS + DWELL
# =============================================================================


class EscalationPolicy:

    """
    Prevents operational regime thrashing.

    Uses:
    - dwell confirmation
    - escalation locking
    - cooldown windows
    """


    def __init__(
        self,
        dwell_threshold: int = 2,
        lock_seconds: int = 300
    ):

        self.dwell_threshold = dwell_threshold

        self.lock_seconds = lock_seconds

        self.current_regime = (
            OperationalRegime.STABLE
        )

        self.pending_regime = None

        self.dwell_count = 0

        self.escalation_locked = False

        self.last_escalation_time = None



    def evaluate(
        self,
        new_regime: OperationalRegime,
        timestamp: datetime
    ) -> Tuple[
        OperationalRegime,
        bool
    ]:


        # Active escalation cooldown
        if (
            self.escalation_locked
            and self.last_escalation_time
        ):

            elapsed = (

                timestamp
                -
                self.last_escalation_time

            ).total_seconds()


            if elapsed < self.lock_seconds:

                return (

                    self.current_regime,

                    False

                )


            self.escalation_locked = False



        # No regime change
        if new_regime == self.current_regime:

            self.pending_regime = None

            self.dwell_count = 0

            return (

                self.current_regime,

                False

            )


        # Accumulate confirmation dwell
        if new_regime == self.pending_regime:

            self.dwell_count += 1

        else:

            self.pending_regime = new_regime

            self.dwell_count = 1



        # Confirm transition
        if self.dwell_count >= self.dwell_threshold:


            escalation = (

                new_regime.value
                in
                (
                    "warning",
                    "critical"
                )

                and

                self.current_regime.value
                in
                (
                    "stable",
                    "caution"
                )

            )


            self.current_regime = new_regime

            self.pending_regime = None

            self.dwell_count = 0


            if escalation:

                self.escalation_locked = True

                self.last_escalation_time = timestamp


            return (

                new_regime,

                escalation

            )


        return (

            self.current_regime,

            False

        )



# =============================================================================
# IMMUTABLE AUDIT LEDGER
# SHA256 CRYPTOGRAPHIC CHAIN
# =============================================================================


class ImmutableAuditLedger:


    def __init__(self):

        self.entries = []

        self.chain_head = (
            "0" * 64
        )



    def append(
        self,
        patient_id: str,
        action: str,
        data: Dict[str, Any]
    ) -> str:


        entry = {

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "patient_id":
                patient_id,

            "action":
                action,

            "data":
                copy.deepcopy(data),

            "previous_hash":
                self.chain_head,

        }


        block_hash = hashlib.sha256(

            json.dumps(
                entry,
                sort_keys=True,
                default=str
            ).encode()

        ).hexdigest()



        entry["immutable_hash"] = block_hash


        self.entries.append(entry)


        self.chain_head = block_hash


        return block_hash



    def verify_integrity(self) -> bool:


        expected_previous = (
            "0" * 64
        )


        for entry in self.entries:


            if (
                entry["previous_hash"]
                !=
                expected_previous
            ):

                return False



            candidate = copy.deepcopy(entry)


            stored_hash = candidate.pop(
                "immutable_hash"
            )


            calculated_hash = hashlib.sha256(

                json.dumps(
                    candidate,
                    sort_keys=True,
                    default=str
                ).encode()

            ).hexdigest()



            if (
                calculated_hash
                !=
                stored_hash
            ):

                return False



            expected_previous = stored_hash



        return True



    def query_patient(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:


        return [

            entry

            for entry in self.entries

            if entry["patient_id"]
            ==
            patient_id

        ]



    def export_json(self) -> str:

        return json.dumps(

            self.entries,

            indent=2,

            default=str

        )



# =============================================================================
# ASYNC JOB QUEUE
# RETRY / REQUEUE / TTL SAFETY
# =============================================================================

class JobQueue:

    """
    Priority-based async queue.

    Guarantees:

    - retry requeue
    - bounded completed history
    - safe queue access
    - no unbounded memory growth
    """


    def __init__(
        self,
        max_completed_history: int = 1000
    ):

        self.queue = asyncio.PriorityQueue()

        self.jobs = {}

        self.completed_jobs = OrderedDict()

        self.max_completed_history = (
            max_completed_history
        )

        self._lock = asyncio.Lock()



    def _evict_old_completed(self):

        while (
            len(self.completed_jobs)
            >
            self.max_completed_history
        ):

            job_id, _ = (
                self.completed_jobs.popitem(
                    last=False
                )
            )

            self.jobs.pop(
                job_id,
                None
            )



    async def submit(
        self,
        patient_id: str,
        vitals: Dict[str, Any],
        priority: int = 2
    ) -> str:


        async with self._lock:


            job = ScheduledJob(

                patient_id=patient_id,

                vitals_snapshot=vitals

            )


            self.jobs[job.job_id] = job


            await self.queue.put(

                (
                    priority,

                    job.job_id

                )

            )


            return job.job_id



    async def mark_failed_and_requeue(
        self,
        job_id: str,
        priority: int = 1
    ):


        async with self._lock:


            job = self.jobs.get(
                job_id
            )


            if not job:

                logger.warning(
                    f"Unknown job {job_id}"
                )

                return



            if (
                job.retry_count
                <
                job.max_retries
            ):


                job.retry_count += 1

                job.status = (
                    JobStatus.QUEUED
                )


                await self.queue.put(

                    (
                        priority,

                        job_id

                    )

                )


            else:


                job.status = (
                    JobStatus.FAILED
                )


                self.completed_jobs[job_id] = job


                self._evict_old_completed()



    async def complete(
        self,
        job_id: str,
        result: Dict[str, Any]
    ):


        async with self._lock:


            job = self.jobs.get(
                job_id
            )


            if not job:

                logger.warning(
                    f"Unknown job {job_id}"
                )

                return



            job.status = (
                JobStatus.COMPLETED
            )


            job.final_result = result


            self.completed_jobs[job_id] = job


            self._evict_old_completed()



    def queue_size(self) -> int:

        return self.queue.qsize()



    def export_summary(self):

        return {

            "total_jobs":
                len(self.jobs),

            "completed":
                sum(

                    1

                    for job

                    in self.completed_jobs.values()

                    if job.status
                    ==
                    JobStatus.COMPLETED

                ),

            "failed":
                sum(

                    1

                    for job

                    in self.completed_jobs.values()

                    if job.status
                    ==
                    JobStatus.FAILED

                ),

            "queue_depth":
                self.queue_size(),

        }



# =============================================================================
# ASYNC JOB SCHEDULER
# =============================================================================


class AsyncJobScheduler:

    """
    Worker execution engine.

    Safety features:

    - CancelledError propagation
    - guaranteed task_done()
    - retry recovery
    - exception visibility
    """


    def __init__(
        self,
        num_workers: int = 2
    ):

        self.job_queue = JobQueue()

        self.num_workers = num_workers

        self.tasks = []

        self.is_running = False



    async def start(
        self,
        execution_router: Callable
    ):


        self.is_running = True


        for worker_id in range(
            self.num_workers
        ):

            self.tasks.append(

                asyncio.create_task(

                    self._worker_loop(

                        worker_id,

                        execution_router

                    )

                )

            )



    async def submit_job(
        self,
        patient_id: str,
        vitals: Dict[str, Any],
        priority: int = 2
    ) -> str:


        return await self.job_queue.submit(

            patient_id,

            vitals,

            priority

        )



    async def _worker_loop(
        self,
        worker_id: int,
        execution_router: Callable
    ):


        while self.is_running:


            try:

                priority, job_id = (

                    await self.job_queue.queue.get()

                )


            except asyncio.CancelledError:

                raise



            try:


                async with self.job_queue._lock:


                    job = self.job_queue.jobs.get(
                        job_id
                    )


                    if not job:

                        continue



                    job.status = (
                        JobStatus.RUNNING
                    )



                try:


                    result = await execution_router(

                        job.vitals_snapshot

                    )


                    if hasattr(
                        result,
                        "regime"
                    ):

                        result = asdict(
                            result
                        )


                    await self.job_queue.complete(

                        job_id,

                        result

                    )



                except asyncio.CancelledError:

                    raise



                except Exception as error:


                    logger.error(

                        f"Worker {worker_id} "
                        f"failed job {job_id}: {error}"

                    )


                    await self.job_queue.mark_failed_and_requeue(

                        job_id

                    )


            finally:


                self.job_queue.queue.task_done()



    async def stop(self):


        self.is_running = False


        for task in self.tasks:

            task.cancel()



        results = await asyncio.gather(

            *self.tasks,

            return_exceptions=True

        )


        for result in results:


            if (

                isinstance(
                    result,
                    Exception
                )

                and

                not isinstance(
                    result,
                    asyncio.CancelledError
                )

            ):

                logger.error(
                    f"Worker shutdown error: {result}"
                )



# =============================================================================
# PROVISIONAL STORE
# TTL CACHE + RECONCILIATION
# =============================================================================

# =============================================================================
# PROVISIONAL STORE
# TTL CACHE + RECONCILIATION
# =============================================================================


class ProvisionalStore:

    """
    Temporary verdict storage layer.

    Purpose:

    - hold provisional decisions
    - reconcile with final results
    - enforce TTL expiration
    - prevent mutation through exports
    """


    def __init__(
        self,
        ttl_seconds: int = 300,
        max_capacity: int = 5000
    ):

        self.provisionals = OrderedDict()

        self.ttl_seconds = ttl_seconds

        self.max_capacity = max_capacity



    def store(
        self,
        patient_id: str,
        job_id: str,
        risk_score: float,
        regime: str
    ):


        self._evict_expired()


        if len(self.provisionals) >= self.max_capacity:

            self.provisionals.popitem(
                last=False
            )


        self.provisionals[patient_id] = {

            "job_id":
                job_id,

            "risk_score":
                risk_score,

            "regime":
                regime,

            "is_provisional":
                True,

            "stored_at":
                datetime.now(
                    timezone.utc
                ),

        }



    def get(
        self,
        patient_id: str
    ) -> Optional[Dict[str, Any]]:


        self._evict_expired()


        return self.provisionals.get(
            patient_id
        )



    def reconcile(
        self,
        patient_id: str,
        job_id: str,
        final_result: Dict[str, Any]
    ) -> bool:


        self._evict_expired()


        entry = self.provisionals.get(
            patient_id
        )


        if entry is None:

            logger.warning(

                f"Reconcile failed: "
                f"unknown patient {patient_id}"

            )

            return False



        if entry.get(
            "job_id"
        ) != job_id:


            logger.warning(

                f"Reconcile mismatch: "
                f"{patient_id}"

            )

            return False



        entry["is_provisional"] = False

        entry["final_result"] = final_result

        entry["reconciled_at"] = (

            datetime.now(
                timezone.utc
            )

        )


        return True



    def export_all(self):

        return copy.deepcopy(

            dict(
                self.provisionals
            )

        )



    def _evict_expired(self):

        now = datetime.now(
            timezone.utc
        )


        expired = [

            key

            for key, value

            in self.provisionals.items()

            if (

                now -
                value["stored_at"]

            ).total_seconds()
            >
            self.ttl_seconds

        ]


        for key in expired:

            self.provisionals.pop(
                key,
                None
            )



# =============================================================================
# OBSERVE CLINICAL ENGINE
# MAIN ORCHESTRATOR
# =============================================================================


class ObserveClinicalEngine:

    """
    Pipeline:

        Validate
          ↓
        Select Engines
          ↓
        Execute Risk Models
          ↓
        Bayesian Fusion
          ↓
        Escalation Policy
          ↓
        Audit Ledger
    """


    ENGINE_MAP = {

        "heuristic":
            RiskAdapters.heuristic,

        "bayesian":
            RiskAdapters.bayesian,

        "trajectory":
            RiskAdapters.trajectory,

        "drift":
            RiskAdapters.drift,

        "behavioral":
            RiskAdapters.behavioral_vaccine,

        "adversarial":
            RiskAdapters.adversarial,

        "physiological_reserve":
            RiskAdaptersPhysiological.physiological_reserve,

    }



    def __init__(
        self,
        max_tracked_patients: int = 10000
    ):


        self.audit_ledger = (
            ImmutableAuditLedger()
        )


        self.scheduler = (
            AsyncJobScheduler(
                num_workers=2
            )
        )


        self.provisional_store = (
            ProvisionalStore()
        )


        self._max_tracked_patients = (
            max_tracked_patients
        )


        self._patient_policies = OrderedDict()

        self._patient_entropy = {}


        self._state_lock = (
            threading.Lock()
        )



    def _touch_patient(
        self,
        patient_id: str
    ):


        with self._state_lock:


            if patient_id in self._patient_policies:

                self._patient_policies.move_to_end(
                    patient_id
                )


            while (

                len(self._patient_policies)

                >

                self._max_tracked_patients

            ):

                evicted, _ = (

                    self._patient_policies.popitem(
                        last=False
                    )

                )


                self._patient_entropy.pop(
                    evicted,
                    None
                )



    def _get_policy(
        self,
        patient_id: str
    ) -> EscalationPolicy:


        with self._state_lock:


            if patient_id not in self._patient_policies:

                self._patient_policies[patient_id] = (

                    EscalationPolicy()

                )


        self._touch_patient(
            patient_id
        )


        return self._patient_policies[patient_id]

    def select_engines(
        self,
        vitals: VitalsSnapshot
    ) -> List[str]:

        """
        Deterministic engine selection.

        Starts lightweight.

        Adds deeper analysis based on:

        - entropy
        - forced heavy mode
        - historical context
        - telemetry availability
        - possible syndromes
        """


        engines = [

            "heuristic"

        ]


        recent_entropy = (

            self._patient_entropy.get(
                vitals.patient_id,
                0.0
            )

        )


        if (

            recent_entropy > 0.6

            or

            vitals.context.get(
                "force_heavy"
            )

        ):

            engines += [

                "bayesian",

                "trajectory",

                "drift",

            ]



        if (

            "previous_o2"
            in
            vitals.context

            or

            "previous_hr"
            in
            vitals.context

        ):

            if "trajectory" not in engines:

                engines.append(
                    "trajectory"
                )



        if vitals.context.get(
            "recent_o2_readings"
        ):

            engines.append(
                "adversarial"
            )



        # Behavioral engine must execute whenever
        # syndrome thresholds could potentially fire.

        if (

            vitals.oxygen_saturation < 92.0

            or

            vitals.heart_rate > 140

            or

            vitals.heart_rate < 90

            or

            vitals.respiratory_rate > 35

            or

            vitals.temperature > 38.5

        ):

            engines.append(
                "behavioral"
            )



        # Advanced physiology path

        if (

            recent_entropy > 0.6

            or

            vitals.context.get(
                "force_heavy"
            )

            or

            _has_physiological_telemetry(
                vitals
            )

        ):

            engines.append(
                "physiological_reserve"
            )



        # Remove duplicates while preserving order

        seen = set()

        ordered = []


        for engine in engines:

            if engine not in seen:

                seen.add(engine)

                ordered.append(
                    engine
                )


        return ordered



    def evaluate(
        self,
        vitals: VitalsSnapshot
    ) -> FusedVerdict:

        """
        Complete synchronous evaluation pipeline.

        validate
        select
        execute
        fuse
        classify
        escalate
        fingerprint
        audit
        """


        policy = self._get_policy(
            vitals.patient_id
        )


        # =========================================================
        # DATA INTEGRITY GATE
        # =========================================================


        faults = validate_vitals(
            vitals
        )


        if faults:

            return self._fault_verdict(
                vitals,
                policy,
                faults
            )



        # =========================================================
        # ENGINE EXECUTION
        # =========================================================


        selected = self.select_engines(
            vitals
        )


        outputs = [

            self.ENGINE_MAP[name](vitals)

            for name in selected

        ]



        # =========================================================
        # FUSION
        # =========================================================


        (
            fused_risk,

            entropy,

            regime_probs,

            rationale

        ) = BayesianFusion.fuse(
            outputs
        )



        with self._state_lock:

            self._patient_entropy[
                vitals.patient_id
            ] = entropy



        candidate_regime = (

            OperationalRegime(

                max(
                    regime_probs,
                    key=regime_probs.get
                )

            )

        )



        # =========================================================
        # SAFETY BYPASS CONDITIONS
        # =========================================================


        heuristic_output = next(

            (
                output

                for output in outputs

                if output.engine_name
                ==
                "heuristic"

            ),

            None

        )


        hard_rule_fired = (

            heuristic_output is not None

            and

            heuristic_output.risk_score >= 0.5

        )



        syndrome_fired = any(

            "DANGEROUS_PATTERN:" in rule

            for output in outputs

            for rule in output.triggered_rules

        )



        bypass = (

            hard_rule_fired

            or

            syndrome_fired

        )



        if (

            bypass

            and

            candidate_regime.value
            in
            (
                "warning",
                "critical"
            )

        ):


            escalation = (

                policy.current_regime.value
                in
                (
                    "stable",
                    "caution"
                )

            )


            final_regime = candidate_regime


            policy.current_regime = (
                final_regime
            )


            policy.pending_regime = None

            policy.dwell_count = 0



            if escalation:

                policy.escalation_locked = True

                policy.last_escalation_time = (

                    vitals.timestamp

                )


            bypass_reason = (

                "hard-rule"

                if hard_rule_fired

                else

                "dangerous-syndrome"

            )


            bypass_notes = [

                (
                    "CLINICAL_SAFETY_BYPASS: "
                    f"{bypass_reason} "
                    "trigger skipped dwell confirmation"
                )

            ]



        else:


            final_regime, escalation = (

                policy.evaluate(

                    candidate_regime,

                    vitals.timestamp

                )

            )


            bypass_notes = []



        triggered = (

            bypass_notes

            +

            [

                rule

                for output in outputs

                for rule in output.triggered_rules

            ]

        )


        confidence = (

            sum(
                output.confidence
                for output in outputs
            )
            /
            len(outputs)

            if outputs

            else

            0.0

        )

        # =========================================================
        # DETERMINISTIC DECISION FINGERPRINT
        # =========================================================

        decision_data = {

            "vitals":
                asdict(vitals),

            "selected_engines":
                selected,

            "outputs":
            [

                {

                    "engine":
                        output.engine_name,

                    "risk":
                        output.risk_score,

                    "confidence":
                        output.confidence,

                    "rules":
                        output.triggered_rules,

                }

                for output in outputs

            ],


            "verdict":
            {

                "risk_score":
                    fused_risk,

                "regime":
                    final_regime.value,

                "escalation_required":
                    escalation,

                "entropy":
                    entropy,

            }

        }


        fingerprint = decision_fingerprint(
            decision_data
        )



        # =========================================================
        # BUILD FINAL VERDICT
        # =========================================================


        verdict = FusedVerdict(

            risk_score =
                fused_risk,

            regime =
                final_regime,

            confidence =
                confidence,

            entropy =
                entropy,

            active_engines =
                selected,

            triggered_rules =
                triggered,

            timestamp =
                datetime.now(
                    timezone.utc
                ),

            escalation_required =
                escalation,

            decision_fingerprint =
                fingerprint,

        )



        # =========================================================
        # IMMUTABLE AUDIT ENTRY
        # =========================================================


        audit_hash = self.audit_ledger.append(

            vitals.patient_id,

            "clinical_assessment",

            {

                **decision_data,

                "decision_fingerprint":
                    fingerprint,

            }

        )


        verdict.audit_hash = audit_hash



        if escalation:

            logger.info(

                "ESCALATION: "

                f"patient={vitals.patient_id} "

                f"regime={final_regime.value} "

                f"risk={fused_risk:.2f}"

            )


        return verdict



    def _fault_verdict(
        self,
        vitals: VitalsSnapshot,
        policy: EscalationPolicy,
        faults: List[str]
    ) -> FusedVerdict:


        """
        Handles invalid telemetry.

        Invalid sensor data is never scored as healthy.

        Routes to WARNING state so human review
        can verify patient or equipment.
        """


        escalation = (

            policy.current_regime.value

            in

            (
                "stable",
                "caution"
            )

        )



        policy.current_regime = (

            OperationalRegime.WARNING

        )


        policy.pending_regime = None

        policy.dwell_count = 0



        if escalation:

            policy.escalation_locked = True

            policy.last_escalation_time = (

                vitals.timestamp

            )



        triggered = [

            (
                "CLINICAL_SAFETY_BYPASS: "
                "data-integrity fault skipped scoring"
            )

        ]



        triggered += [

            f"DATA_INTEGRITY_FAULT: {fault}"

            for fault in faults

        ]



        decision_data = {


            "vitals":

                asdict(vitals),


            "selected_engines":

                [],


            "outputs":

                [],


            "verdict":

            {

                "risk_score":

                    0.0,


                "regime":

                    "warning",


                "escalation_required":

                    escalation,


                "entropy":

                    0.0,


                "data_integrity_fault":

                    True,

            }

        }



        fingerprint = decision_fingerprint(
            decision_data
        )


        audit_hash = self.audit_ledger.append(

            vitals.patient_id,

            "clinical_assessment",

            {

                **decision_data,

                "decision_fingerprint":

                    fingerprint,

            }

        )


        logger.warning(

            "DATA_INTEGRITY_FAULT: "

            f"patient={vitals.patient_id} "

            f"faults={faults}"

        )



        return FusedVerdict(

            risk_score =
                0.0,

            regime =
                OperationalRegime.WARNING,

            confidence =
                0.0,

            entropy =
                0.0,

            active_engines =
                [],

            triggered_rules =
                triggered,

            timestamp =
                datetime.now(
                    timezone.utc
                ),

            escalation_required =
                escalation,

            decision_fingerprint =
                fingerprint,

            audit_hash =
                audit_hash,

        )



# =============================================================================
# SMOKE TEST
# =============================================================================


if __name__ == "__main__":


    vitals = VitalsSnapshot(

        patient_id =
            "P001",

        timestamp =
            datetime.now(
                timezone.utc
            ),

        heart_rate =
            155,

        oxygen_saturation =
            85.0,

        respiratory_rate =
            35,

        temperature =
            38.5,


        context = {

            "age_months":
                24,

            "force_heavy":
                True,

        }

    )



    engine = ObserveClinicalEngine()



    verdict = engine.evaluate(
        vitals
    )


    print(

        f"Risk: {verdict.risk_score:.2f} | "

        f"Regime: {verdict.regime.value} | "

        f"Entropy: {verdict.entropy:.3f}"

    )


    print(

        f"Engines run: "

        f"{verdict.active_engines}"

    )


    print(

        f"Triggered ({len(verdict.triggered_rules)}):"

    )


    for rule in verdict.triggered_rules:

        print(
            f"  - {rule}"
        )


    print(

        "Audit chain valid: "

        f"{engine.audit_ledger.verify_integrity()}"

    )



    # Second evaluation tests escalation persistence

    verdict2 = engine.evaluate(
        vitals
    )


    print(

        "\nSecond call: "

        f"Regime={verdict2.regime.value} "

        "Escalation policy tested"

    )