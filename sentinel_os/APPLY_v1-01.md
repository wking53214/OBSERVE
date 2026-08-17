# APPLY — EventV1/OutcomeV1 (v1)

Branch `eventv1-outcomev1`, commit **9faa298**, on top of **56fc612**
(`Remove spent cassette-snapshot-forensics patch artifact from tree`).

21 files changed, 2752 insertions, 17 deletions.

---

## Before you start

Confirm you're on the right base:

```bash
cd ~/sentinel_os
git fetch origin && git checkout main && git pull
git log --oneline -1        # expect 56fc612
```

If HEAD has moved past 56fc612, use the patch route below rather than the
bundle — it will tell you honestly if something conflicts.

---

## Route A — bundle (preferred)

```bash
git fetch /path/to/eventv1-outcomev1.bundle eventv1-outcomev1:eventv1-outcomev1
git log --oneline main..eventv1-outcomev1     # expect one commit, 9faa298
```

Look it over, then:

```bash
git merge --ff-only eventv1-outcomev1
```

## Route B — patch

```bash
git checkout -b eventv1-outcomev1
git am 0001-EventV1-OutcomeV1-stamped-events-durable-outcome-obl.patch
```

---

## Verify before pushing

The cassette code hash moved in this change, so **any cassette binding
already in your local ledger will refuse** until the table is refreshed.
That is binding enforcement working correctly, not a defect — but it will
look like a wall of failures if you don't expect it.

```bash
psql -h localhost -U iceberg -d iceberg -c "DROP TABLE IF EXISTS ledger_entries CASCADE;"
cd sentinel_os
python -m pytest . --ignore=test_twin_live.py -q
```

Expect **544 passed, 6 skipped**. Baseline on 56fc612 is 442 passed, 6
skipped, so 102 of these are new.

Run it a second time without resetting the database — it should be
identical. Then:

```bash
ruff check .        # expect: All checks passed!
bandit -ll -r . -q  # 3 mediums, all pre-existing (test_phase2_limitations
                    # lines 40/164, test_regulatory_cassettes line 128)
```

Then push:

```bash
git push origin main
```

---

## What changed, in one screen

**New modules**

| File | What it owns |
|---|---|
| `event_v1.py` | The three provenance stamps, the method rule, and episode assembly from stamped events. |
| `outcome_v1.py` | The Provenance Rule (module docstring), outcome obligations, bounded reason vocabularies, maturation rules, the cohort return path. |

**Changed**

- `canonical_fields.py` — `outcome_obligation` added to `OPTIONAL_HASHED_FIELDS` (the documented one-line addition).
- `governance/ledger_postgres.py` — new record field, nullable indexed column, canonical form, insert, plus the new `record_outcome_harm_event`. **Two defect fixes**: `verify_chain` was not selecting the new column, and had no `outcome_harm_event` branch.
- `cassette_capabilities.py` — new opt-in `outcome_obligation` capability.
- `cassette_forensics.py` — `event_v1` and `outcome_v1` join the governance code-hash surface.
- `twin_custody.py` / `twin_shipper.py` / `twin_sync_worker.py` / `twin_receiver.py` — clear obligation metadata shipped, new `obligation_ledger` table, three endpoints (derive / transition / list).
- `production_harness.py` — every live call now assembles a validated Episode and runs `judge_episode`.
- `cassettes/ivr_cassette.py` 2.0.1 → **2.0.2**, `cassettes/banking_cassette.py` 2.0.2 → **2.0.3** (moved code hash, behaviour unchanged, neither enables the new capability).

**New tests** — 102 across five files: `test_event_v1.py`, `test_outcome_v1.py`, `test_outcome_chain_records.py`, `test_live_path_kernel_wiring.py`, `test_twin_outcome_obligations.py`.

---

## Two things worth a second look

**1. This does not fix the fabricated data.** The route still comes from the
last digit of the caller's number and the per-node waits are still the fixed
0.1/0.5/0.4 split. What changed is that both now travel stamped `estimated`
with the derivation named in the record, so a reader can tell which parts of
a call were measured. Actually replacing them is the Twilio ingest work.

**2. The kernel judgment is additive.** `quality_score` still drives what the
harness does; the kernel's verdict rides alongside it in the ledger row and
the two are cross-checked. A disagreement is logged and recorded, not acted
on. Swapping the live scoring path in the same change would have made any
behaviour difference impossible to attribute — but it does mean the kernel is
witnessing, not yet driving, and that's a deliberate choice you may want to
revisit once the two have agreed on real traffic for a while.

---

## Left open

- The two new twin endpoints are covered by `TestClient` against a local
  Postgres. They are **not** covered by `test_twin_live.py`'s real
  three-identity/PKI setup, which stays excluded from CI.
- Cohort assembly is still manual. `to_cohort_decision` turns one resolved
  obligation into one `CohortDecision`; nothing yet schedules the sweep that
  collects them and calls `check_statistical_outcome_equity`. That is the
  natural next piece, and it is now unblocked for the first time.
- No cassette in the repo enables `outcome_obligation` yet. The capability,
  the hashed field, the twin store and the derivation are all proven by
  tests, but the first real lending cassette is still to be written.
