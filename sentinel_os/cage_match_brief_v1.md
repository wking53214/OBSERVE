# Cage Match Brief: queue_schema Original vs. Contract Rebuild

## Purpose

Two working implementations of the transmission queue exist, built in separate sessions with no contact between them. Before either becomes the permanent foundation for the roadster, they compete under identical, previously-established test conditions — settled by evidence, not by which one arrived first.

## Background

Fighter O is the original: built and chaos-verified in the transmission session (real Redis, SIGKILL, kill -9). Fighter R is a rebuild: produced in the api_server_v2 session, which never had access to Fighter O and worked entirely from the written queue contract to build something for the ingress to run against. Reconciliation after the fact found the two are compatible in intent but incompatible at the wire level — different constructor keyword, different enqueue return shape, and each has methods the other lacks. Neither has been proven better, only different. This match settles it.

## Fighters & Chain of Custody

Before anything else runs: re-hash every file in the match kit (sha256, first 12 hex chars) and confirm against this table. A mismatch means a file was corrupted or substituted in transit — stop and report, don't proceed.

**Fighter O — "Original" (transmission session, chaos-verified)**

| file | sha256 (12) |
|---|---|
| queue_schema.py | `133efa2aec16` |
| lua/_common.lua | `54d9b3e8a0ff` |
| lua/enqueue.lua | `8f9ad9fb5470` |
| lua/claim.lua | `97f63637c331` |
| lua/ack.lua | `f8907fe8ed1c` |
| lua/fail.lua | `2af50c2a03cd` |
| lua/reap.lua | `f58a45b79f59` |
| lua/requeue_dead.lua | `b83a03b4dea5` |

**Fighter R — "Rebuild" (api_server_v2 session, contract-only)**

| file | sha256 (12) |
|---|---|
| queue_schema_standin.py | `7674d897eb10` |
| lua/enqueue.lua | `9a5f007fadcd` |
| lua/promote_due.lua | `98e96dd57de6` |
| lua/claim.lua | `2eef88ff7b8c` |
| lua/heartbeat.lua | `46defac2fc40` |
| lua/ack.lua | `182e3008a973` |
| lua/fail.lua | `aa217311028c` |
| lua/reap_expired.lua | `958fb658be5d` |

## Match Kit — 21 Files, Placement

Fighter O and Fighter R must run from **separate directories**, each with its own sibling `lua/` folder. Both loaders resolve scripts relative to their own file's location, and the two fighters use different script names for equivalent operations (O's `reap.lua` vs. R's `reap_expired.lua`) — they cannot share one `lua/` directory without collision.

```
cage_match/
  fighter_o/
    queue_schema.py
    lua/
      _common.lua        ← from _common_lua.txt
      enqueue.lua         ← from enqueue_lua.txt
      claim.lua           ← from claim_lua.txt
      ack.lua              ← from ack_lua.txt
      fail.lua             ← from fail_lua.txt
      reap.lua             ← from reap_lua.txt
      requeue_dead.lua     ← from requeue_dead_lua.txt
  fighter_r/
    queue_schema_standin.py
    lua/
      enqueue.lua          ← from standin_enqueue_lua.txt
      promote_due.lua      ← from standin_promote_due_lua.txt
      claim.lua            ← from standin_claim_lua.txt
      heartbeat.lua        ← from standin_heartbeat_lua.txt
      ack.lua              ← from standin_ack_lua.txt
      fail.lua             ← from standin_fail_lua.txt
      reap_expired.lua     ← from standin_reap_expired_lua.txt
  adapter.py                (built fresh this session — see Rule 5)
  test_queue_schema.py       (Round 1 — Fighter O's native suite, 18 tests)
  sentinel_worker.py
  test_sentinel_worker.py    (Round 3 — worker suite, 8 tests)
  api_server_v2.py
  test_api_server_v2.py      (Round 2 — ingress suite, 31 tests)
```

## Weigh-In: Known Differences Going In

Declared before any round runs, so the match doesn't "discover" these as if they were new findings — they're disclosed up front to keep the scoring honest.

**Fighter R has, Fighter O lacks:** `get_job`, `ping`, `heartbeat` (lease renewal — O has *no* lease-renewal mechanism at all; an O lease can only expire, never be extended), `promote_due` as a distinct op, `flush_namespace`, `namespace=` constructor kwarg, dict-shaped `enqueue` return, `claim_token` kwargs on ack/fail.

**Fighter O has, Fighter R lacks:** `requeue_from_dlq`, `dlq_peek`, `dlq_rate`, `error_trail`, `verify_invariants` (self-audit), `classify_exception`, `close`, shared `_common.lua` guard logic, `requeue_dead` op.

These are disclosures, not findings. A round is never scored as a loss for either fighter lacking machinery this brief already knows it lacks.

## Rules, Declared Before the Bell

1. **Invariant violation = knockout.** A lost job, a double-claim, incorrect accounting, or a dishonest failure state (reporting success when nothing happened, or vice versa) ends that fighter's round as a loss, regardless of anything else in the round.
2. **Speed is observed, never decisive.** Throughput/latency differences go in the match report. They never determine a round's winner.
3. **Ties favor the original.** If both fighters survive a round clean, it's a tie. If the full match ties, Fighter O's write path is canonical for the merge — longer verification lineage (chaos-tested with real SIGKILL/kill-9, not contract-tested).
4. **One-sided machinery is a capability difference, not a failure.** Per the weigh-in above — a scenario only Fighter R's heartbeat or only Fighter O's DLQ replay can satisfy is scored as "R has this, O doesn't" (or the reverse), never as a knockout.
5. **The adapter translates dialect, never behavior.** It may rename methods/kwargs and reshape return values (tuple ↔ dict) so both fighters can be driven by the same scenarios. If a scenario can't be translated without changing what's actually being tested, report it in the match report as a structural difference — don't silently skip it, and don't silently resolve it in either fighter's favor.

## Rounds

**Round 1 — Transmission chaos** (native suite, both fighters, 18 scenarios). Worker SIGKILL mid-job; kill -9 Redis with jobs in flight; concurrent claim storm; burst accounting under load; retry/DLQ semantics; recovery from queue state alone after a crash.

**Round 2 — Ingress live fire** (api_server_v2's suite, both fighters via adapter, 31 scenarios). Garbage/malformed-input storm; frozen Redis; a stuck job; instant-poll immediately after submit; concurrent resubmission of the same call sid.

**Round 3 — Worker integration** (sentinel_worker's suite, both fighters via adapter, 8 scenarios). Full worker suite, including the crash-between-ledger-commit-and-ack window — the scenario proving a job is recorded exactly once even when the worker dies at the worst possible instant.

## After the Bell: Capability Manifest & Merge

Regardless of round outcomes, produce a complete two-directional capability manifest: every method, behavior, and safeguard each fighter has that the other lacks. Build the unified `queue_schema.py` from the round-winner's write path (Fighter O's, on a full tie) and graft every item on the loser's side of the manifest onto it. Every grafted capability gets its **own new test** — grafting the heartbeat, for instance, needs a test proving lease renewal actually extends a live claim under the winner's locking scheme, not just that the method exists and returns.

**Zero semantic changes to the winning write path.** The graft adds capability; it does not alter how the winner already handles claim/ack/fail/reap.

## Gate

Done when the unified file passes all three suites green, from a fresh clone, on the Chromebook:

- Transmission: 18/18
- Worker: 8/8
- Ingress: 31/31

## Deliverables

1. Unified `queue_schema.py` + `lua/` (one directory, replaces both fighters)
2. A **complete** queue contract document — the gap between what the contract said and what Fighter R had to invent from it is the root cause of this whole fork; closing that gap matters as much as the code merge
3. `cage_match_report_v1.md` — fighter hashes (confirming arrival integrity), per-round results with reasoning, the full capability manifest, and exactly what was grafted and why

## Fallback

If Fighter R's files are unrecoverable at match time (container recycled, etc.), abandon the match and default to Option A: add Fighter O's missing read-side methods (`get_job`, `ping`) directly, and adjust the ingress's submit-response handling to match Fighter O's native return shape. The chaos-verified write path stays canonical either way.
