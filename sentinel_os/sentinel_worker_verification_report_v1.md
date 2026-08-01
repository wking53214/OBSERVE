# sentinel_worker.py — Verification Report v1

**Component:** Tier 2 worker — consumes the transmission, drives the real V12 harness
**Date:** July 16, 2026
**Environment:** Redis 7.0.15, Postgres 16, redis-py 8.0.1, psycopg2 2.9.x, Python 3.12.3; repo @ `87ae59a`
**Method:** 8 tests, all against **real Postgres and real Redis**, calling the **real, unmodified `IcebergProductionHarness.process_call`** — only `append_decision` is monkeypatched, and only in the one test designed to force the F-2 shape. No Claude API key configured, so governed calls exercise the harness's own documented "no governor configured" fail-closed path — a real code branch, not a stub. **8/8 passed on three consecutive clean-state runs.** A real subprocess run of the CLI entrypoint, real `SIGTERM`, exited 0.

## The one decision this file exists to get right

`process_call` mostly doesn't raise — by design, per its own comments. It **reports** ledger-write failure rather than throwing. So the worker's ack/fail decision has to be read from the *shape* of its return value, not from exception handling. Get this mapping wrong and you reintroduce exactly the bug the transmission was built to make structurally impossible.

| Result shape | Action | Why |
|---|---|---|
| `error: "duplicate_sid"` | **ACK** | Proof the dedup contract worked — see below |
| any other `error` | **FAIL, non-retryable** | Bad input; retrying won't fix it |
| `ledger_write_failed: True` | **FAIL, retryable — never ack** | The F-2 shape: a decision was made but not recorded |
| anything else (including a governor rejection) | **ACK** | Recorded, complete — a "no" is a finished job |
| harness raises | **FAIL**, reason from `classify_exception` | Defensive; harness shouldn't do this, but a worker must not treat "unknown" as success |

## Verified live

**W-1. Happy path, real ledger row.** A governed call is claimed, processed through the real harness, ledger row confirmed via `sid_exists`. An ungoverned call (below `governance_trigger`) completes with no ledger row expected, matching the harness's own gate logic.

**W-2. A governor rejection is a completed job.** With no Claude client configured, the harness's fail-closed path returns `safe=False` but **records** the decision. The worker acks it. Verified live: `sid_exists` true, `Outcome.OK`. This is the "governance_blocked=True is not a queue failure" rule, proven against a real code path.

**W-3. Bad input dead-letters clean.** A record with an unrecognized status is rejected by `TwilioLogParser` (`error: "Failed to parse call"`); the worker dead-letters it as `data_corruption`, non-retryable, and — the important negative — **confirms no ledger row was created** for it.

**W-4. The F-2 shape, forced live and recovered live.** `append_decision` is monkeypatched to raise on its first call only. Attempt 1: worker gets `ledger_write_failed=True`, calls `fail()` with `db_connection_loss`, confirms **`sid_exists` is false** (nothing was silently reported as done), confirms the job is *not* acked. After the backoff elapses, attempt 2 uses the real `append_decision` again, succeeds, and `sid_exists` becomes true — exactly once, confirmed by call count on the patched function (`calls["n"] == 2`).

**W-5. Worker crash between ledger commit and ack — the hardest case, done for real.** This one doesn't simulate the crash; it *creates* the exact state a crash would leave behind. `process_call` is invoked directly so the ledger row commits for real (`sid_exists` becomes true) — then the worker simply never acks, standing in for a process that died in that gap. After the lease expires, `reap_expired()` finds it, logs `process_crash`, and requeues it. A second worker claims it (attempt 2), calls `handle_one`, and gets `duplicate_sid` back from the harness — which it correctly treats as already-done and acks. Final check queries `get_decisions()` directly and confirms **exactly one** ledger row exists for that call_sid, not zero and not two. This is the queue's central promise (crash-safe, at-least-once-into-a-dedup) proven end-to-end through a real worker and a real ledger, not asserted from queue internals alone.

**W-6. Concurrent workers, no cross-worker duplication.** 25 jobs, 4 worker instances draining one shared queue concurrently. All 25 acked, all 25 present in the ledger via `sid_exists`, and a direct `get_decisions()` count confirms **exactly 25** rows — no duplicate writes across workers sharing one queue.

**W-7. Runs as a real process.** The CLI entrypoint (`python3 sentinel_worker.py`) was started as an actual subprocess with real env vars, processed a real enqueued job (log line confirms `outcome: ok`), received a real `SIGTERM`, logged a clean shutdown with counters (`processed: 1, acked: 1, failed: 0`), and exited **0**.

## Design notes

- **One harness per worker**, held open for the process lifetime — cassette loaded once, Postgres pool and Claude client (if configured) held open, matching how `IcebergProductionHarness` is meant to be used (not reconstructed per call).
- **Reaping runs on its own timer thread**, independent of this worker's own claim loop, so a fleet fully saturated with in-flight jobs still recovers other workers' abandoned leases instead of only reaping when idle.
- **Structured logging reuses the project's own `setup_logging`/`JSONFormatter`** (`operational_resilience.py`) via the same `extra={"extra_data": {...}}` convention `production_harness.py` already uses — no parallel logging format introduced.
- Every log line at failure carries `job_id`, `call_sid`, `attempt`, and `worker_id`, so a dead-lettered job's full attempt history is greppable from ops logs, not just from `dlq_peek()`.

## NOT verified in this environment

- **Real Claude API governance decisions.** No API key configured; the "no governor configured" fail-closed branch was exercised instead, which is a real harness code path but not the LLM call itself.
- **Worker OS-process crash under load** (the queue-level SIGKILL chaos test already proved queue-side recovery in isolation; W-5 here proves the worker-side half of that same guarantee using direct calls rather than a second `SIGKILL`'d subprocess — a `SIGKILL`'d worker subprocess mid-claim was not additionally re-run here since the queue's own kill test already covers the mechanism this depends on).
- **Sustained multi-hour operation, memory growth, or connection-pool exhaustion under long-running load.**
- **`run_forever`'s idle/backpressure behavior at very high sustained throughput** — tested at moderate concurrency (4 workers / 25 jobs), not at the queue suite's burst scale (5,000 jobs).
- Same caveat as the queue report: **this suite shares an author with the code.** Recommend a fresh-clone Chromebook re-run, and ideally an adversarial review pass, before treating this as done.

## Scope confirmation

Delivered: `sentinel_worker.py`, `test_sentinel_worker.py`, this report. Depends on the already-verified `queue_schema.py` + `lua/` from the prior session, and the existing, unmodified `production_harness.py`. Not built, by design: the ingress rewrite (`api_server_v2.py`), rate limiting, circuit breaking — this worker is the piece those will sit in front of.
