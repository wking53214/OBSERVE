"""
ClinicalSignalValidator

Salvaged from ARCHIVE/extracted/report_8 before ARCHIVE's cleanup pass
closed out. Confirmed via cross-repo search: not present anywhere else
in the sweep (only hits were raw source transcripts, never implemented
code) - genuinely novel, unlike its neighbors in the same file (which
turned out to be the same identity/hedging/causal-check family already
covered by CITADEL, just renamed again).

Distinct from CITADEL's checks by design, not by accident: CITADEL
penalizes hedging language everywhere. This validator does the
opposite on purpose - HEDGING_IS_GOOD - because appropriate epistemic
caution ("may", "uncertain") is a sign of a well-formed clinical signal,
not a defect. What it actually requires is concreteness: a time anchor,
a numeric value, and clinical context. A signal can hedge all it wants;
it just can't be vague about when, how much, or who.

Placed here (not merged into observe_clinical_risk_source.py) because
that source file is itself flattened/unreconstructed - same defect
CITADEL's artifact_1.py had. This follows OBSERVE's existing
_source.py / _adapter.py convention as its own small adapter rather
than adding to a file that doesn't currently run.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


class ClinicalSignalValidator:
    """Domain-specific validation for clinical signals.

    Opposite of linguistic polishing: this checks for the PRESENCE of
    concrete grounding, not the absence of hedging.
    """

    REQUIRED_CLINICAL_MARKERS = {
        "temporal_specificity": re.compile(
            r"\b(\d{1,2}:\d{2}|hour|minute|second|onset)\b", re.IGNORECASE
        ),
        "numeric_value": re.compile(
            r"\b\d+(\.\d+)?(?:\s*(?:bpm|mmHg|beats|percent|%|SpO2|O2|sats))\b",
            re.IGNORECASE,
        ),
        "clinical_context": re.compile(
            r"\b(patient|neonate|infant|pediatric|vital|monitor|alert|abnormal)\b",
            re.IGNORECASE,
        ),
    }

    # Deliberately NOT penalized - see module docstring.
    HEDGING_IS_GOOD = re.compile(
        r"\b(may|might|could|possibly|uncertain|unclear|suggest)\b",
        re.IGNORECASE,
    )

    def __init__(self, profile_name: str = "clinical"):
        self.profile_name = profile_name
        self.validation_log: List[Dict[str, Any]] = []

    def validate_signal(self, signal_text: str) -> Tuple[bool, List[str]]:
        """Check if signal has minimum clinical coherence."""
        failures: List[str] = []

        if not self.REQUIRED_CLINICAL_MARKERS["temporal_specificity"].search(signal_text):
            failures.append("Missing temporal specificity (when did this occur?)")

        if not self.REQUIRED_CLINICAL_MARKERS["numeric_value"].search(signal_text):
            failures.append("Missing quantitative values (vital signs, measurements)")

        if not self.REQUIRED_CLINICAL_MARKERS["clinical_context"].search(signal_text):
            failures.append("Missing clinical context (what patient/system?)")

        is_valid = len(failures) == 0

        self.validation_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_sample": signal_text[:100],
            "is_valid": is_valid,
            "failures": failures,
        })

        return is_valid, failures


if __name__ == "__main__":
    v = ClinicalSignalValidator()
    print(v.validate_signal("Patient HR dropped to 58 bpm at 03:12, monitor alert triggered."))
    print(v.validate_signal("Patient seems a little off today."))
    print(v.validate_signal("Onset unclear, but HR possibly trending low, 62 bpm, infant monitor flagged."))
