# Upstream

OBSERVE is a downstream of three repositories, not an independent codebase.
Before 2026-09-07 it carried stale copies of their files with no record of
where they came from or when they were last synced. This file and
`VENDORED.md` are that record.

| Upstream | Path here | Synced from commit | Sync date |
| --- | --- | --- | --- |
| observe-perceive | `observe_consolidated.py`, `test_observe_consolidated.py` | `717c2e2` | 2026-09-07 |
| sentinel_os (`sentinel_os/` subtree) | `sentinel_os/` | `ddedd12` | 2026-09-07 |
| GSA-815 | `sentinel_os/` (files that live in GSA-815) | `44ee595` | 2026-09-07 |

What was tried on 2026-09-07 and what it showed:

- Syncing every diverged file from sentinel_os and GSA-815 (51 files) and
  re-running this repository's suite dropped it from 570 passed to 337
  passed: the upstream kernel has moved on to modules this snapshot does not
  carry. Those 51 files were reverted and are marked `diverged` below. They
  cannot be synced file by file; reconciling them means adopting the current
  sentinel_os kernel wholesale (the way GSA-815 does, as a submodule) and
  deleting the copy here.
- Syncing the observe-perceive-derived files inside `sentinel_os/` (the
  engine, PERCEIVE, the clinical governance system, the exporters and their
  tests, plus the modules they now import: `kalman_trajectory`,
  `reserve_control`, `capacity_planning`, `governance_contracts`) collected
  cleanly and was kept.
- The root `observe_consolidated.py` is a **two-way fork**, not a stale copy.
  It defines `compute_decision_fingerprint`, `compute_state_commitment`,
  `PARAMETER_SET`/`PARAMETER_SET_VERSION`, `REGIME_DISTRIBUTION_BANDS` and
  `_canonical_json`, which upstream does not have and which
  `test_observe_invariants.py` (this repository's own 400-line invariants
  suite) depends on. Upstream has `sanitize_context` and the context trust
  boundary, which this copy does not. Overwriting the root copy with upstream
  broke the invariants suite at import, so it was kept as is and is marked
  `diverged`. Reconciliation is upstream-first: port the fingerprint and
  state-commitment work into observe-perceive, then re-sync here.

Rules from here on:

1. A file that exists upstream is changed upstream and re-synced here, never
   edited here. `VENDORED.md` lists every such file and whether it currently
   matches.
2. A file marked `unique` in `VENDORED.md` exists only in this repository.
   209 such files were found; they are candidates for either
   upstreaming or deletion, and they are the reason this repository still
   exists as more than a fork.
3. To re-sync: check out the upstreams beside this repository and run the
   audit's sync script (copy every upstream-present file, run the suite, keep
   the result only if the suite does not regress).
