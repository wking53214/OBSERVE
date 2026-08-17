# Deadcode Sweep — Batch 1 (Code Removals)

## Summary
Three commits, 890 deletions across 4 files. All verified with two back-to-back full test runs (438 passed, ruff clean).

### Commits
- **76b49cd** — Remove orphaned Grafana Kubernetes ConfigMap export path (37 lines)
- **90a437b** — Remove _fallback_bounds and the governance_params it cached (18 lines)
- **ee956bd** — Remove spent cassette-snapshot-forensics patch artifact (835 lines)

## To Apply

### From patches (in order):
```bash
cd /path/to/sentinel_os
git am 0001-Remove-orphaned-Grafana-Kubernetes-ConfigMap-export-.patch
git am 0002-Remove-_fallback_bounds-and-the-governance_params-it.patch
git am 0003-Remove-spent-cassette-snapshot-forensics-patch-artif.patch
```

### From archive (if you prefer to check the branch first):
```bash
tar xzf deadcode-sweep-batch1.tar.gz
# This extracts the tree at that commit; you can inspect it before applying patches
```

## What Was Removed

### Batch 1: grafana_dashboard.py (76b49cd)
**Removed:** `export_grafana_kubernetes_configs()`, `GRAFANA_DATASOURCE_CONFIG`, `GRAFANA_DASHBOARD_CONFIG`

**Why:** No references anywhere. The two constants existed only to feed the function. The module's live surface (`GrafanaDashboard`, `generate_dashboard_json`) is untouched and still imported by `api_server_resilient.py` and tests.

### Batch 2: claude_governance_api.py + production_harness.py (90a437b)
**Removed:** 
- `ClaudeGovernanceDecider._fallback_bounds()` method
- `governance_params` parameter from `__init__`
- `self.governance_params` attribute
- `governance_params=self._params()` argument at production_harness.py:196

**Why:** The method was orphaned by the earlier Finding-2 fail-closed rewrite — every parse-failure branch now returns `lo_bound`/`hi_bound` as `None` on purpose, so the cassette-sourced fallback path was deliberately abolished. The parameter was the only reader of `self.governance_params`, which contradicted `_params()`'s own docstring (read the cassette fresh at decision time, never cached). No live defect, but a `swap_cassette` would have left the decider on an old policy. The ledger's unrelated `append_decision(..., governance_params=...)` API is untouched.

### Batch 3: sentinel_cassette_snapshot_forensics_v1.patch (ee956bd)
**Removed:** 835-line patch file

**Why:** Delivery artifact committed alongside the work it delivered. All three targets are live in the tree, and reverse-applying the patch fails — the code moved on after it landed. It was a stale near-duplicate of the real modules.

## Test Verification
- Baseline (HEAD before changes): 438 passed, 6 skipped, 4 failed (environmental)
- After batch 1: 438 passed, 6 skipped, 4 failed ✓
- After batch 2: 438 passed, 6 skipped, 4 failed ✓
- After batch 3: 438 passed, 6 skipped, 4 failed ✓

All failures are environmental (missing TLS certs, missing sentinelsvc OS identity). Ruff clean throughout.

## Notes
- The remaining four candidates from the sweep are correctly not-dead per your spec (documented stubs, API surfaces, honest gaps, capability-gated paths).
- The `.gitignore` rule fix (add `*.patch` and `*.bundle`) and stale doc references (COMPLIANCE.md, MODEL_CARD.md) are in separate commits that follow.

## Branch State
The patches are based on commit `ddbe04c` (Remove dead CallerIntent enum from sentinel_core.py). The branch `deadcode-sweep-batch1` in the sandbox contains all three commits and is ready to merge to main.
