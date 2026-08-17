# CI native-postgres change -- delivery (read this before merging)

Base: twin-live-infra @ 4659471 (already delivered, fully verified locally
383/383 twice back-to-back -- safe to apply/merge on its own regardless of
what you decide about this commit).
This branch: twin-ci-native-postgres @ d881bc0, one commit on top.

## What this is

Closes the one honest gap left open in the twin-live-infra delivery: CI
still couldn't run test_twin_live.py, because GitHub Actions' Postgres runs
in a separate Docker container reachable only over TCP, and peer auth
(which sentinelsvc/twincustomer/twincustodian all depend on) needs a Unix
socket shared with the test process -- no amount of test-side fixing could
ever close that gap, only a different Postgres setup for the job could.

This commit replaces the `services: postgres:` Docker container with a
natively apt-installed Postgres on the runner (same package, same
`local all all peer` default this repo's own dev containers already use),
provisions it with the iceberg/iceberg identity every DSN in the repo
assumes, provisions the twin suite's OS identities via the now-committed
`scripts/twin_ensure_services.sh`, and runs the full suite with zero
exclusions.

## Important: how this was verified, and what that does and doesn't prove

**I cannot run a real GitHub Actions job from this environment.** Everything
else delivered this session (the C2 checkers, the twin-live-infra fix) was
verified by actually running the real test suite start to finish, repeatedly.
This one is different, and I want to be upfront about exactly how far my
verification goes:

What I did: extracted every `run:` block from the literal workflow YAML and
replayed them, in order, in a completely fresh environment (Postgres, Redis,
and all three OS identities fully purged, not just reset) using a small
local `sudo` stub that faithfully preserves real sudo's flag semantics
(`-u`, `-E`) so the commands that actually ran were byte-identical to what
the workflow specifies. That's the same base OS GitHub's `ubuntu-latest`
runner uses. Result: full suite, no exclusions, **383/383**.

What I could NOT verify: the very first "Install dependencies" step (plain
`pip install -r requirements.txt`) fails standalone in this specific
sandbox, because its system Python is externally-managed (Debian/apt
Python, PEP 668) and refuses a bare `pip install` outside a virtualenv.
That step is **unmodified** from the version already confirmed green on a
real GitHub Actions run in an earlier session -- GitHub's `setup-python`
action installs a standalone Python build that doesn't carry PEP 668's
restriction, so this should be a sandbox-only artifact, not a real problem
-- but I could not confirm that step passes end-to-end myself, only reason
about why it should.

## Recommended path: PR first, not a direct push

The workflow only triggers `on: push: branches: [main]` or
`pull_request: branches: [main]` -- pushing this branch on its own won't
run CI at all. **Open a PR from `twin-ci-native-postgres` into `main`**
(after merging twin-live-infra into main first, or targeting main directly
if you've already merged that base) so you get a real Actions run to look
at before this touches main's history. If it's green, merge it. If it's
not, the fix is contained to one file and nothing else is at risk --
twin-live-infra underneath it is unaffected either way.

## Apply

```bash
cd ~/sentinel_os
# assuming twin-live-infra is already merged to main:
git checkout main
git checkout -b twin-ci-native-postgres
git bundle verify /path/to/twin-ci-native-postgres.bundle
git pull /path/to/twin-ci-native-postgres.bundle twin-ci-native-postgres
git push origin twin-ci-native-postgres
# then open a PR on GitHub from this branch into main, and check the
# Actions tab on the PR before merging.
```

Or via patch:

```bash
git checkout -b twin-ci-native-postgres main
git am /path/to/twin-ci-native-postgres.patch
```
