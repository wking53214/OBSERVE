from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

# =====================================================================
# GOVERNANCE REGISTRY AND DECORATOR
# =====================================================================
MODULE_REGISTRY: Dict[str, Type] = {}

def register_as_module(cls: Type) -> Type:
   """Governance handshake validation decorator."""
   MODULE_REGISTRY[cls.__name__] = cls
   setattr(cls, "_gaps_authenticated", True)
   setattr(cls, "_registered", True)
   return cls


# =====================================================================
# GSA UNIVERSAL ADAPTER MODULES
# =====================================================================
@register_as_module
class VitalValidationModule:
   """Validates physical vital bounds and logs structural risk metrics."""
   VITALS_PHYSICAL_BOUNDS = {
       "heart_rate": (0.0, 350.0),
       "oxygen_saturation": (0.0, 100.0),
       "respiratory_rate": (0.0, 150.0),
       "temperature": (20.0, 45.0),
   }

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       vitals = payload.get("vitals", {})
       faults = []

       for k, (lo, hi) in self.VITALS_PHYSICAL_BOUNDS.items():
           val = vitals.get(k)
           if not isinstance(val, (int, float)) or not math.isfinite(val):
               faults.append(f"{k}=nonfinite")
           elif not (lo <= val <= hi):
               faults.append(f"{k}=out_of_range")

       payload["validation_faults"] = faults
       headers["risk_metrics"]["validation_fault_count"] = len(faults)
       headers["structural_indices"]["vitals_validated"] = len(faults) == 0
       return payload


@register_as_module
class RiskAssessmentAdaptersModule:
   """Executes ensemble clinical risk adapters over standardized vital streams."""
   PEDIATRIC_NORMS = {
       "neonatal": {"hr_high": 160, "hr_low": 80, "rr_high": 50, "o2_low": 90, "temp_high": 38.5},
       "infant":   {"hr_high": 150, "hr_low": 90, "rr_high": 45, "o2_low": 90, "temp_high": 39.0},
       "toddler":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
       "child":    {"hr_high": 130, "hr_low": 100, "rr_high": 35, "o2_low": 92, "temp_high": 39.5},
       "generic":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
   }

   def _get_age_group(self, age_months: Optional[int]) -> str:
       if age_months is None: return "generic"
       if age_months < 3: return "neonatal"
       if age_months < 12: return "infant"
       if age_months < 36: return "toddler"
       return "child"

   def _regime_distribution(self, score: float) -> Dict[str, float]:
       score = max(0.0, min(1.0, score))
       if score >= 0.75: return {"stable": 0.05, "caution": 0.10, "warning": 0.25, "critical": 0.60}
       if score >= 0.50: return {"stable": 0.10, "caution": 0.20, "warning": 0.55, "critical": 0.15}
       if score >= 0.25: return {"stable": 0.35, "caution": 0.50, "warning": 0.12, "critical": 0.03}
       return {"stable": 0.88, "caution": 0.08, "warning": 0.03, "critical": 0.01}

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       vitals = payload.get("vitals", {})
       ctx = vitals.get("context", {})
       age_key = self._get_age_group(ctx.get("age_months"))
       norms = self.PEDIATRIC_NORMS[age_key]

       outputs = []

       # 1. Heuristic Adapter
       h_score, h_trig = 0.0, []
       if vitals.get("oxygen_saturation", 100) < norms["o2_low"]:
           h_score += 0.3
           h_trig.append("low_o2")
       if vitals.get("heart_rate", 80) > norms["hr_high"]:
           h_score += 0.2
           h_trig.append("tachy")
       if vitals.get("temperature", 37.0) > norms["temp_high"]:
           h_score += 0.1
           h_trig.append("fever")
       outputs.append({
           "engine": "heuristic", "score": min(h_score, 1.0),
           "confidence": 0.9 if ctx.get("age_months") is not None else 0.7,
           "regime": self._regime_distribution(h_score), "triggered": h_trig, "abstained": False
       })

       # 2. Bayesian Adapter
       o2_dev = (norms["o2_low"] - vitals.get("oxygen_saturation", 100)) / 5.0
       hr_dev = (vitals.get("heart_rate", 80) - norms["hr_high"]) / 10.0
       b_score, b_trig = 0.0, []
       if o2_dev > 2:
           b_score += 0.5
           b_trig.append("o2_dev")
       if abs(hr_dev) > 2:
           b_score += 0.3
           b_trig.append("hr_dev")
       outputs.append({
           "engine": "bayesian", "score": min(b_score, 1.0),
           "confidence": 0.85, "regime": self._regime_distribution(b_score),
           "triggered": b_trig, "abstained": False
       })

       # 3. Behavioral Adapter
       bh_score, bh_trig = 0.0, []
       if vitals.get("oxygen_saturation", 100) < 92 and vitals.get("heart_rate", 80) > 140:
           bh_score += 0.4
           bh_trig.append("stress_combo")
       if vitals.get("respiratory_rate", 20) > 40:
           bh_score += 0.3
           bh_trig.append("tachypnea")
       outputs.append({
           "engine": "behavioral", "score": min(bh_score, 1.0),
           "confidence": 0.8, "regime": self._regime_distribution(bh_score),
           "triggered": bh_trig, "abstained": False
       })

       payload["risk_outputs"] = outputs
       headers["metadata"]["active_adapters"] = [o["engine"] for o in outputs]
       return payload


@register_as_module
class FusionEngineModule:
   """Fuses multi-adapter risk estimations and evaluates regime distribution entropy."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       outputs = payload.get("risk_outputs", [])
       active = [o for o in outputs if not o.get("abstained", False)]
       pool = active if active else outputs

       if not pool:
           payload["fused_result"] = {"risk_score": 0.0, "entropy": 0.0, "regime_dist": {}}
           return payload

       weight_sum = sum(o["confidence"] for o in pool) or 1.0
       fused_risk = sum(o["score"] * o["confidence"] for o in pool) / weight_sum

       regime_dist = {"stable": 0.0, "caution": 0.0, "warning": 0.0, "critical": 0.0}
       for o in pool:
           for k, v in o["regime"].items():
               regime_dist[k] += v * o["confidence"]

       regime_dist = {k: v / weight_sum for k, v in regime_dist.items()}
       entropy = -sum(p * math.log2(p + 1e-9) for p in regime_dist.values())

       payload["fused_result"] = {
           "risk_score": fused_risk,
           "entropy": entropy,
           "regime_distribution": regime_dist,
           "mean_confidence": sum(o["confidence"] for o in outputs) / max(len(outputs), 1)
       }

       headers["risk_metrics"]["fused_risk_score"] = fused_risk
       headers["risk_metrics"]["fusion_entropy"] = entropy
       return payload


@register_as_module
class RegimeClassificationModule:
   """Maps fused scores to operational regimes and enforces escalation mandates."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       fused = payload.get("fused_result", {})
       faults = payload.get("validation_faults", [])

       if faults:
           classified_regime = "warning"
           escalation = True
       else:
           dist = fused.get("regime_distribution", {})
           classified_regime = max(dist, key=dist.get) if dist else "stable"
           escalation = classified_regime in ("warning", "critical")

       fingerprint_data = {
           "vitals": payload.get("vitals", {}),
           "risk": fused.get("risk_score", 0.0),
           "regime": classified_regime,
           "entropy": fused.get("entropy", 0.0)
       }
       decision_hash = hashlib.sha256(
           json.dumps(fingerprint_data, sort_keys=True, default=str).encode()
       ).hexdigest()

       verdict = {
           "classified_regime": classified_regime,
           "escalation_required": escalation,
           "decision_fingerprint": decision_hash,
           "timestamp": datetime.now(timezone.utc).isoformat()
       }

       payload["verdict"] = verdict
       headers["metadata"]["classified_regime"] = classified_regime
       headers["risk_metrics"]["escalation_required"] = escalation
       headers["structural_indices"]["decision_fingerprint"] = decision_hash
       return payload


# =====================================================================
# CENTRALIZED BINDING ENGINE AND ORCHESTRATOR
# =====================================================================
@register_as_module
class CoreOrchestratorBinder:
   """Centralized binding engine validating handshakes and sequencing execution."""

   def __init__(self) -> None:
       self.validator = VitalValidationModule()
       self.risk_adapters = RiskAssessmentAdaptersModule()
       self.fusion_engine = FusionEngineModule()
       self.classifier = RegimeClassificationModule()

   def validate_handshakes(self) -> bool:
       """Validates module authentication before pipeline execution."""
       modules = [
           VitalValidationModule,
           RiskAssessmentAdaptersModule,
           FusionEngineModule,
           RegimeClassificationModule
       ]
       for mod in modules:
           if not getattr(mod, "_gaps_authenticated", False):
               raise PermissionError(f"Handshake failed for module: {mod.__name__}")
       return True

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       """Sequences pipeline execution and outputs serialized clinical summary."""
       self.validate_handshakes()

       headers = payload.setdefault("_gaps_headers", {
           "metadata": {"orchestrator": self.__class__.__name__, "timestamp": time.time()},
           "risk_metrics": {},
           "structural_indices": {}
       })

       payload = self.validator.process(payload)
       payload = self.risk_adapters.process(payload)
       payload = self.fusion_engine.process(payload)
       payload = self.classifier.process(payload)

       clinical_summary = {
           "patient_id": payload.get("vitals", {}).get("patient_id"),
           "classified_regime": payload.get("verdict", {}).get("classified_regime"),
           "escalation_required": payload.get("verdict", {}).get("escalation_required"),
           "fused_risk_score": payload.get("fused_result", {}).get("risk_score"),
           "entropy": payload.get("fused_result", {}).get("entropy"),
           "decision_fingerprint": payload.get("verdict", {}).get("decision_fingerprint"),
           "gaps_headers": headers
       }

       payload["clinical_summary"] = json.dumps(clinical_summary, indent=2, default=str)
       return payload


if __name__ == "__main__":
   sample_vitals_payload = {
       "vitals": {
           "patient_id": "PED-PATIENT-881",
           "heart_rate": 165.0,
           "oxygen_saturation": 88.0,
           "respiratory_rate": 48.0,
           "temperature": 39.2,
           "context": {"age_months": 8}
       }
   }

   binder = CoreOrchestratorBinder()
   result = binder.process(sample_vitals_payload)
   print("--- CLINICAL RISK EVALUATION COMPLETED ---")
   print(result["clinical_summary"])
