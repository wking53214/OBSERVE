from __future__ import annotations
import copy
import hashlib
import json
import uuid
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Type

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
class CanonicalSHA256Hasher:
   """Computes deterministic SHA-256 hashes for canonicalized event payloads."""
   ROOT_HASH = "GENESIS"

   @staticmethod
   def canonicalize(data: Any) -> str:
       return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       event_data = payload.get("event_data", {})
       previous_hash = payload.get("previous_hash", self.ROOT_HASH)
       
       canonical_payload = {
           "previous_hash": previous_hash,
           "event_id": event_data.get("event_id", ""),
           "entity_id": event_data.get("entity_id", ""),
           "sequence_no": event_data.get("sequence_no", 0),
           "event_type": event_data.get("event_type", ""),
           "delta": event_data.get("delta", {}),
           "provenance": event_data.get("provenance", {})
       }
       
       computed_hash = hashlib.sha256(self.canonicalize(canonical_payload).encode("utf-8")).hexdigest()
       payload["computed_hash"] = computed_hash
       headers["structural_indices"]["hash_digest"] = computed_hash
       return payload


@register_as_module
class EventStoreModule:
   """Manages partitioned append-only ledger streams and state hash tracking."""
   def __init__(self) -> None:
       self._streams: Dict[str, List[Dict[str, Any]]] = {}
       self._heads: Dict[str, str] = {}
       self._hasher = CanonicalSHA256Hasher()

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       entity_id = payload.get("entity_id", "DEFAULT_ENTITY")
       event_type = payload.get("event_type", "UNKNOWN")
       delta = payload.get("delta", {})
       provenance = payload.get("provenance", {})
       action = payload.get("action", "append")

       if action == "append":
           stream = self._streams.setdefault(entity_id, [])
           seq_no = len(stream) + 1
           event_id = str(uuid.uuid4())
           event_record = {
               "event_id": event_id,
               "entity_id": entity_id,
               "sequence_no": seq_no,
               "event_type": event_type,
               "delta": copy.deepcopy(delta),
               "provenance": provenance
           }
           prev_hash = self._heads.get(entity_id, CanonicalSHA256Hasher.ROOT_HASH)
           hash_payload = {"event_data": event_record, "previous_hash": prev_hash}
           hashed_res = self._hasher.process(hash_payload)
           curr_hash = hashed_res["computed_hash"]
           
           stream.append(event_record)
           self._heads[entity_id] = curr_hash
           payload["committed_event"] = event_record
           payload["event_hash"] = curr_hash
           headers["structural_indices"]["head_hash"] = curr_hash
           headers["metadata"]["sequence_number"] = seq_no
       elif action == "replay":
           since_seq = payload.get("since_sequence", 0)
           stream = self._streams.get(entity_id, [])
           payload["replayed_events"] = [e for e in stream if e["sequence_no"] > since_seq]
           
       return payload


@register_as_module
class ClinicalReducerModule:
   """Executes deterministic domain state reduction over normalized clinical events."""
   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       context = copy.deepcopy(payload.get("context", {}))
       event = payload.get("proposed_event", {})
       event_type = event.get("event_type", "")

       if event_type == "vitals":
           context["vitals"] = event.get("delta", {})
       elif event_type == "escalation":
           context["escalation_logged"] = True
       elif event_type == "status":
           context["critical_status"] = event.get("delta", {}).get("status")
       else:
           raise ValueError(f"Unsupported event type: {event_type}")

       payload["projected_context"] = context
       return payload


@register_as_module
class GovernanceAuditorModule:
   """Audits state transitions against clinical invariants using read-only proxies."""
   def _critical_requires_escalation(
       self, before: Mapping[str, Any], event: Dict[str, Any], after: Mapping[str, Any]
   ) -> Tuple[bool, str]:
       if after.get("critical_status") == "CRITICAL" and not after.get("escalation_logged", False):
           return False, "Safety violation: critical state transition detected without active escalation log"
       return True, "OK"

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       current_context = payload.get("context", {})
       projected_context = payload.get("projected_context", {})
       event = payload.get("proposed_event", {})

       before_view = MappingProxyType(current_context)
       after_view = MappingProxyType(projected_context)

       valid, msg = self._critical_requires_escalation(before_view, event, after_view)
       errors = [] if valid else [f"critical_requires_escalation: {msg}"]

       payload["audit_passed"] = valid
       payload["audit_errors"] = errors
       
       headers["risk_metrics"]["governance_valid"] = valid
       headers["risk_metrics"]["violation_count"] = len(errors)
       return payload


@register_as_module
class SnapshotManagerModule:
   """Manages interval-based state snapshotting and active memory cache synchronization."""
   def __init__(self, interval: int = 1) -> None:
       self._interval = interval
       self._snapshots: Dict[str, Dict[str, Any]] = {}

   def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
       headers = payload.setdefault("_gaps_headers", {"metadata": {}, "risk_metrics": {}, "structural_indices": {}})
       entity_id = payload.get("entity_id", "DEFAULT_ENTITY")
       seq_no = payload.get("sequence_no", 0)
       projected_context = payload.get("projected_context", {})
       
       last_snap = self._snapshots.get(entity_id, {"seq": 0, "context": {}})
       unsnapped_count = seq_no - last_snap["seq"]

       if unsnapped_count >= self._interval:
           self._snapshots[entity_id] = {
               "seq": seq_no,
               "context": copy.deepcopy(projected_context)
           }
           payload["snapshot_taken"] = True
           headers["metadata"]["snapshot_sequence"] = seq_no
       else:
           payload["snapshot_taken"] = False

       return payload


# =====================================================================
# CENTRALIZED BINDING ENGINE AND ORCHESTRATOR
# =====================================================================
@register_as_module
class CoreOrchestratorBinder:
   """Centralized binding engine validating handshakes and sequencing execution."""
   def __init__(self) -> None:
       self.event_store = EventStoreModule()
       self.reducer = ClinicalReducerModule()
       self.auditor = GovernanceAuditorModule()
       self.snapshot_manager = SnapshotManagerModule(interval=1)

   def validate_handshakes(self) -> bool:
       """Validates module authentication before pipeline execution."""
       modules = [
           CanonicalSHA256Hasher,
           EventStoreModule,
           ClinicalReducerModule,
           GovernanceAuditorModule,
           SnapshotManagerModule
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

       entity_id = payload.get("entity_id", "PATIENT_001")
       event_type = payload.get("event_type", "vitals")
       delta = payload.get("delta", {})
       provenance = payload.get("provenance", {})
       current_context = payload.get("current_context", {})

       proposed_event = {
           "event_id": "PROVISIONAL",
           "entity_id": entity_id,
           "sequence_no": 1,
           "event_type": event_type,
           "delta": delta,
           "provenance": provenance
       }

       # Step 1: Reducer projection
       reducer_payload = {"context": current_context, "proposed_event": proposed_event}
       reducer_res = self.reducer.process(reducer_payload)
       projected_context = reducer_res["projected_context"]

       # Step 2: Governance Auditor
       auditor_payload = {
           "context": current_context,
           "projected_context": projected_context,
           "proposed_event": proposed_event,
           "_gaps_headers": headers
       }
       auditor_res = self.auditor.process(auditor_payload)

       if not auditor_res["audit_passed"]:
           clinical_summary = {
               "transaction_status": "REJECTED",
               "entity_id": entity_id,
               "errors": auditor_res["audit_errors"],
               "gaps_headers": headers
           }
           payload["transaction_result"] = {"accepted": False, "messages": auditor_res["audit_errors"]}
           payload["clinical_summary"] = json.dumps(clinical_summary, indent=2, default=str)
           return payload

       # Step 3: Event Store Commit
       store_payload = {
           "action": "append",
           "entity_id": entity_id,
           "event_type": event_type,
           "delta": delta,
           "provenance": provenance,
           "_gaps_headers": headers
       }
       store_res = self.event_store.process(store_payload)
       committed_event = store_res["committed_event"]

       # Step 4: Snapshot Manager
       snap_payload = {
           "entity_id": entity_id,
           "sequence_no": committed_event["sequence_no"],
           "projected_context": projected_context,
           "_gaps_headers": headers
       }
       snap_res = self.snapshot_manager.process(snap_payload)

       clinical_summary = {
           "transaction_status": "ACCEPTED",
           "entity_id": entity_id,
           "sequence_no": committed_event["sequence_no"],
           "event_hash": store_res["event_hash"],
           "snapshot_updated": snap_res["snapshot_taken"],
           "gaps_headers": headers
       }

       payload["transaction_result"] = {"accepted": True, "messages": ["OK"]}
       payload["updated_context"] = projected_context
       payload["clinical_summary"] = json.dumps(clinical_summary, indent=2, default=str)
       return payload


if __name__ == "__main__":
   sample_transaction = {
       "entity_id": "PATIENT_102",
       "event_type": "vitals",
       "delta": {"heart_rate": 82, "bp_sys": 120},
       "provenance": {"actor_id": "USER_DOC_01", "policy_id": "POL_99", "justification": "Routine check"},
       "current_context": {}
   }

   binder = CoreOrchestratorBinder()
   output = binder.process(sample_transaction)
   print("--- TRANSACTION COMPLETED ---")
   print(output["clinical_summary"])
