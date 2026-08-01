# SENTINEL OS — MASTER PATCH SESSION

**Repository:** https://github.com/wking53214/sentinel_os
**Nesting:** clone target → `cd sentinel_os/sentinel_os/` (repo root, then the actual package one level down). All paths below assume you're standing in that inner directory unless stated otherwise.

## CONTEXT — read this before touching anything

A prior session (Opus, live execution against real Postgres 16.14) audited this repo at HEAD (`80e9f39`) and found:
- Two CRITICALs from an earlier audit (chain tamper detection, cassette-snapshot forensics) were **genuinely fixed** — verified live by flipping a decision's `approved` field in place and confirming `verify_chain()` caught it.
- But the fix commit **broke the build**: 25 tests failing, `process_call()` raised on every call, because of a `float_value()`/`int_value()` type mismatch and the harness passing `cassette=None` to the Twilio parser instead of the resolved cassette.
- A **Gate 0 patch** was written and verified (clean clone, patch applies, full suite passes) that fixes the build, updates 4 stale tests, deletes 2 dead files, fixes an unconditional-skip test fixture (`conftest.py`'s `test_ledger`/`test_cassette` used to `pytest.skip()` no matter what — now they probe Postgres for real), a resulting import-identity bug that surfaced once the fixture stopped hiding it, and a `_as_json()` bug that silently turned SQL `NULL` into `{}`. End state: **142 passed, 0 skipped, 0 failed.**
- Beyond that, a full audit (load test, outage/recovery simulation, cassette-swap-under-load, static analysis, dependency CVE scan) found the governance/fail-closed core and throughput to be genuinely solid (0 approvals leaked across 300 calls during a simulated sustained outage; ~800k governed calls/hr ceiling; P99 3ms at realistic concurrency), but left these **open, unpatched** findings:

| ID | Finding | File(s) |
|---|---|---|
| H-A | Ledger not truly immutable: `ledger_immutability.sql` blocks UPDATE/DELETE via triggers (verified live) but **not TRUNCATE** (row triggers don't fire on it), and the app connects as **superuser** so triggers are droppable | `governance/ledger_postgres.py`, `ledger_immutability.sql` |
| H-B | API key auth is timing-unsafe (`api_key not in self.keys`, not `hmac.compare_digest`), plaintext storage, and there is **zero rate limiting** on any endpoint (`/ledger`, `/process_call`, `/verify_ledger` etc.) | `api_key_auth.py`, `api_server_resilient.py` |
| H-C | `fastapi==0.104.1` pin — live 2026 Starlette CVE-2026-48710 ("BadHost", auth-bypass via malformed Host header) + CVE-2025-62727 (Range-header DoS) sit in its dependency tree, reachable given this exposes an authed server | `requirements.txt` |
| M-A | `AUDIT_PLAYBOOK.md`'s own hash-verification SQL references a column `hash` that doesn't exist (real column is `current_hash`) and uses a canonical form that doesn't reproduce the real hash — confirmed live: running it errors with `column "hash" does not exist` | `AUDIT_PLAYBOOK.md` |
| M-B | No idempotency/dedup on `sid`/`caller_id` — duplicate call submission (retry, client bug) writes two permanent rows into an append-only chain | `production_harness.py`, `twilio_log_ingestion.py` |
| M-D | No pod-level `securityContext` (`runAsNonRoot`, `readOnlyRootFilesystem`, capability drops) anywhere in `k8s/` or `Deploy/k8s/` — non-root today only by Dockerfile `USER` convention, not cluster-enforced | `k8s/deployment.yaml`, `Deploy/k8s/` |
| L-B | 130 ruff findings, overwhelmingly unused imports/locals/f-strings, no logic bugs | repo-wide |
| L-C | No distributed tracing (grepped for opentelemetry/trace_id/span — zero hits) | `production_harness.py` is the natural spine |

## MISSION

Produce **one master `git diff` patch file** that fixes everything in that table **that has no contingency** — meaning: no undeclared secrets, no external cluster/API dependency to validate, no ambiguous business-policy call with more than one reasonable answer. For anything that genuinely needs a human decision or credential you don't have, **do not guess** — implement nothing for it, and list it explicitly at the end under "NOT INCLUDED — needs a decision," with the specific question that needs answering.

Explicitly:
- **H-A, H-B, H-C, M-A, M-D, L-B are all contingency-free.** Fix all of them.
- **M-B (idempotency) is likely a contingency** — "what should happen on a duplicate `sid`: reject, dedupe silently, or log-and-allow?" is a policy call, not an engineering one. Do not implement a guessed behavior change. You may add a **detection-only** version (log/flag a duplicate without changing what gets written) if that's genuinely behavior-neutral; if it isn't, skip it and flag it.
- **L-C (tracing) is a judgment call** — it's a real new dependency (`opentelemetry-*`) and touches every call in the hot path. If you can add it with an OTLP exporter that's a no-op/no-crash when no collector is configured (safe default), include it; if you can't verify that live in the sandbox, skip it and flag it rather than ship something untested.
- For H-A specifically: the `ledger_reader` non-superuser role already exists in `ledger_immutability.sql` but nothing wires the app to connect as it. Wire it with a **configurable env var** (e.g. `ICEBERG_LEDGER_ROLE`/`ICEBERG_LEDGER_PASSWORD`), defaulting to the existing superuser behavior with a printed warning if unset — don't hardcode a password that doesn't exist yet. Also add a statement-level `BEFORE TRUNCATE` trigger, since row-level triggers don't cover it.
- For H-C: bump the pin(s), then **run the full test suite** to confirm nothing broke before including it in the patch.

## ENVIRONMENT SETUP (do this first — same as the prior session)

```bash
git clone https://github.com/wking53214/sentinel_os.git
cd sentinel_os/sentinel_os/

pip install psycopg2-binary anthropic==0.116.0 "httpx<0.28" prometheus_client \
    pytest==7.4.0 fastapi==0.104.1 uvicorn==0.24.0 pydantic==2.4.0 python-dotenv \
    --break-system-packages -q

apt-get update -q
apt-get install -y -q postgresql
export PGBIN=$(ls -d /usr/lib/postgresql/*/bin)
mkdir -p /var/lib/pgsql/data && chown -R postgres:postgres /var/lib/pgsql
su postgres -c "$PGBIN/initdb -D /var/lib/pgsql/data -A trust"
su postgres -c "$PGBIN/pg_ctl -D /var/lib/pgsql/data -l /tmp/pglog.txt -o '-p 5432' start"
su postgres -c "$PGBIN/psql -p 5432 -c \"CREATE USER iceberg WITH PASSWORD 'iceberg' SUPERUSER;\""
su postgres -c "$PGBIN/psql -p 5432 -c \"CREATE DATABASE iceberg OWNER iceberg;\""

mkdir -p certs && openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem \
    -out certs/cert.pem -days 365 -nodes -subj "/CN=localhost"
```

**First, before writing anything new:** confirm the Gate 0 fixes described above are actually needed on the HEAD you cloned (a newer commit may have superseded some of this — check `git log`). If HEAD already includes them, don't re-apply; if it doesn't, apply Gate 0 first (build must be green — `142 passed, 0 skipped, 0 failed` — before you start layering H-A/H-B/H-C/M-A/M-D on top).

## VERIFICATION BAR — non-negotiable

Every fix in the patch must be proven **live**, the same way the prior session did it, not just read and assumed correct:
- H-A: apply `ledger_immutability.sql`, then actually attempt `TRUNCATE` and `UPDATE`/`DELETE` as both the superuser and (if wired) `ledger_reader`, and show the results.
- H-B: write a driver that hits an authed endpoint with a wrong key and confirms timing doesn't leak (or at minimum confirms `hmac.compare_digest` is now used), and confirms rate limiting actually triggers a 429 past the configured threshold.
- H-C: run the full suite post-bump, live, and paste the pass/fail count.
- M-A: run the corrected playbook SQL against a live ledger with real entries and show it matches `verify_chain()`'s own answer.
- M-D: validate the manifests parse (`kubectl apply --dry-run=client` or equivalent if available; otherwise at minimum YAML-lint them) — don't just eyeball the diff.
- Whole patch: fresh clone, apply patch, full test suite, report the exact pass/fail/skip counts, same as the Gate 0 verification.

## DELIVERABLE

1. A single `git diff`-format `.patch` file covering everything contingency-free from the table above (plus Gate 0 if not already on HEAD), verified to apply cleanly to a fresh clone and leave the suite green.
2. A short summary: what's in the patch, what live checks proved each fix works, and effort/verification evidence per item (matching the style of the prior session's Gate 0 handoff).
3. An explicit **"NOT INCLUDED — needs a decision"** section for M-B and (if skipped) L-C, each with the specific one-sentence question that needs an answer before it can be safely automated.

Be honest if something doesn't hold up under live testing — say so and show the failing output rather than quietly softening the claim, same standard as the audit this builds on.
