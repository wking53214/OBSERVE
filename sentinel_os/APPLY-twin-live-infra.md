# Twin live-infra fix -- delivery

Baseline: origin/main @ 97b3571 (C2 input-side checkers, 365/365 green,
already merged and pushed).
This branch: twin-live-infra @ 4659471, one commit on top of 97b3571.

## What this actually fixes

Not test flakiness -- a real bug in `cassette_loader.py`, the production
cassette-loading path. `CassetteLoader.load_cassette()` dynamically
`exec`'d cassette modules without registering them in `sys.modules`, which
made `cassette_forensics.compute_cassette_code_hash` silently fall back to
a meaningless placeholder instead of the cassette's real source. The
result: the same cassette class hashed differently depending on how it was
loaded, and the two hashes would eventually collide in the ledger's
`bind_cassette_version` tamper-detection tripwire -- a false positive that
cascaded into a pile of unrelated-looking failures ("permission denied for
table ledger_entries" and friends) any time the full suite ran more than
once against the same persistent ledger. Full root-cause and fix detail is
in the commit message (`git log -1`).

Alongside that, this commit also does what you asked for directly: it
captures the twin live-suite's infrastructure (three OS identities, their
peer-auth Postgres roles) as real, committed, idempotent setup code
(`scripts/twin_ensure_services.sh`) instead of leaving it as tribal
knowledge from whichever container originally built it -- and fixes two
smaller real bugs in `test_twin_live.py` that only showed up once that
infra actually existed (a hardcoded dev-container path, and a
`ledger_reader` password that silently disagreed with `conftest.py`).

## Verified

Full repo suite, **no `--ignore` flags at all** -- all 383 tests (341
original baseline + 24 C2 input-side-checker tests + 18 twin-live tests) --
run **twice back-to-back from a clean database with zero manual reset in
between**: 383/383 both times. Before this fix, the same back-to-back run
reliably failed the second time; confirmed reproducible before the fix,
confirmed gone after it.

One unrelated, pre-existing flaky test surfaced once during verification --
`test_api_server_v2.py::test_L11_frozen_redis_health_stays_alive`, a
wall-clock latency assertion that's sensitive to system load. It passed in
isolation and on every other run; nothing in this commit touches it. Not
fixed here -- flagging it honestly rather than silently working around it.

## Setting up the infra locally (one-time, on your Chromebook)

Before running the full suite (with `test_twin_live.py` included) locally,
install the self-heal script once:

```bash
cd ~/sentinel_os/sentinel_os
sudo install -m 0755 scripts/twin_ensure_services.sh /usr/local/bin/twin_ensure_services
sudo /usr/local/bin/twin_ensure_services
```

This is idempotent -- safe to re-run any time (e.g. after a reboot, or if
Postgres/Redis need restarting). It creates `sentinelsvc`, `twincustomer`,
`twincustodian` as real OS users with matching peer-auth Postgres roles,
and grants `sentinelsvc` into the existing `ledger_reader` role. It does
NOT touch anything if it's already been run before.

## Apply on your Chromebook

```bash
cd ~/sentinel_os
git fetch origin   # baseline expected at 97b3571
git checkout -b twin-live-infra 97b3571
git bundle verify /path/to/twin-live-infra.bundle
git pull /path/to/twin-live-infra.bundle twin-live-infra
```

Or via patch instead:

```bash
cd ~/sentinel_os
git checkout -b twin-live-infra 97b3571
git am /path/to/twin-live-infra.patch
```

Then, after running the one-time infra setup above:

```bash
cd sentinel_os
python3 -m pytest . -q   # full suite, no --ignore, expect 383 passed
```

Once you're happy with it:

```bash
git checkout main
git merge --ff-only twin-live-infra
git push origin main
```

## What's still open (stated plainly, not buried)

- GitHub Actions CI still excludes `test_twin_live.py` -- not because the
  infra is missing anymore, but because peer auth needs a Unix socket the
  test process and Postgres share, and this workflow's Postgres runs in a
  separate Docker service container reachable only over TCP. Closing this
  in CI means giving that job a natively-installed Postgres instead of the
  `services:` container -- a real, separable follow-up, not attempted
  here since I can't verify a GitHub Actions run from this environment.
- The unrelated flaky timing test noted above.
