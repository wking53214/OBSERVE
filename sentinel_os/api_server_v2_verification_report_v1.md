# api_server_v2 Verification Report — v1

**Component:** `api_server_v2.py` — stateless FastAPI ingress (roadster tier 1, third piece after the transmission and the worker)
**Date:** 2026-07-17
**Environment:** container — Ubuntu 24, Python 3.12.3, FastAPI 0.139.0, uvicorn 0.24.0, redis-py 8.0.1, Redis 7.0.15 (dedicated instance on :6390, spawned and chaos-controlled by the suite)
**Repo state:** origin/main still at `87ae59a`. `queue_schema.py` + `lua/` in this environment are the prior session's **contract rebuild** (see Caveats), not the pushed originals.
**Method:** every L-series claim below was exercised over **real HTTP against a real running uvicorn process** with real concurrency (one TCP connection per simulated caller where callers are being counted). TestClient was used only for the T-series routing/validation cases. All headline numbers were produced by **three consecutive clean runs** of the final suite (31 passed / 31, in 63.9s / 61.5s / 67.7s); values below are quoted as the range across those runs. Raw metrics: `chaos_metrics_run{1,2,3}.json`.

---

## 1. What was proven, and how

### 1.1 F-A — garbage and dead jobs cannot gate other callers (structural + live)

**Structural.** The ingress contains no circuit breaker and no shared per-job mutable state. The only shared object is the queue's Redis connection pool (max 64 connections, 2s socket timeouts per call). `test_T10` verifies this two ways at once: (a) the live module table of a process that imported the ingress contains no `production_harness`, `resilient_harness`, `sentinel_core`, or `governance.*` module; (b) an AST walk of the source finds no import, name, or attribute referencing any of those or `CircuitBreaker`. The old failure shape (`resilient_harness.py:22` — one `CircuitBreaker(failure_threshold=5, timeout=60)` gating every caller) cannot exist here because nothing synchronous remains to wrap.

**Live — garbage storm (`L08`).** 300 concurrent callers in one burst, shuffled: 150 valid records, 120 malformed (missing sid, integer sid, blank sid, path-traversal sid), 30 oversized (300 KB).

| Measure | Run 1 / 2 / 3 |
|---|---|
| Valid callers receiving 202 **during** the storm | 150/150 in all runs |
| Malformed → 422, oversized → 413 | 120 + 30 in all runs |
| Every 202'd job queryable afterward | 150/150 in all runs |
| Fresh submissions immediately post-storm, p95 | 46.7 / 38.2 / 41.5 ms |

**Live — DLQ deaths don't latch anything (`L09`).** 10 jobs driven to `dead` (the exact count that would have opened the old breaker twice over), then 20 fresh submissions: all 202, p95 52.3 / 47.2 / 58.9 ms. In the old shape this scenario is 60 seconds of 5xx for every caller.

### 1.2 F-E — nothing blocks /health or concurrent requests (structural + live)

**Structural.** Every queue-touching endpoint is a plain `def`, so FastAPI executes it on the AnyIO worker threadpool; the event loop never runs blocking I/O. `/health` is `async def` with zero I/O and no guards — it exercises only the loop. All Redis calls carry 2s socket timeouts, so a hung Redis costs a bounded threadpool thread, never a hang.

**Live — stuck job (`L10`).** One job claimed with a 60s lease and never acked ("stuck worker") while 40 other jobs were submitted and drained to `done` around it: 40/40 done in every run, the stuck job still honestly `processing`, `/health` p99 during the window 95 / 109 / 163 ms. (Caveat: the window is short, 14–25 health samples — the strong /health evidence is 1.2 below.)

**Live — frozen Redis (`L11`).** `SIGSTOP` on the Redis process (kernel still accepts connections; every command hangs — the nastiest version of "slow dependency") while 30 concurrent submits/polls fired and a dedicated probe thread on its own persistent connection sampled `/health` continuously:

| Measure | Run 1 / 2 / 3 |
|---|---|
| /health probe samples during freeze | 166 / 172 / 167 |
| /health p50 | 2.7 / 2.2 / 2.4 ms |
| /health max | 159 / 90 / 164 ms |
| Queue-touching responses | 100% honest `503 queue_unavailable` + `Retry-After`; zero hangs, zero fake states, zero 404s |
| 503 latency p50 / max | ~2.9 s / 3.03–3.18 s (bounded by the 2s socket timeout + contention overhead; degraded single call 2.04–2.05 s) |
| Recovery after `SIGCONT` | next submit 202, `/ready` true, within the 10s wait in every run |

**Live — real overlap, not inspection (`L12`, `L14`).** 200 submissions from 50 client threads: overlap factor (Σ individual latencies ÷ wall clock) 44.4–45.5×. A serialized event loop makes that number ~1. A second generator — single-threaded asyncio, 100 persistent keepalive connections, built to remove the load generator's own GIL contention from the measurement — sustained 80.9–84.5 rps with 500/500 → 202.

**Where the ceiling is (measured, not asserted):** on this container, `/health` alone benches 80.5 rps and the full submit path 73.5 rps — the single-worker ceiling is the box's CPU on HTTP handling itself; validation + enqueue + logging adds ~1.2 ms/request over the routing baseline. An unplanned but useful datum: a bench accidentally run against a Redis that had died measured the total-outage path at ~73 rps of instant honest 503s — a downed queue does not collapse the ingress's request handling. These are box-relative numbers, not production capacity claims; the ingress is stateless, so capacity scales with `INGRESS_WORKERS`/replicas (untested — see §3).

### 1.3 No untrackable 202 (`L07`)

Mechanism: the 202 is returned only after `enqueue()`'s single atomic Lua script has created the job hash and pushed it pending. Live: 150 submit→immediate-poll pairs per run (poll on a different TCP connection), 30-way concurrency — **0 / 450 pairs across the three runs** hit a 404; every instant poll returned a real state.

### 1.4 The ingress never lies about state (`L05`, `L11`, `T05`)

Unknown ID → `404 {"error": "job_not_found", ...}` with no status field — structurally distinct from any pending shape. Queue unreachable → `503 queue_unavailable` ("state unknown right now"), never 404, never a fabricated status, with `Retry-After`. A 413-rejected oversized record is proven **not** enqueued. No code path returns a job_id that wasn't durably enqueued.

### 1.5 Full trajectory observability, including a useful "dead" (`L01`–`L04`)

Polled over HTTP at every hop, one job observed exactly `pending → processing → scheduled → processing → done` (identical in all three runs), with `claimed_by`, `attempts`, `lease_expires_at`, `scheduled_for`/`retry_in_s`, and the retry's `error_trail` entry still present in the final `done` view. Non-retryable failure → `dead` with `dead_reason=data_corruption_in_transit`, `died_at`, `last_error`, and the trail. Retry exhaustion → `dead` after attempts [1, 2, 3], full three-entry trail, `dead_reason` = last failure's reason. "Dead" is diagnosable from the poll response alone, which was the requirement.

### 1.6 Idempotency on sid (`L06`)

20 **concurrent** resubmissions of one sid: 20× 202, exactly 1 `deduped=false` in every run (the Lua enqueue is the arbiter), same job_id for all. Resubmission after completion returns 202 / `status=done` / `deduped=true` and does not reset the job.

### 1.7 Cheap-reject validation without duplicating the harness (`T01`–`T08`)

Rejected at ingress (422): missing sid, integer sid (StrictStr — no coercion), blank/whitespace/control-character/`/`-containing sid, non-JSON body; (413): oversized body. Admitted untouched: everything else — `T07` asserts the enqueued payload is byte-for-byte the submitted record; Twilio-shape parsing stays the harness's job, and a record that is garbage-past-the-sid dead-letters with a real reason instead of being second-guessed at the door. Poll responses never echo the payload back (`T08`) — no free PII replay from a status endpoint.

### 1.8 The guard seam takes today's auth unmodified (`L13`)

A second live ingress with `ICEBERG_API_KEYS` set attached the existing `api_key_auth.require_api_key` (with its per-IP pre-auth limiter) through the `INGRESS_GUARDS` seam: unkeyed → 401, wrong key → 403, keyed → 202, `/health` stays open. `rate_limiter_v2.py` (F-F) is one `INGRESS_GUARDS.append(...)` at the same seam — keyed on connecting IP / authenticated principal, never payload identity — and was deliberately **not** built.

---

## 2. Incidents during verification (the verifier needed fixing, not the code)

Reported because run-1 numbers would otherwise look suppressed. First full run: 25/30, five failures traced to **the test harness**, not the ingress: (a) the suite piped the server's stdout and read nothing, so once the 64KB pipe filled, every server-side logging call blocked on the pipe — a self-inflicted outage (fix: server output to files, as a supervisor does in production); (b) the no-breaker check was a blunt text scan that flagged the docstring *describing* the old breaker (fix: AST walk of actual code); (c) `/health` latency was measured through the same 50-thread generator producing the chaos, contaminating server numbers with client-side GIL queuing (fix: dedicated probe thread, own persistent connection). After those fixes the final suite passed 31/31 three times consecutively with the stable numbers above. No change to `api_server_v2.py` resulted from any of this.

---

## 3. What was NOT verified

- **The real worker was not in the loop.** `sentinel_worker.py` is not present in this environment (never pushed; container state from the transmission session only). State transitions were driven by a test Drainer speaking the same `TransmissionQueue` consumer API the worker uses (`claim`/`heartbeat`/`ack`/`fail`/`reap_expired`). The ingress only reads job hashes and cannot distinguish the two — but ingress→worker→ledger end-to-end remains unverified as a whole system.
- **The queue under test is the contract rebuild.** `queue_schema.py` + `lua/` here were rebuilt last session from the documented, verified transmission contract because the originals were never pushed. Before merging, diff against your local originals. The ingress touches exactly four queue methods — `enqueue`, `get_job`, `stats`, `ping` — plus the constructor; if local names differ, those are the only call sites.
- **Multi-process ingress** (`INGRESS_WORKERS > 1`, or multiple replicas) untested. The design is stateless so it should be safe; that is an inference, not evidence.
- **TLS passthrough** (`SSL_CERTFILE`/`SSL_KEYFILE` → uvicorn) untested; no certs were exercised.
- **Chunked uploads bypass the 413 guard** by construction (it checks declared Content-Length); bounded by the fronting proxy in production, as documented in the code. Not exercised.
- **Degraded-mode latency is redis-py-version-dependent.** Measured on redis-py 8.0.1: one ~2.05s socket-timeout per call. A client-library upgrade that changes retry policy changes the 503 budget; re-measure L11 if redis-py moves.
- **No soak.** Longest continuous run ~68s; memory/fd behavior over hours not observed.
- **Absolute numbers are this container's**, not production hardware's. Treat rps/latency as shape evidence, not capacity planning.
- Standing caveat: the test suite shares an author with the code under test.

---

## 4. Deliverables

| File | What |
|---|---|
| `api_server_v2.py` | The ingress (place at repo root beside `queue_schema.py`) |
| `test_api_server_v2.py` | The live suite — spawns its own Redis (:6390) and uvicorn (:8102/:8103); `python3 -m pytest test_api_server_v2.py -v -s` |
| `chaos_metrics_run{1,2,3}.json` | Raw measured numbers behind every figure quoted above |
| `api_server_v2_verification_report_v1.md` | This report |

Out of scope, by design, with their seam ready: `rate_limiter_v2.py` (F-F) and any deliberate scoped `circuit_breaker.py` attach at `INGRESS_GUARDS`.
