# Transmission Queue Contract v1

The single source of truth for `queue_schema.py` (unified build) — the Redis-backed transmission between the stateless ingress (`api_server_v2.py`) and the V12 governance worker pool (`sentinel_worker.py`). This document exists because two correct implementations diverged at the wire; every interface fact below is now load-bearing and tested (67/67 across four suites — see `cage_match_report_v1.md`).

## 1. Guarantees

1. **Exactly-one-structure invariant.** Every admitted job ID lives in exactly one of five structures at all times — `pending` (list), `scheduled` (zset), `processing` (zset), `dead` (zset), `done` (zset, retention-bounded) — and every transition is one atomic Lua script. No crash timing loses a job; no interleaving double-claims one. `verify_invariants()` audits this on demand.
2. **At-least-once delivery; exactly-once effect by dedup at both ends.** Ingress retries are absorbed by `enqueue()` idempotency on `job_id` (use the call sid). Worker redeliveries are absorbed by the Postgres ledger's sid dedup. The pipe itself never promises exactly-once — the ends do.
3. **Worker contract:** claim → work → **commit ledger write** → ack. Never ack on a failed ledger write — `fail()` it with a reason. A crash between commit and ack is safe by design: redelivery hits the ledger dedup.
4. **Fencing.** Each claim carries a fencing identity (worker_id + per-claim token). ack / fail / heartbeat from an expired-and-reclaimed worker return STALE (dialect: `False` / `"fenced"`) and cannot touch the live claim.
5. **Loud failure.** Every Redis failure raises. Nothing is caught-and-printed. An enqueue that didn't happen never looks like one that did.
6. **Clock authority is Redis TIME**, read inside each script. Worker host clocks never touch lease or retry arithmetic.
7. **Payload integrity.** Payloads are checksummed at enqueue and verified at claim; corruption at rest dead-letters with evidence — the worker never sees a tampered payload.
8. **Bounded, diagnosable retries.** Retryable failures back off exponentially (base·2^(n−1), capped, plus jitter in the original dialect; deterministic in the rebuild dialect) up to `max_attempts`, then dead-letter with the complete error trail (attempt, reason, detail, worker, timestamp). Unclassified deaths set `escalate=1`.
9. **Crash recovery.** `reap_expired()` — safe from any worker on a timer — requeues or dead-letters expired leases with a trail entry, and quarantines dangling references to `orphans` instead of crashing or silently dropping.
10. **Completion records.** Ack leaves a `done` record (status, `completed_at_ms`, optional result) retained for `done_keep_ms` (default 24 h). Within retention: the job is pollable as "done", a resubmit dedups (**a finished job is never reset or re-run**), a second ack returns GONE. `done_keep_ms=0` restores v1 delete-on-ack.

## 2. Two dialects, one engine

The constructor picks the facade; both operate the same keys, scripts, fence, and guarantees. Cross-dialect handles on the same prefix interoperate (tested).

| | **Original dialect** — `TransmissionQueue(name=...)` | **Rebuild dialect** — `TransmissionQueue(namespace=...)` |
|---|---|---|
| Used by | `sentinel_worker.py`, chaos suite | `api_server_v2.py`, ingress suite |
| Defaults | max_attempts 5 · lease 30000 ms · backoff 1000→60000 ms · jitter 250 ms · socket 5 s | max_attempts 3 · lease 30 s · backoff 0.5→30 s · jitter 0 (deterministic) · socket 2 s |
| enqueue | `enqueue(payload, job_id=...)` → unpackable as `(job_id, created)` | `enqueue(job_id=..., payload=...)` → same object, read as `{"job_id","status","deduped"}` (status is live: "pending" on create, current state — including "done" — on dedup) |
| claim | `claim(worker_id, lease_ms=, wait_timeout_s=)` → `ClaimedJob` or None | `claim(worker_id=, lease_seconds=)` → dict with `claim_token` or None |
| ack | `ack(claimed_job)` → `Outcome` (OK/GONE/STALE) | `ack(job_id, claim_token, result=None)` → bool; `result` persists on the done record |
| fail | `fail(claimed_job, Reason, detail, retryable=)` → `(Outcome, backoff_ms)` | `fail(job_id, claim_token, reason, error, retryable=True)` → `"scheduled" \| "dead" \| "fenced"` |
| heartbeat | `heartbeat(claimed_job, lease_ms=)` → `Outcome` | `heartbeat(job_id, claim_token, lease_seconds=)` → bool |
| Reason vocabulary in views | `process_crash`, `data_corruption` | `process_crash_restart`, `data_corruption_in_transit` (accepted on write, rendered on read; storage is always canonical) |

Both dialects share, identically: `get_job`, `ping`, `stats`, `promote_due`, `reap_expired`, `requeue_from_dlq`, `dlq_peek`, `dlq_rate`, `error_trail`, `verify_invariants`, `flush_namespace`, `classify_exception`, `close`.

## 3. Job lifecycle and views

`pending → processing → done`, with `processing → scheduled → pending` on retryable failure, `processing/scheduled → dead` on budget exhaustion or non-retryable reason, `dead → pending` via `requeue_from_dlq` (fresh budget, history kept). `get_job(job_id)` renders any state read-only: pending (payload, attempts, budget), processing (claimed_by, lease_expires_at), scheduled (scheduled_for, error_trail, last_error), done (completed_at, result), dead (dead_reason, died_at, full trail) — or None for never-existed / retention-expired. GONE answers: ack, fail, heartbeat, or requeue against a done record all return GONE-class results, matching v1's answers when completion deleted the record.

## 4. Operations & observability

`stats()` is one cheap call returning the superset both consumers need: depths (`pending`, `scheduled`, `scheduled_due`, `processing`, `processing_overdue`, `dead`, `dead_last_hour`, `done_retained`), staleness (`oldest_pending_age_ms`/`_s`), `depth_ready`, `orphan_refs`, lifetime `counters` (incl. `completed`, mirrored as `done` for the rebuild's readers), and `dead_reasons`. `processing_overdue > 0` means the reaper is behind. Run `reap_expired()` on a timer from every worker; run `promote_due()` from a scheduler if you want promotion decoupled from claims (claims still promote opportunistically). `verify_invariants()` is the audit; it prunes `done` at the retention boundary before judging, so expiry is never a false alarm.

## 5. Deployment

Single Redis primary; `appendonly yes` (`appendfsync always` for a zero-loss guarantee across a Redis kill -9; `everysec` accepts up to ~1 s of acknowledged enqueues at risk — choose per environment; the suite's crash test runs `always` so its claim is honest). Keys derive from one prefix inside Lua — not Redis-Cluster slot-safe. Redis Sentinel failover: compatible in principle, **not verified**. Memory: each completion retains one job hash + trail for `done_keep_ms`; size accordingly or lower the retention.
