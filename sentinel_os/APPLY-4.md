# Applying: small-gaps list + full July 28 roadmap item 4

Seven patches, apply in order from `~/sentinel_os/sentinel_os` on `main` (currently `abb61a7`):

```
cd ~/sentinel_os/sentinel_os
git checkout main
git pull origin main
git am ~/Downloads/0001-Fix-AC-13-test-fallout-two-pre-existing-tests-never-.patch
git am ~/Downloads/0002-Wire-cohort-equity-findings-into-live-judgment-mortg.patch
git am ~/Downloads/0003-Wire-dimension-6-ZIP-county-geographic-equity-into-c.patch
git am ~/Downloads/0004-Close-the-4th-small-gap-node-role-tags-replace-name-.patch
git am ~/Downloads/0005-AI-cost-tracking-real-token-counts-dollar-cost-discl.patch
git am ~/Downloads/0006-Lease-heartbeat-wire-the-already-built-renewal-into-.patch
git am ~/Downloads/0007-Recommendation-impact-testing-predictive-accuracy-sc.patch
```

(Move all seven `.patch` files to `~/Downloads/` first, or point `git am` at wherever you saved them.)

Then verify:

```
export PGHOST=localhost PGPORT=5432 PGDATABASE=iceberg PGUSER=iceberg PGPASSWORD=iceberg
python3 -m pytest . --ignore=test_twin_live.py -q
```

Expect `756 passed, 6 skipped`. (One throughput-timing test in
`test_api_server_v2.py` flaked once under sandbox load during this session's own
verification, unrelated to any of these patches — if you ever see it flake, just
re-run; it passes clean in isolation.)

**If you see a "Cassette version binding conflict" error** on `ivr:standard-ivr:...`
after applying 0002/0003/0005/0007 (all of which touch shared governance code): that's
expected, not a bug. These patches move the code hash every cassette binds against.
If your local Postgres already has bindings from before these patches, they'll refuse
under the new hash. Fix: drop and let it recreate —
```
psql -h localhost -U iceberg -d iceberg -c "DROP TABLE IF EXISTS ledger_entries CASCADE;"
```
then re-run the suite. This only affects your local dev ledger, not anything already
shipped to a twin.

**0005 and 0007 both add real Postgres columns** the first time they run against an
existing `ledger_entries` table (`ai_cost`, then `shadow_run_hash`) — both via the
same `ADD COLUMN IF NOT EXISTS` pattern every prior optional field used. No manual
step needed.

**0006 needs Redis** — same Redis you already have running for everything else in
this suite, no new setup.

**0007 adds a new CLI** (`python3 recommendation_impact.py run --queue <name>
--cassette-version <version>` / `... score`) meant to run on a schedule, same shape
as `obligation_sweep.py`'s existing CLI. Nothing runs it automatically — that's a
deployment decision for whenever real production data exists to shadow-run against.

## What's in each patch

**0001** — fixes 7 pre-existing tests that broke when the AC-13 ship-token
auth fix merged (not something this session's own change caused — found
while getting a clean baseline before building on top of it).

**0002** — small-gap item 1: `RegulatoryDeck` can now escalate a live
mortgage decision to human review when its cohort has a flagged C2 equity
finding, without ever touching the automated score. Off by default —
nothing changes for any other caller unless you explicitly pass
`twin_client` and `replica_id` when constructing the deck.

**0003** — small-gap item 2: dimension 6 (ZIP/county geographic
equity) is now wired into `c2_rollup()` the same way dimension 5 was —
and 0002's escalation now picks it up automatically, no extra wiring
needed since that code was already generic across dimensions.

**0004** — small-gap item 4: `ivr_events` can now carry an optional `role`
tag (queue/agent/escalation) per stop, so a real event source doesn't have
to rename its stops to match Sentinel's old "*queue*"/agent_a-g name
convention. Wired into all three originally-flagged consumers; only one
of the three (production_harness.py's live queue detection) is actually
on the production path today, the other two are built but not yet called
from there.

Small-gap item 3 (cohort-reviews auth) needed no patch — it turned out to
already be closed by the AC-13 merge (see conversation).

**0005** — roadmap item 4, piece 1 (AI cost tracking). Every real Claude
API call now captures its real token usage and computes a dollar cost from
a pricing table fetched fresh from Anthropic's official docs this session.
Disclosed to the ledger as a new optional hashed field.

**0006** — roadmap item 4, piece 2 (lease/heartbeat). Turned out not to be
greenfield: `queue_schema.py` already had a full, tested lease-renewal
mechanism (`heartbeat()`), grafted in from a separate rebuild — but
`sentinel_worker.py`, the actual production worker, never called it. Fixed
by having the worker's existing reaper timer also heartbeat its own
in-flight job.

**0007** — roadmap item 4, piece 3 (recommendation impact testing),
scoped to predictive-accuracy measurement rather than true A/B impact
testing (your call, since none of the AI recommendation methods this
covers are wired into the live decision path today). Generates real
"shadow" recommendations from real ledger data, records them without
ever acting on them, and scores them later against what actually
happened. Deliberately excludes staffing-adjustment shadow runs — no
real agent-headcount data source exists anywhere in this system to feed
it honestly.

**That closes out Wm's entire July 28 roadmap item 4** (event ingestion,
AI cost tracking, lease/heartbeat, recommendation-impact testing all
done). What's left on the broader roadmap: item 5, the real
phone-system hookup.

## Merge

```
git checkout main
git merge wire-cohort-equity-into-live-judgment --no-ff
git push origin main
```
