# The Transmission — Verification Report v1

**Component:** Tier 2 Redis queue (`queue_schema.py` + Lua scripts)
**Date:** July 16, 2026
**Environment:** Redis 7.0.15, redis-py 8.0.1, Python 3.12.3, Ubuntu 24 container; repo cloned at HEAD `87ae59a` (one commit past the fifth-pass audit HEAD `5fb20b3` — a COMPLIANCE.md rewrite, no code change)
**Method:** Every claim below was produced by executing the suite (`test_queue_schema.py`, 18 tests) against a real `redis-server` process this session — no mocks, no fakes. Chaos tests use real `SIGKILL` on real OS processes. The suite passed **18/18 on three consecutive clean-state runs** (8.7s, 8.2s, 8.3s).

---

## The invariant everything hangs on

A job admitted to the transmission exists in **exactly one** of four structures at all times — `pending` (list), `scheduled` (retry zset), `processing` (lease zset), `dead` (DLQ zset) — and every transition between them is a **single atomic Lua script** executed server-side. `verify_invariants()` audits this directly and was asserted after every chaos scenario. There is no state in which a crash loses a job, and no interleaving in which two workers hold the same job.

## Verified live (evidence, not confidence)

**V-1. No double-claim under concurrency.** 2,000 jobs, 12 concurrent claimers: 2,000 claims, 2,000 unique job IDs, 0 duplicates, completion counter exactly 2,000, invariant clean. Drain rate 2,347 claim+ack/s. Atomicity is server-side (Redis serializes scripts), so the guarantee is independent of client topology — the crash test below repeats a claim from a genuinely separate OS process.

**V-2. Crashed worker: no loss, no duplicate, queue-only recovery.** A real forked worker process claimed a job (700ms lease) and was `SIGKILL`ed mid-job. The queue alone recovered it: `reap_expired()` found the expired lease, recorded a `process_crash` error entry naming the dead worker, requeued the job; a second worker claimed it (attempt 2) and completed it exactly once. No worker registry, no heartbeats — the lease zset is sufficient.

**V-3. Claim fencing (the stale-zombie case).** Worker A's lease expired, the job was reaped and reclaimed by worker B. A's late `ack` and `fail` were both rejected (`stale`, counted), B's ack succeeded, completed count = 1. A worker that "comes back from the dead" cannot corrupt someone else's claim. (Its already-committed ledger write, if any, is absorbed by the ledger's sid dedup — see delivery semantics.)

**V-4. Broker death: kill -9 on Redis itself.** With 70 jobs pending, 10 in-flight under lease, and 20 already completed, Redis was `SIGKILL`ed and restarted (`appendonly yes`, `appendfsync always`). Result: counters and all 80 live jobs intact, the 10 orphaned leases reaped and recovered, all 100 jobs eventually completed, 0 lost, 0 duplicated, invariant clean. Two properties proven incidentally: (a) the **same client object's connection pool recovered** without intervention; (b) the restarted server had an **empty script cache**, and every operation still worked — the NOSCRIPT→EVAL fallback is real, not assumed.

**V-5. Retries are bounded, backed off, and diagnosable.** A job failed with `network_latency` three times: observed backoffs 100ms then 200ms (base×2^(n−1), jitter 0 for determinism), then dead-lettered at the attempt budget. Its DLQ record carries the full trail — attempt number, reason, detail, worker, timestamp for every failure, newest first. `dlq_peek()` answers WHY, not just THAT.

**V-6. Reason taxonomy behaves per spec.** All reasons use the established DR vocabulary verbatim. `data_corruption` is non-retryable by default (a bad payload won't heal by retrying) and dead-letters on first failure. `unclassified` sets `escalate=1` on the job. Per-reason DLQ counters and a trailing-hour DLQ rate are queryable. A crash-looping job (kills its worker every attempt) still dead-letters after its budget with reason `process_crash`.

**V-7. Corruption is caught before a worker sees it.** Every payload is checksummed (SHA-256) at enqueue and verified at claim. A payload tampered at rest was auto-dead-lettered with both checksum prefixes in the evidence; the worker never received it; a `corrupt_payloads` counter incremented. A dangling queue reference with no job record is quarantined to an `orphans` list and counted — never silently skipped.

**V-8. Failure is loud, never silent (the F-2 lesson, structurally).** An unreachable broker makes `enqueue()` raise; there is no code path in the module that catches a Redis error and reports success — no bare excepts, no print-and-continue. An enqueue that did not happen cannot look like one that did. Client-side `retry_on_timeout` is deliberately OFF: blind retries of non-idempotent ops are how silent duplicates happen; `enqueue` is idempotent so callers may retry it explicitly, and a re-sent `ack` after a dropped reply returns `gone` harmlessly (tested).

**V-9. Idempotent admission.** Enqueue is idempotent on `job_id`: a repeated enqueue (ingress webhook retry) is counted as a duplicate, not re-inserted. Tested; intended usage is `job_id = call_sid`.

**V-10. Observability before outage.** One cheap `stats()` call returns: ready depth, pending/scheduled/processing/dead sizes, **oldest-pending age** (staleness), **overdue leases** (reaper lag — >0 means recovery is behind), DLQ arrivals in the trailing hour, per-reason death counts, lifetime counters. All asserted live.

**V-11. Burst accounting is exact.** 5,000-job burst: enqueue 8,854/s single-threaded; 8 workers drained at 3,584 claim+ack/s; completed = enqueued = 5,000, every structure empty after, invariant clean. These are in-container loopback numbers — shape evidence, not capacity planning — but they sit two orders of magnitude above the ~32/s serialized V12 ledger ceiling, so the transmission will not be the bottleneck; the workers will be, which is the point.

## Delivery semantics (the contract the worker session inherits)

The queue is **at-least-once**. Exactly-once *effect* comes from dedup at both ends of the pipe, not from the pipe: ingress retries are absorbed by idempotent enqueue on `call_sid`; worker retries are absorbed by the ledger's sid dedup. Worker contract, in order: **claim → do work → commit ledger write → ack**. Never ack on a failed ledger write — `fail()` it with a reason. A worker that dies between ledger commit and ack causes a retry that the ledger dedup absorbs. This ordering is documented in the module and in `ClaimedJob`, but it is a contract the worker must honor — the queue cannot enforce it from its side.

## NOT verified in this environment (read this list as seriously as the one above)

- **Redis Sentinel failover.** No Sentinel deployment available here. Single-node kill -9 recovery is proven; primary election behavior during a failover window is not. Design expectation: operations fail loudly during the window and resume after — unobserved.
- **`appendfsync everysec` loss window.** The zero-loss claim in V-4 was earned under `appendfsync always`, deliberately. Under the default `everysec`, a broker kill -9 can lose up to ~1s of acknowledged enqueues. That tradeoff is documented, not measured.
- **Multi-host clock skew.** Designed out — Redis server TIME is the only clock in lease/retry arithmetic; worker clocks never participate — but demonstrated on one machine only.
- **Redis Cluster.** Explicitly unsupported: keys are derived from a prefix inside Lua, which is not cluster-slot-safe. Single instance/primary assumed and documented.
- **Long soak.** Minutes of load, not hours or days; no long-horizon memory-growth observation.
- **Real V12/ledger integration.** Out of scope per the package; payloads were treated as opaque, as designed.
- **True asymmetric network partition.** Broker death and unreachable broker are tested; a physically induced reply-lost-after-execute partition is not — its client-side consequence (ack retry) is simulated and safe (V-8).
- **`classify_exception()` helper** is a suggestion utility for the worker and is not exercised by this suite; the worker owns final reason classification.

One epistemic caveat in this project's own tradition: **the suite and the code share an author.** Three clean runs is necessary evidence, not sufficient. The right next check is a fresh-clone run on the Chromebook (below), and ideally an adversarial pass by a session that didn't write it.

## Design decisions worth knowing (directional, not code-level)

- **Polling claim, not blocking pop.** A blocking move would split the claim into two steps and need a second recovery path for a crash between them. One atomic script plus ≤50ms polling latency wins for a system whose failure mode of record is silent loss, not milliseconds. The interval is tunable per call.
- **Retried jobs rejoin the back of the FIFO line**, so a retry storm cannot starve fresh calls.
- **Error trails are capped** (attempt budget + 3 entries) so a hot failure loop cannot grow Redis memory unboundedly.
- **`requeue_from_dlq()`** gives an operator a one-call way to return a dead job to service with a fresh budget while preserving its error history.

## Re-running this on the Chromebook

```bash
sudo apt-get install -y redis-server   # or have redis-server on PATH
pip install redis pytest --break-system-packages
cd <dir containing queue_schema.py, lua/, test_queue_schema.py>
python3 -m pytest -q -s test_queue_schema.py
```
The suite starts and destroys its own Redis instances on ports 6399/6400; it does not touch a system Redis.

## Scope confirmation

Delivered: `queue_schema.py`, `lua/` (7 scripts: shared helpers + enqueue, claim, ack, fail, reap, requeue_dead), `test_queue_schema.py`, this report. Not built, by design: worker, ingress, rate limiting, circuit breaking — the seams they plug into are the `enqueue()/claim()/ack()/fail()` surface plus `stats()` for metrics scraping.
