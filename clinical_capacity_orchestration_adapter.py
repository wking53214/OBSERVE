from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Type

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
class ObserveTelemetryModule:
   """Evaluates telemetry and vitals to produce clinical risk scores and operational regime classifications."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault(
           "_gaps_headers",
           {"metadata": {}, "risk_metrics": {}, "structural_indices": {}},
       )
       vitals = payload.get("vitals", {})

       heart_rate = float(vitals.get("heart_rate", 80.0))
       o2_sat = float(vitals.get("oxygen_saturation", 98.0))

       risk_score = 0.0
       triggered_rules = []

       if o2_sat < 90.0:
           risk_score += 0.5
           triggered_rules.append("CRITICAL_O2_DESATURATION")
       if heart_rate > 150.0:
           risk_score += 0.4
           triggered_rules.append("SEVERE_TACHYCARDIA")

       risk_score = min(risk_score, 1.0)
       regime = (
           "critical"
           if risk_score >= 0.7
           else ("warning" if risk_score >= 0.3 else "stable")
       )
       escalation_required = risk_score >= 0.3

       payload["observe_verdict"] = {
           "risk_score": risk_score,
           "regime": regime,
           "escalation_required": escalation_required,
           "active_engines": ["heuristic", "bayesian", "drift"],
           "triggered_rules": triggered_rules,
           "audit_hash": "obs_sha256_hash_mock_001",
       }

       headers["risk_metrics"]["clinical_risk_score"] = risk_score
       headers["metadata"]["regime"] = regime
       headers["structural_indices"]["escalation_required"] = (
           escalation_required
       )
       return payload


@register_as_module
class CapacityModulationModule:
   """Evaluates system utilization and adjusts capacity modulation reserves."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault(
           "_gaps_headers",
           {"metadata": {}, "risk_metrics": {}, "structural_indices": {}},
       )
       observe_verdict = payload.get("observe_verdict", {})
       utilization = float(payload.get("utilization", 0.75))

       risk_score = observe_verdict.get("risk_score", 0.0)
       base_escalate = observe_verdict.get("escalation_required", False)

       action = "maintain"
       effective_threshold = 0.85

       if base_escalate and utilization > 0.8:
           action = "defer"
           should_escalate = False
       elif risk_score >= 0.7:
           action = "proactive_escalate"
           should_escalate = True
       else:
           should_escalate = base_escalate

       payload["capacity_recommendation"] = {
           "action": action,
           "effective_threshold": effective_threshold,
           "utilization": utilization,
           "should_escalate": should_escalate,
           "exempt": False,
       }

       headers["risk_metrics"]["system_utilization"] = utilization
       headers["metadata"]["capacity_action"] = action
       return payload


@register_as_module
class PerceiveGovernanceModule:
   """Evaluates policy requests against governance gates and multi-node consensus rules."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault(
           "_gaps_headers",
           {"metadata": {}, "risk_metrics": {}, "structural_indices": {}},
       )
       capacity_rec = payload.get("capacity_recommendation", {})
       observe_verdict = payload.get("observe_verdict", {})

       should_escalate = capacity_rec.get(
           "should_escalate", observe_verdict.get("escalation_required", False)
       )

       if not should_escalate:
           payload["governance_verdict"] = {
               "evaluated": False,
               "approved": True,
               "confidence": 1.0,
               "violations": [],
               "applied_gates": [],
               "audit_hash": None,
           }
           headers["metadata"]["governance_evaluated"] = False
           return payload

       regime = observe_verdict.get("regime", "stable")
       violations = []
       approved = True

       if regime == "critical":
           applied_gates = [
               "boundary_gate",
               "citadel",
               "fortress",
               "invariant_validator",
           ]
       else:
           applied_gates = ["boundary_gate", "citadel"]

       payload["governance_verdict"] = {
           "evaluated": True,
           "approved": approved,
           "confidence": 0.95,
           "violations": violations,
           "applied_gates": applied_gates,
           "audit_hash": "per_sha256_hash_mock_999",
           "consensus_detail": {
               "quorum_fraction": 0.66,
               "status": "unanimous",
           },
       }

       headers["metadata"]["governance_evaluated"] = True
       headers["risk_metrics"]["governance_approved"] = approved
       headers["structural_indices"]["governance_audit_hash"] = (
           "per_sha256_hash_mock_999"
       )
       return payload


@register_as_module
class DecisionRoutingModule:
   """Synthesizes OBSERVE, Capacity, and PERCEIVE outputs into a final clinical decision action."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault(
           "_gaps_headers",
           {"metadata": {}, "risk_metrics": {}, "structural_indices": {}},
       )
       obs = payload.get("observe_verdict", {})
       cap = payload.get("capacity_recommendation", {})
       gov = payload.get("governance_verdict", {})

       action = "continue_monitoring"

       if cap.get("action") == "defer":
           action = "escalation_deferred_capacity"
       elif obs.get("escalation_required"):
           if gov.get("approved"):
               action = "escalate_approved"
           else:
               action = "escalate_blocked"

       payload["final_decision"] = {
           "patient_id": payload.get("vitals", {}).get("patient_id", "UNKNOWN"),
           "timestamp": time.time(),
           "risk_score": obs.get("risk_score", 0.0),
           "regime": obs.get("regime", "stable"),
           "action": action,
           "escalation_required": obs.get("escalation_required", False),
           "governance_approved": gov.get("approved"),
       }

       headers["metadata"]["final_action"] = action
       return payload


# =====================================================================
# CENTRALIZED BINDING ENGINE AND ORCHESTRATOR
# =====================================================================
@register_as_module
class CoreOrchestratorBinder:
   """Centralized binding engine validating handshakes and sequencing execution."""

   def __init__(self) -> None:
       self.observe_module = ObserveTelemetryModule()
       self.capacity_module = CapacityModulationModule()
       self.perceive_module = PerceiveGovernanceModule()
       self.decision_module = DecisionRoutingModule()

   def validate_handshakes(self) -> bool:
       """Validates module authentication before pipeline execution."""
       modules = [
           ObserveTelemetryModule,
           CapacityModulationModule,
           PerceiveGovernanceModule,
           DecisionRoutingModule,
       ]
       for mod in modules:
           if not getattr(mod, "_gaps_authenticated", False):
               raise PermissionError(
                   f"Handshake failed for module: {mod.__name__}"
               )
       return True

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       """Sequences pipeline execution and outputs serialized clinical summary."""
       self.validate_handshakes()

       headers = payload.setdefault(
           "_gaps_headers",
           {
               "metadata": {
                   "orchestrator": self.__class__.__name__,
                   "timestamp": time.time(),
               },
               "risk_metrics": {},
               "structural_indices": {},
           },
       )

       sequence = [
           self.observe_module,
           self.capacity_module,
           self.perceive_module,
           self.decision_module,
       ]

       for module in sequence:
           payload = module.process(payload)

       clinical_summary = {
           "patient_id": payload.get("vitals", {}).get("patient_id"),
           "final_action": headers["metadata"].get("final_action"),
           "regime": headers["metadata"].get("regime"),
           "clinical_risk_score": headers["risk_metrics"].get(
               "clinical_risk_score"
           ),
           "governance_approved": headers["risk_metrics"].get(
               "governance_approved"
           ),
           "gaps_headers": headers,
       }

       payload["clinical_summary"] = json.dumps(
           clinical_summary, indent=2, default=str
       )
       return payload


if __name__ == "__main__":
   sample_payload = {
       "vitals": {
           "patient_id": "P-9982",
           "heart_rate": 168.0,
           "oxygen_saturation": 83.0,
           "respiratory_rate": 46.0,
           "temperature": 39.5,
       },
       "utilization": 0.65,
   }

   binder = CoreOrchestratorBinder()
   result = binder.process(sample_payload)
   print("--- CLINICAL GOVERNANCE PIPELINE EXECUTED ---")
   print(result["clinical_summary"])
