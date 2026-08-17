# Cage Match Report v1 — Transmission Queue Reconciliation

**Match:** Fighter O (original `queue_schema.py`, chaos-verified lineage) vs Fighter R (rebuild `queue_schema_standin.py`, ingress lineage), per `cage_match_brief_v1.md`.
**Referee environment:** Ubuntu 24 container · Python 3.12.3 · pytest 9.1.1 · redis-py 8.0.1 · **real Redis 7.0.15** (apt) · **real PostgreSQL 16** (apt) · real SIGKILL/SIGSTOP throughout. No fakeredis, no mocks of Redis or Postgres anywhere.
**Date:** 2026-07-17.

---

## 1. Chain of custody

All 16 fighter files re-hashed on receipt (sha256, first 12 hex) and **all 16 matched the brief's tables exactly**. The copies placed in each round's ring were re-hashed after placement and remained byte-identical: Fighter O engine `133efa2aec16` and Fighter R engine `7674d897eb10` in every ring where each fought. No fighter file was modified at any point in the match. Neither fighter saw the other's code; each ran against the suites through its own interface or through a documented adapter.

## 2. Arena equipment (full disclosure)

Three suite dependencies are external project modules that were not part of the 21-file kit. Stand-ins were built as **shared arena equipment — byte-identical for both fighters**, so no fairness asymmetry exists:

| Stand-in | Why needed | Hash |
|---|---|---|
| `production_harness.py` | Round 3's suite imports the Iceberg harness (parse → sid dedup → governance gate → fail-closed governor → ledger commit, against real Postgres). Behavior implemented exactly to the contract the worker suite and verification report document. | `5077cd779838` |
| `operational_resilience.py` | `setup_logging` with the project's `extra_data` convention. | `1cb96305b496` |
| `api_key_auth.py` | Round 2's L13 auth-seam test (401 missing key / 403 wrong key / pass on valid). | `1b4b7eb82ad2` |

**Standing caveat:** Round 3's ledger behavior was proven against this stand-in harness, not your real `production_harness.py`. The final gate on your Chromebook against the real harness remains your step.

**Adapters (Rule 5).** Each fighter fought on the other's turf through one adapter that renames methods/kwargs and reshapes returns — never changes behavior:
- **Adapter A** (`adapter_o_as_r.py`, `9bdc74a56b9e`): O's engine behind R's dialect, for Round 2. Pre-declared structural limits, stated *before* the round ran: O deletes the job record on ack (no "done" view possible; post-completion resubmit creates a new job), O discards ack results, O has no lease renewal. Jitter set to 0 because R's dialect declares deterministic backoff.
- **Adapter B** (`adapter_r_as_o.py`, `19aa4393a12e`): R's engine behind O's dialect, for Rounds 1 and 3. Missing machinery **raises a loud `CapabilityGap`** rather than faking an answer; counters R doesn't keep are absent, never fabricated. Borrowed interface vocabulary (Reason/Outcome/ClaimedJob enums and the pure `classify_exception` mapping) is flagged; the manifest still credits it to O. R's reap counts are reshaped into id lists by snapshotting the expired candidates immediately before the atomic reap (exact under the suites' no-concurrent-claimer reap calls; documented).

**Protocol notes:** suites were executed in chunks (each pytest invocation re-creates its session fixtures — fresh Redis/uvicorn per chunk; tests are namespace-isolated so this is sound). One environmental flake: R's native L11 `/health` latency probe failed once under container CPU contention and passed cleanly twice on re-run; scored pass with this footnote.

---

## 3. Round 1 — Transmission chaos (native suite, 18 scenarios)

**Fighter O (native): 18/18 in 7.9s.** Burst: 12,311 enqueue/s, 4,135 claim+ack/s across 8 workers. Real `kill -9` of workers and of Redis itself, zero loss, zero duplicates, invariant sweeps clean.

**Fighter R (via Adapter B): 3/18 verbatim** (FIFO order, ack-retry-safe, broker-unreachable-fails-loud). Referee autopsy of all 15 failures, by failure point:

| Class | Scenarios | Finding |
|---|---|---|
| Core semantics **passed in-test**, died at O-only machinery assertion | happy path, storm (2000 jobs × 12 workers, **zero double-claims verified before death**), retry/backoff (exact 100/200 ms, full trail, correct DLQ), non-retryable immediate DLQ, worker SIGKILL recovery (reap → trail → redelivery attempt 2 → completion), stale-worker fencing (zombie ack **and** fail both fenced), crash-loop budget, stats depth/staleness | 8 scenarios where R's queue behavior was correct; the kill shot was `verify_invariants`, lifetime counters, or the escalate flag — machinery R does not have |
| Blocked before the core claim could be checked → **referee probes** | idempotent depth, Redis kill-9 zero-loss, burst exact accounting | All three probes **PASS**: kill -9 with 70 pending + 10 in-flight → 0 lost, 10 reaped, 100/100 completed, 0 duplicate deliveries; 5,000-job burst → 0 lost, 0 duplicated (8,816 enq/s, 2,554 drain/s) |
| Scenario's subject **is** the missing machinery | escalate flag, corrupted-payload quarantine (R delivered a tampered payload — no checksum), DLQ replay (`requeue_from_dlq`, declared at weigh-in), dangling-reference quarantine (R's claim **crashes with a KeyError** on a ghost id and manufactures a phantom record — loud, no real job lost, but a genuine robustness defect) | 4 capability gaps; 2 were declared at the weigh-in, 2 (escalate, checksum quarantine — plus orphan quarantine and lifetime counters) are **new findings not declared at the weigh-in** |

**Rule 1 check: zero knockouts.** R never lost a job, never double-claimed, never mis-accounted, never reported a dishonest state — every failure was loud.
**Verdict: Round 1 to Fighter O** — clean sweep on native turf; R's unexcused (undeclared) gaps decide it, not any invariant breach.

## 4. Round 2 — Ingress live fire (31 scenarios, real uvicorn + real drainer)

**Fighter R (native): 31/31** (L11 flake footnote above). Full trajectories, retry visibility at every hop, dead-job views, concurrent-resubmit idempotency, garbage storm, stuck-job non-blocking, frozen-Redis honest 503s with alive `/health`, auth seam, throughput floor.

**Fighter O (via Adapter A): 27/31.** All four failures — L01 (done view), L02 (done hop of retry trajectory), L06 (resubmit **after** completion re-runs instead of deduping), L10 (polling 40 completed jobs) — share **one root cause, pre-declared before the round**: O deletes the job record on ack, so "done" is unobservable and the idempotency window ends at completion. Notably O passed the frozen-Redis chaos, the concurrency proof, the stuck-job flow itself, and the full pending→processing trajectory views through the adapter.

Rule 1 check: no knockout — at the queue layer O's model is self-consistent and honest (at-least-once, ledger dedups); the failures are a contract mismatch with the ingress, not corruption. The match's headline engineering finding: **the weigh-in under-declared this gap.** It listed `get_job` as merely absent; the rounds prove `get_job` alone is ungraftable without a completion record — the real difference was the delete-on-ack *policy*.
**Verdict: Round 2 to Fighter R.**

## 5. Round 3 — Worker integration (8 scenarios, real Postgres ledger)

**Fighter O (native): 8/8. Fighter R (via Adapter B): 8/8.** Both fighters proved the scenario this whole architecture exists for: worker crashes **between ledger commit and ack** → job redelivered → `duplicate_sid` detected against the real Postgres ledger → redelivery acked → **exactly one ledger row**, plus the fail-closed no-API-key path, `ledger_write_failed` never swallowed, DLQ diagnosis for unparseable calls, and 25 jobs across 4 concurrent workers with zero duplicate rows.
**Verdict: Round 3 tied — clean.**

## 6. Match verdict

Round 1 → O. Round 2 → R. Round 3 → tie. **Full match: tie.** Zero Rule-1 knockouts by either fighter in any round — both engines keep the promises that matter. Per Rule 3, **Fighter O's write path is canonical for the merge** (longer verification lineage). The rounds show a perfect mirror: each fighter was built against one end of the pipe and dominated that end; the wire-level fork was the real defect, exactly as the brief suspected.

## 7. Capability manifest

**O-only (all retained in the unified build):** payload checksum quarantine at claim; orphan/dangling-reference quarantine; escalate flag on unclassified deaths; lifetime counters (enqueued, duplicate_enqueues, retries, reaped, stale_acks, stale_fails, corrupt_payloads, orphan_refs); `verify_invariants` self-audit; `requeue_from_dlq`; `dlq_peek` / `dlq_rate` / `error_trail` as first-class reads; backoff jitter; `classify_exception`; injected-client constructor mode; dead set as a time-scored zset (enables windowed DLQ rates).

**R-only (all grafted into the unified build):** `get_job` job views; **completion records** (pollable "done", persisted ack result, post-completion dedup); `heartbeat` lease renewal; `promote_due` as an explicit op; `ping`; `flush_namespace`; `namespace=` construction; claim_token-addressed ack/fail; dict-shaped enqueue/claim returns; the rebuild's reason vocabulary (`process_crash_restart`, `data_corruption_in_transit`) as a read/write bridge; rebuild operational defaults (3 attempts, 2s socket timeouts, deterministic backoff).

**Behavioral deltas reconciled:** second-ack-of-done returns GONE in both dialects (v1 contract preserved on top of retained records); fail/requeue against a done record answer GONE; R's fenced-vs-gone ambiguity resolved (the unified engine distinguishes; the rebuild dialect string-collapses both to "fenced" as its callers expect).

## 8. The merge

Base: Fighter O verbatim. **Byte-identical, untouched:** `_common.lua` (`54d9b3e8a0ff`), `claim.lua` (`97f63637c331`), `reap.lua` (`f58a45b79f59`) — the claim fence, checksum/orphan quarantine, promotion, and reaping are the original's, unchanged. **Surgically extended:** `enqueue.lua` (return enriched 0/1 → {created, live status}; state logic identical), `ack.lua` (completion now writes a TTL'd done record + `done` zset instead of `DEL`; `done_keep_ms=0` restores v1 byte-for-byte effects; fence and counters unchanged), `fail.lua` / `requeue_dead.lua` (one guard line each: done → 'gone', matching v1's deleted-hash answers). **New:** `heartbeat.lua`, `promote_due.lua` — both under the same `owner_check` fence / promotion logic as the originals. Python: one class, two constructor-selected dialect facades over one engine; the five-structure exactly-one invariant extends to `done` and the audit knows it (with retention-boundary pruning so an expiring record is never a false violation).

## 9. Gate

Fresh gate directory (unified build + all three suites + shared scaffolding), run in full:

| Suite | Result |
|---|---|
| Original chaos suite (Fighter O's 18) | **18/18** |
| Worker integration (8, real Postgres) | **8/8** |
| Ingress live fire (31, real uvicorn) | **31/31** |
| New graft suite (`test_grafts.py`, 10) | **10/10** |
| **Total** | **67/67** |

The graft suite covers: heartbeat extends a live lease and the reaper honors renewal; reaped zombies cannot heartbeat (fenced, counted); explicit promote_due; get_job across every lifecycle state; done-record views/result/dedup/GONE contract; `done_keep_ms=0` v1-restore; retention expiry; ping/flush; the full rebuild-dialect facade end-to-end; and cross-dialect single-engine/single-fence proof.

## 10. Caveats and open items

1. Round 3 ran against the arena's harness stand-in — re-run `test_sentinel_worker.py` against the real `production_harness.py` on your machine before trusting the merge in the Iceberg path.
2. Done records consume memory for `done_keep_ms` (default 24 h). Sizing: one job hash + trail per completion in the window. Tune per environment; `0` restores v1.
3. Redis Sentinel failover remains unverified, exactly as both fighters' reports already said.
4. `EnqueueResult` is a tuple/mapping hybrid so both call sites keep working; the rebuild-dialect `fail()` positional signature is serviceable but the least elegant seam in the file — both are documented in the contract.
5. The one flake observed all match (R's native L11 latency probe) was environmental; nothing else flaked in ~200 test executions.
