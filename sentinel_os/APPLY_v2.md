# Applying Cohort Assembly

## What this is

Three commits on top of `9faa298` (the EventV1/OutcomeV1 commit you
already applied), delivered as a `git format-patch` series rather than
a bundle -- `git bundle create` failed in this sandbox with an internal
`pack-objects` error writing to stdout (confirmed not a data problem:
`git pack-objects` works fine writing to a file, only the
stdout-pipe path git bundle relies on is broken here). The patch
series carries the same commits, same messages, same authorship, and
applies with the same integrity guarantee (`git am` checks each
patch's content against your tree as it applies).

## Files

- `0001-Cohort-assembly-prep-persist-obligation-resolution-f.patch`
- `0002-Cohort-assembly-obligation_sweep.py-the-primary-side.patch`
- `0003-Cohort-assembly-twin-endpoint-for-cohort_equity_revi.patch`
- `cohort-assembly-combined.diff` -- all three squashed into one diff,
  for reading/reviewing only. Don't apply this one; apply the three
  numbered patches so you keep three separate, individually-messaged
  commits.

## Prerequisite

Your `main` needs to already be at `9faa298` (the EventV1/OutcomeV1
commit). If you haven't applied that bundle yet, do that first --
these three patches are built on top of it and won't apply to
`56fc612`.

## Apply

```bash
cd ~/sentinel_os/sentinel_os   # repo root -- adjust if yours differs

# 1. Confirm you're on 9faa298 before applying
git log --oneline -1
# should show: 9faa298 EventV1/OutcomeV1: stamped events, durable outcome obligations, live kernel

# 2. Apply the three patches in order, as a new branch
git checkout -b cohort-assembly
git am /path/to/downloaded/0001-*.patch \
       /path/to/downloaded/0002-*.patch \
       /path/to/downloaded/0003-*.patch

# 3. Confirm you got exactly these three commits
git log --oneline -3
# should show:
#   92145f5 Cohort assembly: twin endpoint for cohort_equity_review
#   eaf6a85 Cohort assembly: obligation_sweep.py -- the primary-side sweep for C2 dimensions 4+5
#   822b856 Cohort assembly prep: persist obligation resolution fields, ship domain in the clear
```

(The commit hashes above are from my sandbox; `git am` will produce
new commit hashes when applied to your actual `9faa298`, since
committer/timestamp differ. The commit *messages* and diffs will
match. If `git am` reports a conflict, stop and let me know rather
than resolving it blind -- it would mean your tree has drifted from
what these patches assume.)

## Verify

```bash
export PGHOST=localhost PGUSER=iceberg PGPASSWORD=iceberg PGDATABASE=iceberg
export SENTINEL_REDIS_URL=redis://localhost:6379/0
python -m pytest . --ignore=test_twin_live.py -q
# expect: 584 passed, 6 skipped
```

Run it twice back-to-back from a clean ledger, same as always --
`Tests/conftest.py`'s `test_ledger` fixture drops and recreates
`ledger_entries` per test, but the twin-side tests each register a
fresh, randomly-suffixed replica id, so a stale table from a prior run
shouldn't collide either way.

```bash
ruff check .
bandit -ll -q -r .
```

Both were clean on every file this branch touches at delivery time.

## Merge

```bash
git checkout main
git merge --no-ff cohort-assembly
git push origin main
```

## What you're getting, in order

1. **Obligation resolution persistence fix.** The twin computed
   `favorable`/`resolved_value`/`resolved_at`/`resolution_provenance`/
   `resolution_method` on every RESOLVED transition but never wrote
   them to the database or the hash chain. Fixed and covered.
2. **`domain` shipped in the clear**, primary to twin, parsed from
   `cassette_version`'s fixed `domain:name:version` format. Prevents
   two unrelated cassettes that happen to share an `obligation_kind`
   string from having their cohorts silently merged.
3. **`obligation_sweep.py`** -- the actual cohort assembly: buckets
   resolved obligations by `(domain, obligation_kind)`, builds the
   cohort shapes C2 dimensions 4 (statistical outcome equity) and 5
   (correlation-based proxy detection) each need, runs both checks,
   and packages the result. Runs on the primary, not the twin -- see
   the module's own docstring for why (short version: decision input
   fields dimension 5 needs already live on the primary; shipping them
   to the twin in the clear would be a much bigger exposure than
   domain ever was).
4. **Twin endpoint for `cohort_equity_review`** -- `POST` and `GET
   /replica/{id}/cohort-reviews`, its own hash-chained table, same
   independent-witness posture as everywhere else: the twin stores
   what the sweep computed, it never computes the finding itself.

35 new tests across the three commits (18 + 17 + 10 counted at each
commit's own delivery point in the messages -- 574/584 net passing
count reflects a few tests that replace/rename earlier ones rather
than a straight sum). All new tests run against real Postgres and a
real twin instance -- no mocked governance code.

## Left open (natural next work, not started)

- Nothing schedules the sweep on a cadence yet -- it's a callable, not
  a cron job or endpoint trigger. Wiring `obligation_sweep.sweep()` +
  `record_reviews()` into something that runs periodically (or an
  on-demand admin endpoint on the primary) is the natural next piece,
  separate from this one.
- The cohort-level dimension 4/5 findings this produces aren't wired
  into any individual decision's own `c2_rollup()` -- they're recorded
  as their own `cohort_equity_review` chain record, standalone. Wiring
  them back into per-decision C2 rollups (the way dimension 5's
  correlation-proxy signal got wired into the rollup on July 25) is a
  separate, later decision, deliberately not made here.
- `cohort-reviews` endpoints don't check the ship token the way
  `/entries` does -- matching the existing (pre-existing, not
  introduced by this branch) posture of `/obligations/derive` and
  `/obligations/{id}/transition`, which also don't. If you want
  auth tightened across all the obligation-family endpoints, that's
  one consistent piece of work, not specific to cohort assembly.
