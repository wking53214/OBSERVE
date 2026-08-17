# C2 Input-Side Checkers -- delivery

Baseline: origin/main @ b660e21 (regulatory-cassette-framework, 341/341 green).
This branch: c2-input-side-checkers @ 97b3571, one commit on top of b660e21.

Full regression on delivery: 365/365 green (341 baseline + 24 new tests in
Tests/test_c2_input_side_checkers.py). Existing Tests/test_regulatory_cassettes.py
is unmodified and still green.

## What's in this commit

- `sentinel_os/regulatory_checks.py` -- dimension 2 (input-authorization tier
  screen), dimension 3 (narrative-legitimacy screen), and the C2 rollup
  function, all added to the existing reusable-checkers module (already inside
  `cassette_forensics._GOVERNANCE_CODE_MODULES`, so no new module needed to be
  added to the code-hash surface).
- `sentinel_os/Tests/test_c2_input_side_checkers.py` -- new, 24 tests, pure
  logic (no Postgres required to run this file alone).
- `sentinel_os/regulatory_cassettes/README.md` -- updated to document the two
  new checks, the rollup, and the current out-of-scope list.

Not touched: `regulatory_cassettes/cfpb_reg_b.py` (the reference lens) is not
wired to the two new checks this session -- see the commit message for why.

## Apply on your Chromebook (pull clean, then push yourself)

From your local clone (`~/sentinel_os` / `chromebook-iceberg`):

```bash
cd ~/sentinel_os
git fetch origin   # make sure you're current; baseline expected at b660e21
git checkout -b c2-input-side-checkers b660e21
git bundle verify /path/to/c2-input-side-checkers.bundle
git pull /path/to/c2-input-side-checkers.bundle c2-input-side-checkers
```

If you'd rather apply the patch instead of the bundle (e.g. to review/edit
before committing):

```bash
cd ~/sentinel_os
git checkout -b c2-input-side-checkers b660e21
git am /path/to/c2-input-side-checkers.patch
```

Then, once you're happy with it:

```bash
python -m pytest . --ignore=test_twin_live.py -q   # full suite, expect 365 passed
git checkout main
git merge --ff-only c2-input-side-checkers
git push origin main
```

(Do not push directly from this session -- per your standing instruction,
that's your call to make from your own machine.)

## One thing worth knowing about how this was verified

Full-suite verification (both the pre-change baseline and the post-change
365/365 run) required a live Postgres + Redis, which this sandbox doesn't
have by default -- I installed `postgresql` and `redis-server` via apt inside
this session's container (both allowed network domains), started them
manually, and created the `iceberg`/`iceberg` role+db matching the CI
workflow, then ran the exact command CI runs
(`python -m pytest . --ignore=test_twin_live.py -q --tb=short`). That's local
sandbox setup only -- it doesn't touch your machine or CI, which already have
their own Postgres/Redis. Flagging it only because one mid-session rerun
turned up a batch of "permission denied for table ledger_entries" failures
across unrelated test files after I'd done several partial/manual test runs
against the same persistent local DB; a full `DROP DATABASE` + recreate
resolved it cleanly and the full suite passed 365/365 after that. That was
sandbox-state cruft from my own repeated manual runs, not a code issue --
your CI spins up fresh Postgres/Redis containers every run, so it won't see
this at all. Noting it so you have the full picture, not because it should
affect what you do next.
