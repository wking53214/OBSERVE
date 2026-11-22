# Vendored files

Status note (2026-11-19, PR-4): the root engine files were re-synced to observe-perceive `d5962621321c791e79129bcfb807b5ee6e9eaa58` (`d596262`, main). Eight files now: the earlier five plus `clinical_settings.py`, `log_redaction.py` and `logic_stamp.py`, which the current engine imports. The scoring differences against the old engine are listed in `docs/ENGINE_RESYNC_DIFFERENCES.md` and need a clinical reviewer. The `sentinel_os/` copy is NOT re-synced here and still holds the older snapshot below.

Status note (2026-11-15): the pins below were last checked against this repo, not against current upstream. Upstream observe-perceive has moved past `e818659`; see `UPSTREAM.md`.

Status note (2026-11-19): observe-perceive's history has been rewritten. `e818659` and `717c2e2` are no longer on any of its branches; their twins (same date, subject and engine file) are `bca7a70` and `59f87b4`. The 70 rows for files that this repo's own history rewrite removed have been taken out of the table below (owner decision of 2026-11-18). Four other rows name files that later ordinary commits deleted; they are left as they are. The 2026-09-07 counts in the next line were not recomputed.

Status note (2026-11-20): four rows named files that are no longer in this repository (`sentinel_os/test_api_server_v2-1.py`, `sentinel_os/test_governor_failclosed_root.py`, `sentinel_os/rl_ingress_8110.log`, `sentinel_os/Tests/test_queue_staffing_bayes.py`) and were removed. The counts in the "Generated 2026-09-07" line below describe the tree at that date and were not recomputed.

Generated 2026-09-07. sentinel_os/ subtree: {'unique': 209, 'diverged': 53, 'identical': 140} of 402 files.

## Root pins and identity (restored by PR-4, 2026-11-22)

The root engine and its seven sibling modules are observe-perceive
`d5962621321c791e79129bcfb807b5ee6e9eaa58`, copied byte-for-byte and never edited here. Since PR-4 of
`RECONCILE_UPSTREAM_PLAN.md`, `sentinel_os/` holds byte-identical copies of the same eight files. From 2026-10-29
until then a stopgap pinned `sentinel_os/observe_consolidated.py` separately, because it was an older engine
(`bca7a70`) that still held a worsening patient at WARNING during the escalation lock.

| Pin | File | Upstream commit | sha256 |
| --- | --- | --- | --- |
| root | `observe_consolidated.py` | `d596262` | `cf494f53b663b080b5d0f0baa276d8bc41ef8ac7eb4c91e21dbe8d638269338b` |
| root | `cassette.py` | `d596262` | `71b68245390e6f0706f57546839dbd3c28982d98ed522b1e81df88e3af24f8af` |
| root | `pediatric_cassette.py` | `d596262` | `af9d14d3559849a3e50d8e86c5ca6ef15588e929f4a4f80dfe1ecdd2c34d0157` |
| root | `kalman_trajectory.py` | `d596262` | `03be64ba12cbcb3c9fce5b0e20d839bac83537775bbc1a09f9d6c6f45a2e5e9a` |
| root | `governance_contracts.py` | `d596262` | `b483c91bab6a39f2180b69006bad43c525128b3d749b40e1d9db121c4f99b7e2` |
| root | `clinical_settings.py` | `d596262` | `62e06d7cce792e431695720dc20d639c9d1921fbdd070ba6c501ad553b3a9d71` |
| root | `log_redaction.py` | `d596262` | `8a499683eef8bfc4c9f4215f6296ee60dfb4fdb059c7d94b94145302b3935b12` |
| root | `logic_stamp.py` | `d596262` | `ce2ba57778b4a447c822622c3bfe91034056881d3c65f3a634cf9bb7d56abd2b` |

`test_observe_invariants.py::VendoredCopyStaysInSync` fails loudly if a root file stops matching its pin, if any
`sentinel_os/` copy stops being byte-identical to root, or if a row below stops declaring either `identical`.

OBSERVE chooses when the behavioral engine runs in one place, `observe_engine_gate.py`: it selects upstream's
`conservative_legacy` gate (OBSERVE's own rule) until a pediatrician signs off upstream's widened rule. That file is
OBSERVE's own and is not a copy.

## Re-sync log

- 2026-11-22 (PR-4): `sentinel_os/observe_consolidated.py` and the seven modules it needs (`cassette`, `pediatric_cassette`, `kalman_trajectory`, `governance_contracts`, `clinical_settings`, `log_redaction`, `logic_stamp`; the last three were missing) copied from root, so `sentinel_os/` is byte-identical to root for all eight. The older `sentinel_os/` engine (`bca7a70`) held a WARNING patient who worsened to CRITICAL at WARNING during the escalation lock; the current one escalates. One rule-5 test edit: `sentinel_os/test_observe_consolidated.py::TestEscalationPolicy::test_escalation_lock_prevents_immediate_re_escalation`, now asserting upstream's behaviour with upstream's lines. Full `sentinel_os/` suite with Postgres and Redis and the pinned requirements: 1006 passed, 5 failed, 6 skipped before and after (the same five; see the PR). The other `sentinel_os/` files PR-3 synced to `bca7a70` (`perceive_consolidated`, `clinical_governance_system` and their tests, `compliance_exporters`) were not moved by PR-4.
- 2026-11-19 (PR-3): ten observe-perceive-derived files in `sentinel_os/` (`observe_consolidated`, `perceive_consolidated`, `clinical_governance_system`, `kalman_trajectory`, `governance_contracts`, `compliance_exporters` and the four test files for them) re-synced byte-for-byte from observe-perceive `bca7a70`, and `cassette.py` and `pediatric_cassette.py` added. `sentinel_os/observe_consolidated.py` is now byte-identical to the root copy. The oxygen case (SpO2 86, age 24 months, with and without history, age missing, negative or not a number) gave the same five results before and after.

- 2026-10-29: `sentinel_os/queue_schema.py` re-synced from sentinel_os `b5d8e78` (byte-identical, sha256 `6969e87126ed074f...`). The previous copy was an older design that OBSERVE's own `api_server_v2.py` and `twin_sync_worker.py` had already outgrown (they call `namespace=`, `get_job`, `ping`, `promote_due` and `ack(result=)`, which it lacked). Its methods and reasons were a strict subset of upstream's, so nothing OBSERVE-only was lost. Row status above changed from `diverged` to `identical`.

| File | Upstream | Status |
| --- | --- | --- |
| `observe_consolidated.py` | observe-perceive | identical |
| `cassette.py` | observe-perceive | identical |
| `pediatric_cassette.py` | observe-perceive | identical |
| `kalman_trajectory.py` | observe-perceive | identical |
| `governance_contracts.py` | observe-perceive | identical |
| `clinical_settings.py` | observe-perceive | identical |
| `log_redaction.py` | observe-perceive | identical |
| `logic_stamp.py` | observe-perceive | identical |
| `test_observe_consolidated.py` | observe-perceive | diverged |
| `sentinel_os/APPLY-remove-fake-ppo-router.md` | (none) | unique |
| `sentinel_os/data.json` | (none) | unique |
| `sentinel_os/twin_failure_taxonomy_v1-1.md` | (none) | unique |
| `sentinel_os/api_server_v2-1.py` | (none) | unique |
| `sentinel_os/docker-compose-prod.yml` | GSA-815 | diverged |
| `sentinel_os/resilient_harness.py` | GSA-815 | identical |
| `sentinel_os/APPLY-4.md` | (none) | unique |
| `sentinel_os/adaptive_config.py` | GSA-815 | identical |
| `sentinel_os/master-patch-prompt.md` | (none) | unique |
| `sentinel_os/drive_safety_module.py` | (none) | unique |
| `sentinel_os/fix-bayes-learning-loop.bundle` | (none) | unique |
| `sentinel_os/chaos_metrics_run2-1.json` | (none) | unique |
| `sentinel_os/tracing.py` | sentinel_os | identical |
| `sentinel_os/APPLY-remove-dead-callerintent-enum.md` | (none) | unique |
| `sentinel_os/claim.lua.txt` | (none) | unique |
| `sentinel_os/sealed_demographic_channel.sql` | sentinel_os | identical |
| `sentinel_os/twin_migrate.py` | sentinel_os | diverged |
| `sentinel_os/ai_cost_tracking.py` | sentinel_os | identical |
| `sentinel_os/event_v1.py` | sentinel_os | diverged |
| `sentinel_os/cage_match_brief_v1.md` | (none) | unique |
| `sentinel_os/observe_consolidated.py` | observe-perceive | identical |
| `sentinel_os/cassette.py` | observe-perceive | identical |
| `sentinel_os/pediatric_cassette.py` | observe-perceive | identical |
| `sentinel_os/clinical_settings.py` | observe-perceive | identical |
| `sentinel_os/log_redaction.py` | observe-perceive | identical |
| `sentinel_os/logic_stamp.py` | observe-perceive | identical |
| `sentinel_os/production_harness.py` | GSA-815 | diverged |
| `sentinel_os/ivr-events-ingestion-contract.diff` | (none) | unique |
| `sentinel_os/test_sentinel_worker.py` | sentinel_os | diverged |
| `sentinel_os/test_perceive_consolidated.py` | observe-perceive | identical |
| `sentinel_os/_common.lua.txt` | (none) | unique |
| `sentinel_os/twin-plus-redteam.bundle` | (none) | unique |
| `sentinel_os/structure.txt` | (none) | unique |
| `sentinel_os/test_circuit_breaker.py` | sentinel_os | identical |
| `sentinel_os/requirements.txt` | sentinel_os | diverged |
| `sentinel_os/chaos_metrics_run2.json` | (none) | unique |
| `sentinel_os/EXECUTION_REPORT.md` | (none) | unique |
| `sentinel_os/APPLY-twin-ci-native-postgres.md` | (none) | unique |
| `sentinel_os/claude_governance_api.py` | GSA-815 | diverged |
| `sentinel_os/remove-fake-ppo-router.bundle` | (none) | unique |
| `sentinel_os/standin_claim_lua.txt` | (none) | unique |
| `sentinel_os/bisg_estimator.py` | sentinel_os | identical |
| `sentinel_os/enqueue.lua.txt` | (none) | unique |
| `sentinel_os/APPLY-wire-correlation-proxy-into-rollup (1).md` | (none) | unique |
| `sentinel_os/h4-snapshot-forgery.bundle` | (none) | unique |
| `sentinel_os/sentinel_os_patch_v1.diff` | (none) | unique |
| `sentinel_os/APPLY-1.md` | (none) | unique |
| `sentinel_os/test_compliance_exporters.py` | observe-perceive | identical |
| `sentinel_os/cassette_capabilities.py` | sentinel_os | diverged |
| `sentinel_os/cassette-kernel-capability-split.bundle` | (none) | unique |
| `sentinel_os/compliance_exporters.py` | observe-perceive | identical |
| `sentinel_os/production_config.yaml` | sentinel_os | identical |
| `sentinel_os/obligation_sweep.py` | sentinel_os | diverged |
| `sentinel_os/test_observe_consolidated.py` | observe-perceive | identical |
| `sentinel_os/CONSOLIDATION_ANALYSIS_COMPLETE.md` | (none) | unique |
| `sentinel_os/OBSERVE_PERCEIVE_Orientation.pptx` | (none) | unique |
| `sentinel_os/circuit_breaker.py` | sentinel_os | identical |
| `sentinel_os/runtime-user-fix-files.tar.gz` | (none) | unique |
| `sentinel_os/test_integration_consolidated.py` | observe-perceive | identical |
| `sentinel_os/sentinel_os_patch_v1-2.diff` | (none) | unique |
| `sentinel_os/twin_attestation_spec_v1-1.md` | (none) | unique |
| `sentinel_os/cassette_interface.py` | sentinel_os | diverged |
| `sentinel_os/02-COMPLIANCE.commitmsg.txt` | (none) | unique |
| `sentinel_os/01-AUDIT_PLAYBOOK.commitmsg.txt` | (none) | unique |
| `sentinel_os/clinical_governance_system.py` | observe-perceive | identical |
| `sentinel_os/pytest.ini.txt` | (none) | unique |
| `sentinel_os/dashboard.html` | (none) | unique |
| `sentinel_os/iceberg_complete_simulator.py` | GSA-815 | diverged |
| `sentinel_os/c2-finding-2-correlation-mitigation.bundle` | (none) | unique |
| `sentinel_os/sentinel_worker_verification_report_v1.md` | (none) | unique |
| `sentinel_os/cohort-assembly-combined.diff` | (none) | unique |
| `sentinel_os/requeue_dead.lua.txt` | (none) | unique |
| `sentinel_os/sentinel-phase2-files.tar.gz` | (none) | unique |
| `sentinel_os/twin_custody.py` | sentinel_os | diverged |
| `sentinel_os/cage_match_report_v1.md` | (none) | unique |
| `sentinel_os/chaos_metrics_run3.json` | (none) | unique |
| `sentinel_os/test_twin_live.py` | sentinel_os | diverged |
| `sentinel_os/queue_schema_standin.py` | (none) | unique |
| `sentinel_os/test_queue_schema.py` | sentinel_os | diverged |
| `sentinel_os/README.md` | sentinel_os | diverged |
| `sentinel_os/kalman_trajectory.py` | observe-perceive | identical |
| `sentinel_os/test_twin_snapshot_forgery.py` | sentinel_os | identical |
| `sentinel_os/test_twin_custody.py` | sentinel_os | identical |
| `sentinel_os/load_test.py` | sentinel_os | identical |
| `sentinel_os/set_ledger_reader_password.py` | sentinel_os | identical |
| `sentinel_os/api_server.py` | (none) | unique |
| `sentinel_os/test_api_server_v2.py` | sentinel_os | diverged |
| `sentinel_os/redteam-fixes.bundle` | (none) | unique |
| `sentinel_os/sealed_demographic_channel.py` | sentinel_os | diverged |
| `sentinel_os/twin_w_reconciliation_v1-1.md` | (none) | unique |
| `sentinel_os/standin_ack_lua.txt` | (none) | unique |
| `sentinel_os/api_key_auth.py` | sentinel_os | identical |
| `sentinel_os/APPLY-wire-correlation-proxy-into-rollup.md` | (none) | unique |
| `sentinel_os/constellation_module.py` | (none) | unique |
| `sentinel_os/APPLY.md` | (none) | unique |
| `sentinel_os/telemetry_pipeline.py` | GSA-815 | identical |
| `sentinel_os/cross-lens-tier-conflict-wiring.bundle` | (none) | unique |
| `sentinel_os/standin_fail_lua.txt` | (none) | unique |
| `sentinel_os/APPLY_v1-01.md` | (none) | unique |
| `sentinel_os/ledger_immutability.sql` | sentinel_os | identical |
| `sentinel_os/docker-compose.yml` | sentinel_os | diverged |
| `sentinel_os/load_test_config.py` | sentinel_os | identical |
| `sentinel_os/queue_schema.py` | sentinel_os | identical |
| `sentinel_os/perceive_consolidated.py` | observe-perceive | identical |
| `sentinel_os/DEPLOYMENT.md` | sentinel_os | diverged |
| `sentinel_os/sentinel_worker.py` | sentinel_os | diverged |
| `sentinel_os/twin_custodian.py` | sentinel_os | identical |
| `sentinel_os/Dockerfile` | sentinel_os | diverged |
| `sentinel_os/the-twin.bundle` | (none) | unique |
| `sentinel_os/metrics_prometheus.py` | GSA-815 | identical |
| `sentinel_os/.gitignore` | sentinel_os | diverged |
| `sentinel_os/readme-staleness-pass-2.bundle` | (none) | unique |
| `sentinel_os/_.gitignore` | (none) | unique |
| `sentinel_os/GSA.py` | (none) | unique |
| `sentinel_os/api_server_resilient.py` | GSA-815 | identical |
| `sentinel_os/MODEL_CARD.md` | sentinel_os | diverged |
| `sentinel_os/api_server_v2.py` | sentinel_os | diverged |
| `sentinel_os/AC13_twin_endpoint_auth_v1.bundle` | (none) | unique |
| `sentinel_os/chaos_metrics_run3-1.json` | (none) | unique |
| `sentinel_os/wire-correlation-proxy-into-rollup (1).bundle` | (none) | unique |
| `sentinel_os/ascent_compute_module.py` | (none) | unique |
| `sentinel_os/standin_heartbeat_lua.txt` | (none) | unique |
| `sentinel_os/roadster_breakers_verification_report_v1.md` | sentinel_os | identical |
| `sentinel_os/README.txt` | (none) | unique |
| `sentinel_os/ledger-boot-and-ci-gates.bundle` | (none) | unique |
| `sentinel_os/COMPLIANCE.md` | sentinel_os | diverged |
| `sentinel_os/twin_detector.py` | sentinel_os | identical |
| `sentinel_os/twin_verification_report_v1-1.md` | (none) | unique |
| `sentinel_os/api_server_v2_verification_report_v1.md` | (none) | unique |
| `sentinel_os/regulatory-cassette-framework.bundle` | (none) | unique |
| `sentinel_os/README_CONSOLIDATED.md` | (none) | unique |
| `sentinel_os/queue_contract_v1.md` | (none) | unique |
| `sentinel_os/canonical_fields.py` | sentinel_os | diverged |
| `sentinel_os/c2-input-side-checkers-1.bundle` | (none) | unique |
| `sentinel_os/twin-live-infra.bundle` | (none) | unique |
| `sentinel_os/governance_contracts.py` | observe-perceive | identical |
| `sentinel_os/APPLY-cross-lens-tier-conflict-wiring.md` | (none) | unique |
| `sentinel_os/observe_perceive_core.py` | GSA-815 | identical |
| `sentinel_os/test_clinical_governance_system.py` | observe-perceive | identical |
| `sentinel_os/remove-dead-callerintent-enum.bundle` | (none) | unique |
| `sentinel_os/standin_enqueue_lua.txt` | (none) | unique |
| `sentinel_os/test_production_harness_breakers.py` | (none) | unique |
| `sentinel_os/fail.lua.txt` | (none) | unique |
| `sentinel_os/rate_limiter_v2.py` | sentinel_os | identical |
| `sentinel_os/cassette-load-time-binding.bundle` | (none) | unique |
| `sentinel_os/sentinel_soc_module.py` | (none) | unique |
| `sentinel_os/sealanes_module.py` | (none) | unique |
| `sentinel_os/grafana_dashboard.py` | GSA-815 | identical |
| `sentinel_os/test_grafts.py` | sentinel_os | identical |
| `sentinel_os/queue_staffing_bayes_integration.py` | GSA-815 | identical |
| `sentinel_os/APPLY-twin-live-infra.md` | (none) | unique |
| `sentinel_os/reap.lua.txt` | (none) | unique |
| `sentinel_os/chaos_metrics_run1.json` | (none) | unique |
| `sentinel_os/standin_reap_expired_lua.txt` | (none) | unique |
| `sentinel_os/APPLY-ledger-boot-and-ci-gates.md` | (none) | unique |
| `sentinel_os/transmission_verification_report_v1.md` | (none) | unique |
| `sentinel_os/cassette_schema.py` | sentinel_os | diverged |
| `sentinel_os/docs-remaining-modules.bundle` | (none) | unique |
| `sentinel_os/APPLY-3.md` | (none) | unique |
| `sentinel_os/roadster_final_pieces.bundle.txt` | (none) | unique |
| `sentinel_os/cassette_loader.py` | sentinel_os | identical |
| `sentinel_os/smoke_test.sh` | sentinel_os | identical |
| `sentinel_os/sentinel-phase2.bundle` | (none) | unique |
| `sentinel_os/twin_verification_report_v1.md` | sentinel_os | identical |
| `sentinel_os/regulatory_checks.py` | sentinel_os | diverged |
| `sentinel_os/load_test_live.py` | sentinel_os | identical |
| `sentinel_os/outcome_v1.py` | sentinel_os | diverged |
| `sentinel_os/.env.example` | sentinel_os | identical |
| `sentinel_os/governor_injection_defense.py` | sentinel_os | diverged |
| `sentinel_os/sentinel_core.py` | GSA-815 | diverged |
| `sentinel_os/gallm_coordinator.py` | (none) | unique |
| `sentinel_os/twilio_log_ingestion.py` | GSA-815 | diverged |
| `sentinel_os/regulatory_deck.py` | sentinel_os | identical |
| `sentinel_os/chaos_metrics_run1-1.json` | (none) | unique |
| `sentinel_os/APPLY_v1.md` | (none) | unique |
| `sentinel_os/array_ops.py` | sentinel_os | identical |
| `sentinel_os/APPLY-wire-correlation-proxy-into-rollup-1.md` | (none) | unique |
| `sentinel_os/cassette_harness.py` | GSA-815 | identical |
| `sentinel_os/docker-race-fix.bundle` | (none) | unique |
| `sentinel_os/recommendation_impact.py` | sentinel_os | diverged |
| `sentinel_os/test_queue_identity_converter.py` | sentinel_os | diverged |
| `sentinel_os/twin_shipper.py` | sentinel_os | identical |
| `sentinel_os/sentinel-os-lowhanging-fruit.bundle` | (none) | unique |
| `sentinel_os/APPLY_v2.md` | (none) | unique |
| `sentinel_os/GSA_Governance_Operating_Core_Enterprise.py` | (none) | unique |
| `sentinel_os/reserve_control.py` | observe-perceive | identical |
| `sentinel_os/APPLY-docs-remaining-modules.md` | (none) | unique |
| `sentinel_os/start_production.sh` | sentinel_os | identical |
| `sentinel_os/episode.py` | sentinel_os | identical |
| `sentinel_os/APPLY-cross-lens-tier-conflict-wiring-1.md` | (none) | unique |
| `sentinel_os/twin_probe.py` | sentinel_os | identical |
| `sentinel_os/twin_w_reconciliation_v1.md` | sentinel_os | identical |
| `sentinel_os/twin_attestation_spec_v1.md` | sentinel_os | identical |
| `sentinel_os/conftest.py` | sentinel_os | identical |
| `sentinel_os/twin_sync_worker.py` | sentinel_os | identical |
| `sentinel_os/APPLY_ivr-events.md` | (none) | unique |
| `sentinel_os/cross-lens-tier-conflict-wiring-1.bundle.txt` | (none) | unique |
| `sentinel_os/ack.lua.txt` | (none) | unique |
| `sentinel_os/gitignore-certs-fix.bundle` | (none) | unique |
| `sentinel_os/APPLY-c2-finding-2-correlation-mitigation.md` | (none) | unique |
| `sentinel_os/docker-fix.bundle` | (none) | unique |
| `sentinel_os/docs-scrub.bundle` | (none) | unique |
| `sentinel_os/twin_receiver.py` | sentinel_os | identical |
| `sentinel_os/standin_promote_due_lua.txt` | (none) | unique |
| `sentinel_os/operational_resilience.py` | sentinel_os | identical |
| `sentinel_os/cassette_forensics.py` | sentinel_os | diverged |
| `sentinel_os/regulatory_cassette_interface.py` | sentinel_os | diverged |
| `sentinel_os/obligation_supersession.py` | sentinel_os | diverged |
| `sentinel_os/api_server_v2_verification_report_v1-1.md` | (none) | unique |
| `sentinel_os/capacity_planning.py` | observe-perceive | identical |
| `sentinel_os/wire-correlation-proxy-into-rollup-1.bundle.txt` | (none) | unique |
| `sentinel_os/runtime-user-fix.bundle` | (none) | unique |
| `sentinel_os/c2-input-side-checkers.bundle` | (none) | unique |
| `sentinel_os/test_rate_limiter_v2.py` | sentinel_os | identical |
| `sentinel_os/transmission_unified_v1.zip` | (none) | unique |
| `sentinel_os/PHASE2_MIGRATION_NOTES.md` | sentinel_os | identical |
| `sentinel_os/eventv1-outcomev1.bundle` | (none) | unique |
| `sentinel_os/twin-ci-native-postgres.bundle` | (none) | unique |
| `sentinel_os/twin_failure_taxonomy_v1.md` | sentinel_os | identical |
| `sentinel_os/wire-correlation-proxy-into-rollup.bundle` | (none) | unique |
| `sentinel_os/AUDIT_PLAYBOOK.md` | sentinel_os | diverged |
| `sentinel_os/Tests/test_bayes_learning_loop.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_resilience_observability.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_graph_integrity.py` | (none) | unique |
| `sentinel_os/Tests/test_twin_cohort_reviews.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_rl_governance_integration.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_intent_classification_audit.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_bisg_estimator_live.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_cassette_source_of_truth.py` | (none) | unique |
| `sentinel_os/Tests/test_sealed_demographic_channel.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_recommendation_impact.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_live_path_kernel_wiring.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_obligation_sweep.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_ai_cost_ledger.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_phase2_limitations.py` | (none) | unique |
| `sentinel_os/Tests/test_api_key_auth.py` | (none) | unique |
| `sentinel_os/Tests/test_c2_statistical_outcome_equity.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_gallm.py` | (none) | unique |
| `sentinel_os/Tests/test_system_readiness.py` | (none) | unique |
| `sentinel_os/Tests/test_ai_cost_wiring.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_governance_cassettes.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_cassette_governs_every_decision.py` | (none) | unique |
| `sentinel_os/Tests/test_bisg_estimator.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_twin_outcome_obligations.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_twilio_cassette_thresholds.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_event_v1.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_recommendation_impact_integration.py` | (none) | unique |
| `sentinel_os/Tests/test_regulatory_cassettes.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_governor_failclosed.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_domain_from_cassette_version.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_c2_correlation_based_proxy_detection.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_outcome_v1.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_ai_cost_end_to_end.py` | (none) | unique |
| `sentinel_os/Tests/test_c2_geographic_outcome_equity.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_mortgage_cassette.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_e2e_adaptive.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_tls_security.py` | (none) | unique |
| `sentinel_os/Tests/test_production_integration.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_rl_learning.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_ivr_events_contract.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_c2_input_side_checkers.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_ledger_boot_lock.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_observe_perceive.py` | (none) | unique |
| `sentinel_os/Tests/test_twin_receiver_auth.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_sentinel.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_cassette_system.py` | (none) | unique |
| `sentinel_os/Tests/test_episode.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_observe_perceive_fix.py` | (none) | unique |
| `sentinel_os/Tests/test_telemetry_pipeline.py` | GSA-815 | identical |
| `sentinel_os/Tests/test_outcome_chain_records.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_ai_cost_tracking.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_remaining_edge_cases.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_all_suites.py` | (none) | unique |
| `sentinel_os/Tests/test_cassette_capabilities.py` | (none) | unique |
| `sentinel_os/Tests/conftest.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_obligation_supersession.py` | sentinel_os | diverged |
| `sentinel_os/Tests/test_cassette_snapshot_forensics.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_twilio_to_adaptive.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_recommendation_shadow_ledger.py` | sentinel_os | identical |
| `sentinel_os/Tests/test_critical_integration.py` | sentinel_os | identical |
| `sentinel_os/k8s/deployment.yaml` | GSA-815 | diverged |
| `sentinel_os/k8s/secret.yaml.example` | GSA-815 | diverged |
| `sentinel_os/k8s/pvc.yaml` | GSA-815 | identical |
| `sentinel_os/k8s/service.yaml` | GSA-815 | identical |
| `sentinel_os/lua/fail.lua` | sentinel_os | identical |
| `sentinel_os/lua/ack.lua` | sentinel_os | identical |
| `sentinel_os/lua/_common.lua` | sentinel_os | identical |
| `sentinel_os/lua/reap.lua` | sentinel_os | identical |
| `sentinel_os/lua/requeue_dead.lua` | sentinel_os | identical |
| `sentinel_os/lua/heartbeat.lua` | sentinel_os | identical |
| `sentinel_os/lua/rate_limit.lua` | sentinel_os | identical |
| `sentinel_os/lua/enqueue.lua` | sentinel_os | identical |
| `sentinel_os/lua/claim.lua` | sentinel_os | identical |
| `sentinel_os/lua/promote_due.lua` | sentinel_os | identical |
| `sentinel_os/governance/ledger_postgres.py` | sentinel_os | diverged |
| `sentinel_os/governance/self_heal_v1.py` | sentinel_os | identical |
| `sentinel_os/governance/README.md` | sentinel_os | identical |
| `sentinel_os/governance/log_rotation_v1.py` | sentinel_os | identical |
| `sentinel_os/governance/recommend_v1.py` | sentinel_os | identical |
| `sentinel_os/governance/friction_core.py` | sentinel_os | identical |
| `sentinel_os/governance/drift_core_v1.py` | sentinel_os | identical |
| `sentinel_os/Latent/LatentPayload.py` | GSA-815 | identical |
| `sentinel_os/observe/TwilioSyntheticLogGenerator.py` | GSA-815 | identical |
| `sentinel_os/observe/README.md` | GSA-815 | identical |
| `sentinel_os/observe/IngestAdapter.py` | GSA-815 | identical |
| `sentinel_os/Model/Build_Graph.py` | GSA-815 | identical |
| `sentinel_os/Model/README.md` | GSA-815 | identical |
| `sentinel_os/regulatory_cassettes/cfpb_reg_b.py` | sentinel_os | identical |
| `sentinel_os/regulatory_cassettes/__init__.py` | sentinel_os | identical |
| `sentinel_os/regulatory_cassettes/README.md` | sentinel_os | identical |
| `sentinel_os/scripts/twin_ensure_services.sh` | sentinel_os | identical |
| `sentinel_os/Domain/QueueState.py` | GSA-815 | identical |
| `sentinel_os/Domain/CallerState.py` | GSA-815 | identical |
| `sentinel_os/Domain/README.md` | GSA-815 | identical |
| `sentinel_os/Domain/Intent.py` | GSA-815 | identical |
| `sentinel_os/Domain/Emotion.py` | GSA-815 | identical |
| `sentinel_os/Training/curriculum.md` | GSA-815 | identical |
| `sentinel_os/Deploy/argocd/application.yaml` | (none) | unique |
| `sentinel_os/Deploy/k8s/hpa.yaml` | (none) | unique |
| `sentinel_os/Deploy/k8s/ingress.yaml` | (none) | unique |
| `sentinel_os/Deploy/k8s/pdb.yaml` | (none) | unique |
| `sentinel_os/Deploy/k8s/kustomization.yaml` | (none) | unique |
| `sentinel_os/cassettes/__init__.py` | sentinel_os | identical |
| `sentinel_os/cassettes/README.md` | sentinel_os | identical |
| `sentinel_os/cassettes/mortgage_cassette.py` | sentinel_os | diverged |
| `sentinel_os/cassettes/banking_cassette.py` | sentinel_os | diverged |
| `sentinel_os/cassettes/ivr_cassette.py` | sentinel_os | diverged |
| `sentinel_os/Engines/README.md` | GSA-815 | identical |
| `sentinel_os/Engines/simple_rl_trainer.py` | GSA-815 | diverged |
| `sentinel_os/Sim/README.md` | GSA-815 | identical |
| `sentinel_os/Sim/cluster_runner.py` | GSA-815 | identical |
| `sentinel_os/Sim/Simulator.py` | GSA-815 | identical |
| `sentinel_os/archive/run_adaptive.py` | sentinel_os | identical |
