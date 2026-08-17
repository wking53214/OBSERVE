# Documentation for the 5 remaining module directories -- delivery

Base: ledger-boot-and-ci-gates @ 77b7589 (safe to apply/merge independent
of the other pending branches -- pure documentation, touches no code).
This branch: docs-remaining-modules @ 198cf46, one commit on top.

Closes the last item on the July 22 repo-hygiene list: `Domain/`,
`Engines/`, `Model/`, `Sim/`, `observe/` had no READMEs (governance/,
cassettes/, and regulatory_cassettes/ already did).

## What's in this commit

A `README.md` in each of the five directories, plus a pointer to them
added to the top-level `README.md`'s code-navigation section.

Content is derived from actually reading the code, not from the
existing in-file docstrings (which lean heavily on unverified
"Best-in-Class"/"deterministic"/"governance-safe" language). Confirmed
first, via grep, that all five directories are used only by the
standalone simulator (`iceberg_complete_simulator.py`) and its tests --
not the production governance path -- so each README says that up
front.

Two places where a docstring's own claim didn't hold up against the
actual implementation, called out rather than repeated:

- `Engines/README.md`: `rl_ppo_adaptive.py`'s `PPORouter` doesn't
  actually implement PPO despite the name -- it's an untrained random
  policy with a deterministic wait-time adjustment layered on top, no
  training loop at all. `simple_rl_trainer.py` is the one that
  genuinely trains.
- `Sim/README.md`: `cluster_runner.py`'s `run_batch()` docstring claims
  stable/deterministic future-completion ordering; it actually collects
  via `concurrent.futures.as_completed()`, which yields in real
  completion order, not a guaranteed-stable one.

`Model/README.md` also surfaces `Build_Graph.py`'s own in-file review
notes (mutable neighbor lists, no topology versioning, no cycle
detection) rather than re-deriving or dropping them.

## Verified

No code touched. `Tests/test_graph_integrity.py` and
`Tests/test_system_readiness.py` (the two files most directly exercising
this code) still pass, confirming nothing about actual behavior changed.

## Apply

```bash
cd ~/sentinel_os
git checkout -b docs-remaining-modules ledger-boot-and-ci-gates  # or 77b7589 directly
git bundle verify /path/to/docs-remaining-modules.bundle
git pull /path/to/docs-remaining-modules.bundle docs-remaining-modules
```

Or via patch: `git am /path/to/docs-remaining-modules.patch` on the same
base.
