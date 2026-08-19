from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

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
class PolicyGateProcessorModule:
   """Evaluates multi-gate policy constraints over standardized requests."""

   @staticmethod
   def _evaluate_boundary(req: Dict[str, Any]) -> Dict[str, Any]:
       v = []
       if not req.get("request_id"): v.append("missing id")
       if not req.get("request_type"): v.append("missing type")
       allowed = {"escalate_patient", "modify_rule", "export_data", "emergency_override"}
       if req.get("request_type") not in allowed:
           v.append("invalid type")
       ok = len(v) == 0
       return {"gate": "boundary_gate", "approved": ok, "confidence": 0.95 if ok else 0.85, "violations": v}

   @staticmethod
   def _evaluate_citadel(req: Dict[str, Any]) -> Dict[str, Any]:
       v = []
       ctx = req.get("context", {})
       if len(ctx.get("justification", "")) < 10:
           v.append("weak justification")
       ok = len(v) == 0
       return {"gate": "citadel", "approved": ok, "confidence": 0.85 if ok else 0.80, "violations": v}

   @staticmethod
   def _evaluate_fortress(req: Dict[str, Any]) -> Dict[str, Any]:
       v = []
       ctx = req.get("context", {})
       if ctx.get("bypass_approval"):
           v.append("bypass forbidden")
       ok = len(v) == 0
       return {"gate": "fortress", "approved": ok, "confidence": 0.92 if ok else 0.88, "violations": v}

   @staticmethod
   def _evaluate_sentinel(req: Dict[str, Any]) -> Dict[str, Any]:
       v = []
       ctx = req.get("context", {})
       if ctx.get("operation_count_today", 0) > 50:
           v.append("rate anomaly")
       ok = len(v) == 0
       return {"gate": "sentinel", "approved": ok, "confidence": 0.88, "violations": v}

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       request_data = payload.get("request", {})

       gate_results = [
           self._evaluate_boundary(request_data),
           self._evaluate_citadel(request_data),
           self._evaluate_fortress(request_data),
           self._evaluate_sentinel(request_data)
       ]

       payload["gate_results"] = gate_results
       total_violations = sum(len(g["violations"]) for g in gate_results)
       headers["risk_metrics"]["total_gate_violations"] = total_violations
       headers["metadata"]["gates_evaluated"] = [g["gate"] for g in gate_results]
       return payload


@register_as_module
class ConsensusEngineModule:
   """Calculates bounded geometric mean confidence and unanimous consensus."""

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       gate_results = payload.get("gate_results", [])

       if not gate_results:
           payload["consensus"] = {"approved": False, "confidence": 0.0, "violating_gates": ["no_gate_outputs"]}
           headers["risk_metrics"]["consensus_approved"] = False
           return payload

       violating_gates = [g["gate"] for g in gate_results if not g["approved"]]
       confidences = [max(0.0, min(1.0, g["confidence"])) for g in gate_results]

       approved = len(violating_gates) == 0
       geometric_mean = math.prod(confidences) ** (1.0 / len(confidences)) if confidences else 0.0

       consensus_data = {
           "approved": approved,
           "confidence": geometric_mean,
           "violating_gates": violating_gates,
           "consensus_type": "unanimous"
       }

       payload["consensus"] = consensus_data
       headers["risk_metrics"]["consensus_approved"] = approved
       headers["risk_metrics"]["consensus_confidence"] = geometric_mean
       return payload


@register_as_module
class AuditLedgerModule:
   """Generates hash-chained immutable audit ledger entries."""

   def __init__(self) -> None:
       self.chain_hash = hashlib.sha256(b"GENESIS").hexdigest()
       self.entries: List[Dict[str, Any]] = []

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       request_data = payload.get("request", {})
       consensus_data = payload.get("consensus", {})

       audit_id = hashlib.sha256(str(len(self.entries)).encode()).hexdigest()[:16]
       timestamp = datetime.now(timezone.utc).isoformat()

       entry_body = {
           "audit_id": audit_id,
           "timestamp": timestamp,
           "request_snapshot": request_data,
           "consensus": consensus_data,
           "previous_hash": self.chain_hash
       }

       serialized = json.dumps(entry_body, sort_keys=True, default=str).encode()
       entry_hash = hashlib.sha256(serialized).hexdigest()
       self.chain_hash = hashlib.sha256((self.chain_hash + entry_hash).encode()).hexdigest()

       entry_body["immutable_hash"] = self.chain_hash
       self.entries.append(entry_body)

       payload["audit_entry"] = entry_body
       headers["structural_indices"]["immutable_audit_hash"] = self.chain_hash
       headers["structural_indices"]["previous_chain_hash"] = entry_body["previous_hash"]
       return payload


@register_as_module
class EventStoreModule:
   """Appends append-only event-sourced record artifacts."""

   def __init__(self) -> None:
       self.events: List[Dict[str, Any]] = []

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       request_data = payload.get("request", {})
       consensus_data = payload.get("consensus", {})

       event_id = hashlib.sha256(str(len(self.events)).encode()).hexdigest()[:16]
       event_record = {
           "event_id": event_id,
           "event_type": "policy_evaluation",
           "timestamp": datetime.now(timezone.utc).isoformat(),
           "actor_id": request_data.get("actor_id", "system"),
           "details": {"approved": consensus_data.get("approved", False)}
       }

       self.events.append(event_record)
       payload["event_record"] = event_record
       headers["metadata"]["event_id"] = event_id
       return payload


# =====================================================================
# CENTRALIZED BINDING ENGINE AND ORCHESTRATOR
# =====================================================================
@register_as_module
class CoreOrchestratorBinder:
   """Centralized binding engine validating handshakes and sequencing execution."""

   def __init__(self) -> None:
       self.gate_processor = PolicyGateProcessorModule()
       self.consensus_engine = ConsensusEngineModule()
       self.audit_ledger = AuditLedgerModule()
       self.event_store = EventStoreModule()

   def validate_handshakes(self) -> bool:
       """Validates module authentication before pipeline execution."""
       modules = [
           PolicyGateProcessorModule,
           ConsensusEngineModule,
           AuditLedgerModule,
           EventStoreModule
       ]
       for mod in modules:
           if not getattr(mod, "_gaps_authenticated", False):
               raise PermissionError(f"Handshake failed for module: {mod.__name__}")
       return True

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       """Sequences pipeline execution and outputs serialized clinical summary."""
       self.validate_handshakes()

       headers = payload.setdefault("_gaps_headers", {
           "metadata": {"orchestrator": self.__class__.__name__, "timestamp": time.time(), "policy_version": "1.0.0"},
           "risk_metrics": {},
           "structural_indices": {}
       })

       payload = self.gate_processor.process(payload)
       payload = self.consensus_engine.process(payload)
       payload = self.audit_ledger.process(payload)
       payload = self.event_store.process(payload)

       clinical_summary = {
           "policy_version": "1.0.0",
           "request_id": payload.get("request", {}).get("request_id"),
           "consensus_approved": payload.get("consensus", {}).get("approved"),
           "confidence_score": payload.get("consensus", {}).get("confidence"),
           "violating_gates": payload.get("consensus", {}).get("violating_gates"),
           "audit_hash": payload.get("audit_entry", {}).get("immutable_hash"),
           "gaps_headers": headers
       }

       payload["clinical_summary"] = json.dumps(clinical_summary, indent=2, default=str)
       return payload


if __name__ == "__main__":
   sample_request = {
       "request": {
           "request_id": "REQ-101",
           "request_type": "escalate_patient",
           "subject_id": "P-990",
           "actor_id": "DR-402",
           "context": {"justification": "Patient experiencing severe acute symptoms."}
       }
   }

   binder = CoreOrchestratorBinder()
   result = binder.process(sample_request)
   print("--- EVALUATION COMPLETED ---")
   print(result["clinical_summary"])
