# Cross-lens tier-conflict wiring

Built and verified against your real repo (origin/main at `67eea1d`,
same baseline as this session's other delivery). Branch
`cross-lens-tier-conflict-wiring`, single commit `2c0d5e3`.

## What this does

`resolve_tier_conflict` (regulatory_checks.py) has existed and been
tested in isolation since July 23 — nothing ever called it.
`RegulatoryDeck` now detects and resolves it for real: when two or
more LIVE lenses disagree on the same input variable's authorization
tier (C2 dimension 2), a `cross_lens_tier_conflict` finding fires,
disclosed to the ledger like any other live finding, attributed to
whichever lens already held the resolved (stricter) tier.

Detection is **structural**, not a check-name match — any finding
carrying both a `"variable"` and `"tier"` key in its evidence counts,
from whichever lens produced it. The test fixture proves this by
deliberately using a different check name than CFPB's own tier
screen.

Always `ACTION_FLAG` — a conflict between two lenses is a fact for a
human to resolve, not something this deck decides unilaterally.

## Files changed

- `regulatory_deck.py` — new `_cross_lens_tier_conflicts` method,
  wired into both `judge()` (disclosed before any block takes effect)
  and `explain()` (reporting only, writes nothing). Module docstring
  updated.
- `Tests/test_regulatory_cassettes.py` — new `_StrictStateTierLens`
  fixture (models a second jurisdiction that prohibits an input CFPB
  has no declared tier for) and 6 new tests.

## Verification performed

- Full suite: **442 passed, 6 skipped** (436 baseline + 6 new), run
  **twice back-to-back with zero DB reset in between**.
- `ruff check .` — clean (`ruff==0.15.22`, the CI pin).
- `bandit -r . -x ./Tests -ll` — 0 High, 0 Medium.
- Also verified this branch **merges cleanly with the other bundle
  from this session** (`c2-finding-2-correlation-mitigation`) — no
  conflicts, combined suite (452 passed, 6 skipped) green twice
  back-to-back. You can apply either bundle independently, or both.

## How to apply

From your local `sentinel_os` checkout (`origin/main` at `67eea1d`):

```bash
git fetch /path/to/cross-lens-tier-conflict-wiring.bundle cross-lens-tier-conflict-wiring:cross-lens-tier-conflict-wiring
git checkout cross-lens-tier-conflict-wiring
```

Or as a patch on your current branch:

```bash
git am cross-lens-tier-conflict-wiring.patch
```

If you're also applying `c2-finding-2-correlation-mitigation` from
this session, either order works — they touch different files and
merge without conflict (verified above).

## Nothing left open on this one

Unlike the finding-2 mitigation, this wiring doesn't have a deferred
design decision attached — it's a direct completion of work that was
already fully designed and tested in isolation on July 23. Once
applied and merged, this outstanding item is closed.
