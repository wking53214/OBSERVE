# Ledger boot lock + flaky test + real CI gates -- delivery

Base: twin-ci-native-postgres @ d881bc0 (safe to apply/merge independent of
whether the CI native-postgres piece has been verified yet -- this branch
doesn't touch that file's logic, only the ruff/bandit steps within it).
This branch: ledger-boot-and-ci-gates @ 77b7589, one commit on top.

Covers items 6, 8, 9 from the open-items list.

## What's in this commit

1. **Ledger boot-time migration lock** (`governance/ledger_postgres.py`) --
   turned out to be a two-part bug, not the one-line guard originally
   flagged. `Tests/test_ledger_boot_lock.py` (new) proves it: holds an open
   reader on `ledger_entries`, constructs a fresh ledger in another thread,
   asserts construction doesn't block. Two places were unconditionally
   taking `ALTER TABLE`/`DROP TRIGGER`/`CREATE TRIGGER`/`GRANT`-class
   locks on every single construction -- both now check first and only
   take the lock when something would actually change.

2. **The flaky `test_L11_frozen_redis_health_stays_alive`** -- was a bare
   max-latency assertion over ~100-250 samples under heavy concurrent
   load. Now checks p99 against the original tight threshold (still
   catches a genuine hang, which shows as a cluster of slow samples) plus
   a much higher hard ceiling on the true max.

3. **Ruff and bandit are real CI gates now**, not `|| true` decoration.
   Ruff: 73 findings -> 0. Bandit: 2 High + 17 Medium -> 0 and 0, gated at
   Medium+ (`bandit -r . -x ./Tests -ll`). Full detail, including two real
   bugs the lint pass surfaced (not just style noise -- see the commit
   message), is in `git log -1` after applying.

## Verified

Full repo suite, no `--ignore`, all 386 tests, run **twice back-to-back
from a clean database with zero manual reset in between**: 386/386 both
times -- the exact scenario the ledger boot-lock fix exists to survive.
`ruff check .` and `bandit -r . -x ./Tests -ll` both exit 0 standalone.

## Apply

```bash
cd ~/sentinel_os
git checkout -b ledger-boot-and-ci-gates twin-ci-native-postgres  # or d881bc0 directly
git bundle verify /path/to/ledger-boot-and-ci-gates.bundle
git pull /path/to/ledger-boot-and-ci-gates.bundle ledger-boot-and-ci-gates
```

Or via patch: `git am /path/to/ledger-boot-and-ci-gates.patch` on top of
the same base.

Then, once you're happy with it, merge same as the other two branches --
this one has no CI-verification caveat like `twin-ci-native-postgres`
does; everything here was verified directly, so it's safe to merge on its
own timeline regardless of that one's status.
